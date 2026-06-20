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
