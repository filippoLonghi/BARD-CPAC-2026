from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bard_core.cli import build_parser, main


class CliTests(TestCase):
    def test_run_fragments_is_supported_and_run_local_is_absent_from_help(self) -> None:
        parser = build_parser()
        output = StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["--help"])

        self.assertEqual(raised.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("run-fragments", help_text)
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
                        ]
                    )

        self.assertTrue(run.call_args.kwargs["debug_artifacts"])
        self.assertTrue(run.call_args.kwargs["keep_audio_chunks"])

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

    def test_current_docs_do_not_present_run_local_as_a_command(self) -> None:
        root = Path(__file__).resolve().parents[1]
        doc_paths = [root / "README.md", *sorted((root / "docs").glob("*.md"))]

        offenders = [str(path.relative_to(root)) for path in doc_paths if "run-local" in path.read_text(encoding="utf-8")]

        self.assertEqual(offenders, [])
