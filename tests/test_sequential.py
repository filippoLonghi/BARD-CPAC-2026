from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bard_core.audio.chunks import convert_audio_to_wav, split_audio_file
from bard_core.audio.gemini_provider import analyze_chunk_windows_with_gemini
from bard_core.contracts import ImageAsset, MusicSegment, StoryFragment
from bard_core.pipeline_sequential import _processing_visible_path, _validate_scene_ready
from bard_core.story.gemini_story import _word_count, narrative_phase
from bard_core.story.music_translation import translate_music_to_story_cues_local
from bard_core.utils import choose_balanced_fragment_count, music_window_plan, target_story_words_from_wpm


class SequentialPipelineTests(TestCase):
    def test_audio_is_split_into_exact_requested_fragment_count(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "input.wav"
            with wave.open(str(audio), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(b"\x00\x00" * 24000)

            chunks = split_audio_file(audio, root / "chunks", fragment_count=3)

            self.assertEqual(len(chunks), 3)
            self.assertEqual([round(chunk.start_s, 3) for chunk in chunks], [0.0, 1.0, 2.0])
            self.assertEqual([round(chunk.end_s, 3) for chunk in chunks], [1.0, 2.0, 3.0])
            self.assertTrue(all(chunk.path.exists() for chunk in chunks))

    def test_automatic_balanced_fragment_count_avoids_tiny_final_fragment(self) -> None:
        self.assertEqual(choose_balanced_fragment_count(90.0), 2)
        self.assertEqual(choose_balanced_fragment_count(115.0), 2)
        self.assertEqual(choose_balanced_fragment_count(183.9), 3)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "input.wav"
            with wave.open(str(audio), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(10)
                wav.writeframes(b"\x00\x00" * 1839)

            chunks = split_audio_file(
                audio,
                root / "chunks",
                fragment_count=choose_balanced_fragment_count(183.9),
            )

            self.assertEqual(len(chunks), 3)
            self.assertEqual(round(chunks[0].end_s - chunks[0].start_s, 1), 61.3)
            self.assertEqual(round(chunks[-1].end_s, 1), 183.9)
            self.assertGreater(chunks[-1].end_s - chunks[-1].start_s, 50.0)

    def test_explicit_chunk_seconds_preserves_fixed_size_behavior(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "input.wav"
            with wave.open(str(audio), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(10)
                wav.writeframes(b"\x00\x00" * 1839)

            chunks = split_audio_file(audio, root / "chunks", chunk_s=60)

            self.assertEqual(len(chunks), 4)
            self.assertEqual(round(chunks[-1].end_s - chunks[-1].start_s, 1), 3.9)
            self.assertEqual(round(chunks[-1].end_s, 1), 183.9)

    def test_story_words_use_story_wpm_without_text_coverage(self) -> None:
        self.assertEqual(target_story_words_from_wpm(60.0, 70.0), 70)
        self.assertEqual(target_story_words_from_wpm(45.0, 70.0), 52)

    def test_music_window_plan_derives_windows_per_fragment(self) -> None:
        window_s, count = music_window_plan(45.0, fixed_window_s=None, windows_per_fragment=4)

        self.assertEqual(count, 4)
        self.assertEqual(window_s, 11.25)

        fixed_window_s, fixed_count = music_window_plan(45.0, fixed_window_s=15.0, windows_per_fragment=4)

        self.assertEqual(fixed_window_s, 15.0)
        self.assertEqual(fixed_count, 3)

    def test_audio_conversion_creates_processing_compatible_wav(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.wav"
            target = root / "output" / "processing_audio.wav"
            with wave.open(str(source), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(b"\x00\x00" * 8000)

            converted = convert_audio_to_wav(source, target)

            self.assertTrue(converted.exists())
            with wave.open(str(converted), "rb") as wav:
                self.assertEqual(wav.getframerate(), 8000)
                self.assertEqual(wav.getnchannels(), 1)

    def test_docker_path_is_mapped_to_host_workspace(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "BARD_HOST_WORKSPACE": "C:\\work\\BARD",
                "BARD_CONTAINER_WORKSPACE": "/workspace",
            },
        ):
            mapped = _processing_visible_path(Path("/workspace/runs/demo/image.jpg"))

        self.assertEqual(mapped, "C:/work/BARD/runs/demo/image.jpg")

    def test_story_phase_reserves_final_fragment_for_resolution(self) -> None:
        self.assertEqual(narrative_phase(0, 5), "opening and problem")
        self.assertEqual(narrative_phase(3, 5), "climax")
        self.assertEqual(narrative_phase(4, 5), "resolution")

    def test_story_word_count_uses_whitespace_words(self) -> None:
        self.assertEqual(_word_count("Lilla volò. Poi tornò a casa."), 6)

    def test_one_scene_audio_call_can_return_four_fine_music_windows(self) -> None:
        returned = [
            MusicSegment(id=index + 1, start_s=index * 15, end_s=(index + 1) * 15, music_prompt="change")
            for index in range(4)
        ]
        with patch("bard_core.audio.gemini_provider.analyze_with_gemini", return_value=returned) as analyze:
            segments = analyze_chunk_windows_with_gemini(
                Path("scene.wav"),
                object(),
                first_segment_id=9,
                start_s=120,
                end_s=180,
                window_s=15,
            )

        self.assertEqual(analyze.call_args.kwargs["target_segments"], 4)
        self.assertEqual([segment.id for segment in segments], [9, 10, 11, 12])
        self.assertEqual([segment.start_s for segment in segments], [120, 135, 150, 165])
        self.assertEqual(segments[-1].end_s, 180)

    def test_processing_text_timing_constants_are_exposed(self) -> None:
        root = Path(__file__).resolve().parents[1]
        words_source = (root / "apps" / "processing" / "bard_story_visuals" / "WordsSystem.pde").read_text(
            encoding="utf-8"
        )
        sentence_source = (root / "apps" / "processing" / "bard_story_visuals" / "SentenceDisplay.pde").read_text(
            encoding="utf-8"
        )

        self.assertIn("SENTENCE_STABLE_FRACTION = 0.22f", words_source)
        self.assertIn("SENTENCE_MIN_STABLE_MS = 1200", words_source)
        self.assertIn("SENTENCE_MAX_STABLE_MS = 2400", words_source)
        self.assertIn("SENTENCE_FLIGHT_BUFFER_MS = 2000", words_source)
        self.assertIn("SENTENCE_FLIGHT_BUFFER_MS", sentence_source)

    def test_music_to_story_mapping_is_local_and_tracks_small_changes(self) -> None:
        segments = [
            MusicSegment(id=1, music_prompt="quiet", arousal=0.2, tension=0.2, valence=0.1),
            MusicSegment(id=2, music_prompt="dark", arousal=0.7, tension=0.8, valence=-0.6),
            MusicSegment(id=3, music_prompt="release", arousal=0.4, tension=0.3, valence=0.5),
        ]

        translate_music_to_story_cues_local(segments)

        self.assertEqual(segments[1].story_direction, "increase the obstacle or danger")
        self.assertEqual(segments[2].story_direction, "offer relief, help, or a useful discovery")

    def test_scene_readiness_blocks_blank_start_and_accepts_real_image(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "empty"):
            _validate_scene_ready(StoryFragment(id=1, mood="CALM", text=""), require_image=False)

        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "ready.png"
            image_path.write_bytes(b"image")
            fragment = StoryFragment(
                id=1,
                mood="CALM",
                text="The story begins.",
                image_assets=[
                    ImageAsset(
                        role="background",
                        label="forest",
                        prompt="forest",
                        status="retrieved",
                        local_path=str(image_path),
                    )
                ],
            )
            _validate_scene_ready(fragment, require_image=True)
