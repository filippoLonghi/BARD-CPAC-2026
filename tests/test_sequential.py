from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from unittest import TestCase
from unittest.mock import patch
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bard_core.audio.chunks import convert_audio_to_wav, split_audio_file
from bard_core.audio.gemini_provider import analyze_chunk_windows_with_gemini
from bard_core.config import (
    DEFAULT_FRAGMENT_MAX_S,
    DEFAULT_FRAGMENT_MIN_S,
    DEFAULT_FRAGMENT_TARGET_S,
    DEFAULT_SHORT_AUDIO_THRESHOLD_S,
    BardSettings,
)
from bard_core.contracts import ImageAsset, MusicSegment, StoryFragment
from bard_core.pipeline_live import LiveAudioChunk, _fragment_for_live_visual_clock, run_live_pipeline
from bard_core.pipeline_sequential import _processing_visible_path, _validate_scene_ready, run_sequential_pipeline
from bard_core.progress import PipelineTracer
from bard_core.story.gemini_story import _word_count, narrative_phase
from bard_core.story.music_translation import translate_music_to_story_cues_local
from bard_core.utils import choose_balanced_fragment_count, music_window_plan, target_story_words_from_wpm


class SequentialPipelineTests(TestCase):
    def test_live_osc_reschedules_late_fragment_to_visible_window(self) -> None:
        fragment = StoryFragment(id=4, mood="CALM", text="Final text.", start_s=45.0, end_s=60.0)

        adjusted = _fragment_for_live_visual_clock(
            fragment,
            visual_started_at=monotonic() - 70.0,
            chunk_s=15.0,
            tracer=PipelineTracer(),
        )

        self.assertGreater(adjusted.start_s or 0.0, 69.0)
        self.assertAlmostEqual((adjusted.end_s or 0.0) - (adjusted.start_s or 0.0), 15.0, places=2)
        self.assertEqual(fragment.start_s, 45.0)
        self.assertEqual(fragment.end_s, 60.0)

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
        duration_s = 183.9
        fragment_count = choose_balanced_fragment_count(
            duration_s,
            target_s=DEFAULT_FRAGMENT_TARGET_S,
            min_s=DEFAULT_FRAGMENT_MIN_S,
            max_s=DEFAULT_FRAGMENT_MAX_S,
            short_audio_threshold_s=DEFAULT_SHORT_AUDIO_THRESHOLD_S,
        )
        self.assertGreaterEqual(fragment_count, 1)

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
                fragment_count=fragment_count,
            )

            self.assertEqual(len(chunks), fragment_count)
            self.assertEqual(round(chunks[-1].end_s, 1), duration_s)
            expected_chunk_s = duration_s / fragment_count
            self.assertAlmostEqual(chunks[0].end_s - chunks[0].start_s, expected_chunk_s, delta=0.1)
            self.assertGreaterEqual(chunks[-1].end_s - chunks[-1].start_s, min(DEFAULT_FRAGMENT_MIN_S, expected_chunk_s))

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
        flying_source = (root / "apps" / "processing" / "bard_story_visuals" / "FlyingWord.pde").read_text(
            encoding="utf-8"
        )
        director_source = (root / "apps" / "processing" / "bard_story_visuals" / "StoryDirector.pde").read_text(
            encoding="utf-8"
        )

        self.assertRegex(words_source, r"final\s+float\s+SENTENCE_STABLE_FRACTION\s*=")
        self.assertRegex(words_source, r"final\s+int\s+SENTENCE_MIN_STABLE_MS\s*=")
        self.assertRegex(words_source, r"final\s+int\s+SENTENCE_MAX_STABLE_MS\s*=")
        self.assertRegex(words_source, r"final\s+int\s+SENTENCE_FLIGHT_BUFFER_MS\s*=")
        self.assertRegex(words_source, r"final\s+int\s+WORD_MIN_FLIGHT_MS\s*=")
        self.assertRegex(words_source, r"final\s+float\s+WORD_FLIGHT_PX_PER_SECOND\s*=")
        self.assertIn("SENTENCE_FLIGHT_BUFFER_MS", sentence_source)
        self.assertIn("scheduleWordFlights", sentence_source)
        self.assertIn("word.update(elapsed)", sentence_source)
        self.assertIn("currentMergedWordCount += count", words_source)
        self.assertNotIn("word.lockToTarget()", sentence_source)
        self.assertNotIn("desired.setMag", flying_source)
        self.assertNotIn("steer.limit", flying_source)
        self.assertIn("currentSegmentEarliestEndMs", director_source)
        self.assertIn("MIN_LATE_SCENE_DURATION_S", director_source)
        self.assertNotIn("? segment.durationSeconds()", director_source)

    def test_music_to_story_mapping_is_local_and_tracks_small_changes(self) -> None:
        segments = [
            MusicSegment(id=1, music_prompt="quiet", arousal=0.2, tension=0.2, valence=0.1),
            MusicSegment(id=2, music_prompt="dark", arousal=0.7, tension=0.8, valence=-0.6),
            MusicSegment(id=3, music_prompt="release", arousal=0.4, tension=0.3, valence=0.5),
        ]

        translate_music_to_story_cues_local(segments)

        self.assertEqual(segments[1].story_direction, "increase the obstacle or danger")
        self.assertEqual(segments[2].story_direction, "offer relief, help, or a useful discovery")

    def test_scene_readiness_blocks_blank_start_and_requires_two_real_images(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "empty"):
            _validate_scene_ready(StoryFragment(id=1, mood="CALM", text=""), require_image=False)

        with TemporaryDirectory() as tmp:
            background = Path(tmp) / "background.png"
            subject = Path(tmp) / "subject.png"
            background.write_bytes(b"image")
            subject.write_bytes(b"image")
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
                        local_path=str(background),
                    )
                ],
            )
            with self.assertRaisesRegex(RuntimeError, "background and subject"):
                _validate_scene_ready(fragment, require_image=True)
            fragment.image_assets.append(
                ImageAsset(
                    role="subject",
                    label="hero",
                    prompt="hero",
                    status="generated",
                    local_path=str(subject),
                )
            )
            _validate_scene_ready(fragment, require_image=True)

    def test_trace_logger_records_major_events(self) -> None:
        tracer = PipelineTracer(enabled=False)

        tracer.log("RUN start", id="demo")
        tracer.log("FRAGMENT analysis done", fragment=1, segments=4)

        events = tracer.to_json()
        self.assertEqual(events[0]["label"], "RUN start")
        self.assertEqual(events[1]["fragment"], 1)

    def test_sequential_pipeline_writes_compact_artifacts_and_removes_temp_chunks(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "input.wav"
            out_dir = root / "run"
            self._write_wav(audio, seconds=3)

            with self._patched_pipeline(out_dir):
                run_sequential_pipeline(
                    audio,
                    _settings(root),
                    fragment_count=2,
                    generate_images=True,
                    image_provider="openverse",
                    output_dir=out_dir,
                )

            self.assertTrue((out_dir / "story.json").exists())
            self.assertTrue((out_dir / "run_manifest.json").exists())
            self.assertFalse((out_dir / "result.json").exists())
            self.assertFalse((out_dir / "music_segments.json").exists())
            self.assertFalse((out_dir / "scene_cards.json").exists())
            self.assertFalse((out_dir / "audio_chunks").exists())

            story_text = (out_dir / "story.json").read_text(encoding="utf-8")
            self.assertIn('"schema": "bard.replay_story"', story_text)
            self.assertNotIn("story_bible", story_text)
            self.assertNotIn("music_segments", story_text)

    def test_debug_artifacts_and_audio_chunks_are_optional(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "input.wav"
            out_dir = root / "run"
            self._write_wav(audio, seconds=1)

            with self._patched_pipeline(out_dir):
                run_sequential_pipeline(
                    audio,
                    _settings(root),
                    fragment_count=1,
                    generate_images=True,
                    image_provider="openverse",
                    output_dir=out_dir,
                    debug_artifacts=True,
                    keep_audio_chunks=True,
                )

            self.assertTrue((out_dir / "debug" / "result.json").exists())
            self.assertTrue((out_dir / "debug" / "music_segments.json").exists())
            self.assertTrue((out_dir / "debug" / "scene_cards.json").exists())
            self.assertTrue((out_dir / "audio_chunks" / "segment_001.wav").exists())

    def test_startup_buffer_fragments_are_complete_before_start(self) -> None:
        events: list[str] = []

        class FakeOsc:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def start(self) -> None:
                events.append("osc-startup")

            def await_ready(self, timeout_s: float) -> None:
                events.append("ready")

            def send(self, fragment: StoryFragment, *, final: bool = False) -> None:
                events.append(f"send-{fragment.id}")

            def settle(self, delay_s: float) -> None:
                events.append("settle")

            def prime(self, timeout_s: float) -> None:
                events.append("prime")

            def play(self) -> None:
                events.append("play")

            def set_processing_audio(self, audio_path: str) -> None:
                events.append("audio")

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "input.wav"
            out_dir = root / "run"
            self._write_wav(audio, seconds=2)

            def fake_analysis(*args, **kwargs):
                fragment_id = len([event for event in events if event.startswith("analysis")]) + 1
                events.append(f"analysis-{fragment_id}-after-play-{int('play' in events)}")
                start_s = kwargs["start_s"]
                end_s = kwargs["end_s"]
                return [MusicSegment(id=fragment_id, start_s=start_s, end_s=end_s, music_prompt="music", mood_hint="CALM")]

            with self._patched_pipeline(out_dir, fake_analysis=fake_analysis):
                with patch("bard_core.pipeline_sequential.ProcessingOscStream", FakeOsc):
                    run_sequential_pipeline(
                        audio,
                        _settings(root),
                        fragment_count=3,
                        generate_images=True,
                        image_provider="openverse",
                        send_osc=True,
                        startup_delay_s=0,
                        startup_buffer_fragments=2,
                        output_dir=out_dir,
                    )

        self.assertLess(events.index("send-1"), events.index("prime"))
        self.assertLess(events.index("send-2"), events.index("prime"))
        self.assertLess(events.index("prime"), events.index("play"))
        self.assertLess(events.index("play"), events.index("analysis-3-after-play-1"))
        self.assertIn("send-3", events)

    def test_live_pipeline_buffers_complete_fragments_and_never_uses_playback(self) -> None:
        events: list[str] = []

        class FakeOsc:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def start(self) -> None:
                events.append("osc-startup")

            def await_ready(self, timeout_s: float) -> None:
                events.append("ready")

            def send(self, fragment: StoryFragment, *, final: bool = False) -> None:
                events.append(f"send-{fragment.id}-final-{int(final)}")

            def send_images(self, fragment: StoryFragment) -> None:
                events.append(f"send-images-{fragment.id}")

            def settle(self, delay_s: float) -> None:
                events.append("settle")

            def prime(self, timeout_s: float) -> None:
                events.append("prime")

            def play(self) -> None:
                events.append("play")

            def finish(self) -> None:
                events.append("finish")

            def set_processing_audio(self, audio_path: str) -> None:
                events.append("audio")

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "live"
            chunk_1 = root / "chunk_1.wav"
            chunk_2 = root / "chunk_2.wav"
            self._write_wav(chunk_1, seconds=1)
            self._write_wav(chunk_2, seconds=1)

            def fake_analysis(*args, **kwargs):
                fragment_id = kwargs["first_segment_id"]
                return [
                    MusicSegment(
                        id=fragment_id,
                        start_s=kwargs["start_s"],
                        end_s=kwargs["end_s"],
                        music_prompt="music",
                        mood_hint="CALM",
                    )
                ]

            def fake_story(segment, settings, **kwargs):
                fragment_id = kwargs["fragment_index"] + 1
                return (
                    StoryFragment(
                        id=fragment_id,
                        mood="CALM",
                        text=f"Live fragment {fragment_id}.",
                        start_s=segment.start_s,
                        end_s=segment.end_s,
                        keywords=["live"],
                        image_assets=[
                            ImageAsset(role="background", label="bg", prompt="bg"),
                            ImageAsset(role="subject", label="subject", prompt="subject"),
                        ],
                    ),
                    {"last_event": f"live fragment {fragment_id}"},
                )

            def fake_images(fragments, settings, output_dir, **kwargs):
                fragment = fragments[0]
                events.append(f"image-start-{fragment.id}")
                output_dir.mkdir(parents=True, exist_ok=True)
                for asset in fragment.image_assets:
                    path = output_dir / f"{fragment.id}_{asset.role}.png"
                    path.write_bytes(b"image")
                    asset.local_path = str(path)
                    asset.status = "retrieved"
                events.append(f"image-done-{fragment.id}")
                return {
                    "planned_image_assets": 2,
                    "generated_image_assets": 2,
                    "failed_image_assets": 0,
                    "estimated_cost_usd": 0.0,
                }

            def fake_chunks(*args, **kwargs):
                yield LiveAudioChunk(id=1, path=chunk_1, start_s=0, end_s=1, final_available=False)
                yield LiveAudioChunk(id=2, path=chunk_2, start_s=1, end_s=2, final_available=True)

            with patch.multiple(
                "bard_core.pipeline_live",
                ProcessingOscStream=FakeOsc,
                _ensure_microphone_dependencies=lambda: None,
                _record_live_chunks=fake_chunks,
                analyze_chunk_windows_with_gemini=fake_analysis,
                create_story_bible=lambda segments, settings, total: {"title": "Live", "beat_plan": ["one", "two", "three"]},
                generate_story_fragment_with_gemini=fake_story,
                generate_images_for_fragments=fake_images,
                upload_directory_to_gcs=lambda **kwargs: "gs://test/live",
            ):
                result = run_live_pipeline(
                    settings=_settings(root),
                    duration_seconds=3,
                    chunk_s=1,
                    generate_images=True,
                    image_provider="openverse",
                    startup_delay_s=0,
                    startup_buffer_fragments=2,
                    output_dir=out_dir,
                )

            self.assertEqual(len(result.fragments), 2)
            self.assertFalse(result.metadata["complete"])
            self.assertEqual(result.metadata["chunk_s"], 1)
            self.assertEqual(result.metadata["startup_buffer_fragments"], 2)
            self.assertTrue((out_dir / "recorded_audio.wav").exists())
            self.assertEqual(result.metadata["recorded_audio_path"], str(out_dir / "recorded_audio.wav"))
            self.assertNotIn("audio", events)
            self.assertLess(events.index("image-done-1"), events.index("send-1-final-0"))
            self.assertLess(events.index("image-done-2"), events.index("send-2-final-0"))
            self.assertLess(events.index("send-1-final-0"), events.index("prime"))
            self.assertLess(events.index("send-images-1"), events.index("prime"))
            self.assertLess(events.index("send-2-final-0"), events.index("prime"))
            self.assertLess(events.index("send-images-2"), events.index("prime"))
            self.assertLess(events.index("prime"), events.index("play"))
            self.assertLess(events.index("play"), events.index("finish"))

    def _patched_pipeline(self, out_dir: Path, fake_analysis=None):
        def fake_generate_story(segment, settings, **kwargs):
            fragment_id = kwargs["fragment_index"] + 1
            return (
                StoryFragment(
                    id=fragment_id,
                    mood="CALM",
                    text=f"Fragment {fragment_id} is ready.",
                    start_s=segment.start_s,
                    end_s=segment.end_s,
                    keywords=["ready"],
                    image_assets=[
                        ImageAsset(role="background", label="bg", prompt="bg"),
                        ImageAsset(role="subject", label="subject", prompt="subject"),
                    ],
                ),
                {"last_event": f"fragment {fragment_id}"},
            )

        def fake_images(fragments, settings, output_dir, **kwargs):
            output_dir.mkdir(parents=True, exist_ok=True)
            for fragment in fragments:
                for asset in fragment.image_assets:
                    path = output_dir / f"{fragment.id}_{asset.role}.png"
                    path.write_bytes(b"image")
                    asset.local_path = str(path)
                    asset.status = "retrieved"
                    asset.provider = kwargs["provider"]
                    asset.model = "test"
            return {
                "planned_image_assets": 2,
                "generated_image_assets": 2,
                "failed_image_assets": 0,
                "estimated_cost_usd": 0.0,
            }

        analysis = fake_analysis or (
            lambda *args, **kwargs: [
                MusicSegment(
                    id=kwargs["first_segment_id"],
                    start_s=kwargs["start_s"],
                    end_s=kwargs["end_s"],
                    music_prompt="music",
                    mood_hint="CALM",
                )
            ]
        )
        return patch.multiple(
            "bard_core.pipeline_sequential",
            analyze_chunk_windows_with_gemini=analysis,
            create_story_bible=lambda segments, settings, total: {"title": "Test", "beat_plan": ["one", "two"]},
            generate_story_fragment_with_gemini=fake_generate_story,
            generate_images_for_fragments=fake_images,
            prepare_audio_playback=lambda path: type(
                "FakePlayback",
                (),
                {"play": lambda self: None, "wait": lambda self: None},
            )(),
            upload_directory_to_gcs=lambda **kwargs: "gs://test/run",
        )

    def _write_wav(self, path: Path, *, seconds: int) -> None:
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b"\x00\x00" * 8000 * seconds)


def _settings(tmp_path: Path) -> BardSettings:
    return BardSettings(
        root_dir=tmp_path,
        output_dir=tmp_path / "runs",
        labelbank_path=tmp_path / "labels.json",
        audio_provider="gemini",
        story_provider="vertex",
        gcp_project_id="project",
        gcp_location="europe-west1",
        vertex_text_model="gemini-2.5-flash",
        vertex_audio_model="gemini-2.5-flash",
        storage_bucket=None,
        local_story_model="mistral",
        image_provider="none",
        max_image_assets=2,
        image_aspect_ratio="1:1",
        image_timeout_s=10,
        image_model="imagen-4.0-fast-generate-001",
        image_location="europe-west1",
        remove_image_background=False,
        background_removal_provider="fallback",
        replicate_api_token=None,
        replicate_model="black-forest-labs/flux-schnell",
        imagen_model="imagen-4.0-fast-generate-001",
        imagen_location="europe-west1",
        osc_host="127.0.0.1",
        osc_port=5005,
        osc_ready_port=5007,
        osc_ready_bind_host="127.0.0.1",
        processing_ready_timeout_s=1,
        default_chunk_s=30,
        default_wpm=180,
        story_wpm=70,
        fragment_target_s=60,
        fragment_min_s=50,
        fragment_max_s=70,
        short_audio_threshold_s=120,
        story_language="English",
        story_level="children",
        text_coverage=0.72,
        target_words_per_fragment=32,
        music_window_s=None,
        music_windows_per_fragment=1,
        story_scene_s=60,
        processing_startup_delay_s=0,
        startup_buffer_fragments=2,
        live_story_wpm=70,
        live_music_windows_per_fragment=2,
        live_story_scene_s=30,
        live_startup_buffer_fragments=2,
        use_4bit=False,
    )
