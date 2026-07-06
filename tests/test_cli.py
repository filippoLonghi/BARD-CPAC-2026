from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bard_core.cli import build_parser, main
from bard_core.contracts import write_json


class CliTests(TestCase):
    def test_run_fragments_is_supported_and_run_local_is_absent_from_help(self) -> None:
        parser = build_parser()
        output = StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["--help"])

        self.assertEqual(raised.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("run-fragments", help_text)
        self.assertIn("run-live", help_text)
        self.assertIn("replay-live", help_text)
        self.assertNotIn("run-local", help_text)

    def test_run_fragments_forwards_debug_artifacts_and_keep_audio_chunks(self) -> None:
        with TemporaryDirectory() as tmp:
            audio = Path(tmp) / "input.wav"
            audio.write_bytes(b"not used")

            with patch("bard_core.cli.run_sequential_pipeline") as run:
                run.return_value = SimpleNamespace(run_id="test-run", fragments=[])
                with redirect_stdout(StringIO()):
                    main(
                        [
                            "run-fragments",
                            "--audio",
                            str(audio),
                            "--debug-artifacts",
                            "--keep-audio-chunks",
                            "--startup-buffer-fragments",
                            "2",
                        ]
                    )

        self.assertTrue(run.call_args.kwargs["debug_artifacts"])
        self.assertTrue(run.call_args.kwargs["keep_audio_chunks"])
        self.assertEqual(run.call_args.kwargs["startup_buffer_fragments"], 2)

    def test_run_fragments_defaults_do_not_keep_debug_artifacts_or_audio_chunks(self) -> None:
        with TemporaryDirectory() as tmp:
            audio = Path(tmp) / "input.wav"
            audio.write_bytes(b"not used")

            with patch("bard_core.cli.run_sequential_pipeline") as run:
                run.return_value = SimpleNamespace(run_id="test-run", fragments=[])
                with redirect_stdout(StringIO()):
                    main(["run-fragments", "--audio", str(audio)])

        self.assertFalse(run.call_args.kwargs["debug_artifacts"])
        self.assertFalse(run.call_args.kwargs["keep_audio_chunks"])

    def test_run_live_requires_duration_seconds(self) -> None:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised:
            main(["run-live"])

        self.assertEqual(raised.exception.code, 2)

    def test_run_live_can_list_input_devices_without_duration(self) -> None:
        output = StringIO()
        with patch("bard_core.cli.list_audio_input_devices", return_value=["3: Laptop Mic (1 input channel(s), 44100 Hz)"]):
            with redirect_stdout(output):
                main(["run-live", "--list-input-devices"])

        self.assertIn("Laptop Mic", output.getvalue())

    def test_run_live_can_test_input_device_without_duration(self) -> None:
        output = StringIO()
        with patch("bard_core.cli.test_audio_input_device", return_value={"duration_s": 1.0, "rms": 0.2, "peak": 0.4}) as test:
            with redirect_stdout(output):
                main(["run-live", "--input-device", "5", "--test-input-seconds", "1"])

        self.assertEqual(test.call_args.kwargs["input_device"], "5")
        self.assertIn("MIC_OK", output.getvalue())

    def test_run_live_forwards_options(self) -> None:
        with patch("bard_core.cli.run_live_pipeline") as run:
            run.return_value = SimpleNamespace(run_id="live-run", fragments=[])
            with redirect_stdout(StringIO()):
                main(
                    [
                        "run-live",
                        "--duration-seconds",
                        "120",
                        "--chunk-seconds",
                        "20",
                        "--input-device",
                        "3",
                        "--sample-rate",
                        "48000",
                        "--startup-buffer-fragments",
                        "3",
                        "--generate-images",
                        "--image-provider",
                        "openverse",
                        "--debug-artifacts",
                        "--keep-audio-chunks",
                    ]
                )

        self.assertEqual(run.call_args.kwargs["duration_seconds"], 120)
        self.assertEqual(run.call_args.kwargs["input_device"], "3")
        self.assertEqual(run.call_args.kwargs["sample_rate"], 48000)
        self.assertEqual(run.call_args.kwargs["chunk_s"], 20)
        self.assertEqual(run.call_args.kwargs["startup_buffer_fragments"], 3)
        self.assertTrue(run.call_args.kwargs["generate_images"])
        self.assertEqual(run.call_args.kwargs["image_provider"], "openverse")
        self.assertTrue(run.call_args.kwargs["debug_artifacts"])
        self.assertTrue(run.call_args.kwargs["keep_audio_chunks"])

    def test_replay_live_uses_recorded_audio_from_run_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recorded_audio = root / "recorded_audio.wav"
            recorded_audio.write_bytes(b"wav")
            write_json(
                root / "story.json",
                {
                    "schema": "bard.replay_story",
                    "fragments": [
                        {"id": 1, "mood": "CALM", "text": "One.", "start_s": 0.0, "end_s": 15.0}
                    ],
                    "full_story": "One.",
                },
            )
            write_json(root / "run_manifest.json", {"metadata": {"chunk_s": 15}})

            with patch("bard_core.cli.send_fragments_to_processing") as replay:
                with redirect_stdout(StringIO()):
                    main(
                        [
                            "replay-live",
                            "--run-dir",
                            str(root),
                            "--playback",
                            "python",
                        ]
                    )

        self.assertEqual(replay.call_args.kwargs["audio_path"], recorded_audio)
        self.assertIsNone(replay.call_args.kwargs["processing_audio_path"])
        self.assertEqual(replay.call_args.kwargs["slide_duration_s"], 15)
        self.assertTrue(replay.call_args.kwargs["include_images"])

    def test_current_docs_do_not_present_run_local_as_a_command(self) -> None:
        root = Path(__file__).resolve().parents[1]
        doc_paths = [root / "README.md", *sorted((root / "docs").glob("*.md"))]

        offenders = [str(path.relative_to(root)) for path in doc_paths if "run-local" in path.read_text(encoding="utf-8")]

        self.assertEqual(offenders, [])
