from __future__ import annotations

import argparse
from pathlib import Path

from .config import BardSettings, load_env_file
from .contracts import story_fragments_from_json
from .pipeline import run_pipeline
from .transport import send_fragments_to_processing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BARD cloud-ready pipeline tools.")
    parser.add_argument("--env-file", default=None, help="Optional .env file. Keep real secret paths outside git.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run-local", help="Run audio analysis, story generation, and optional OSC output.")
    run.add_argument("--audio", required=True, help="Audio file path.")
    run.add_argument("--ratio", default="1/5", help="Chunk size as ratio of duration, for example 1/5.")
    run.add_argument("--audio-provider", choices=["clap", "gemini"], default=None)
    run.add_argument("--story-provider", choices=["local", "mistral", "vertex", "gemini"], default=None)
    run.add_argument("--send-osc", action="store_true", help="Send generated story fragments to Processing.")
    run.add_argument("--out-dir", default=None, help="Optional output directory for this run.")

    osc = sub.add_parser("send-osc", help="Send an existing story.json to Processing.")
    osc.add_argument("--story-json", required=True, help="Path to story.json.")
    osc.add_argument("--duration", type=float, default=10.0, help="Slide duration in seconds.")
    osc.add_argument("--host", default=None)
    osc.add_argument("--port", type=int, default=None)
    osc.add_argument("--delay", type=float, default=2.0)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    load_env_file(Path(args.env_file).expanduser() if args.env_file else None)
    settings = BardSettings.from_env()

    if args.command == "run-local":
        result = run_pipeline(
            audio_path=Path(args.audio),
            settings=settings,
            ratio=args.ratio,
            audio_provider=args.audio_provider,
            story_provider=args.story_provider,
            send_osc=args.send_osc,
            output_dir=Path(args.out_dir).expanduser() if args.out_dir else None,
        )
        print(f"Run complete: {result.run_id}")
        print(f"Fragments: {len(result.fragments)}")
        print(f"Output root: {settings.output_dir}")
        return

    if args.command == "send-osc":
        fragments = story_fragments_from_json(Path(args.story_json).expanduser())
        send_fragments_to_processing(
            fragments=fragments,
            host=args.host or settings.osc_host,
            port=args.port or settings.osc_port,
            slide_duration_s=args.duration,
            start_delay_s=args.delay,
        )
        print(f"Sent {len(fragments)} fragments to {args.host or settings.osc_host}:{args.port or settings.osc_port}")
        return

    parser.error(f"Unsupported command: {args.command}")
