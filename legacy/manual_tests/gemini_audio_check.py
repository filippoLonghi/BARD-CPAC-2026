from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bard_core.audio.gemini_provider import analyze_with_gemini
from bard_core.config import BardSettings, load_env_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Legacy manual Gemini audio analysis check.")
    parser.add_argument("--audio", required=True, help="Audio file to analyze.")
    parser.add_argument("--env-file", default=None, help="Optional private BARD env file.")
    parser.add_argument("--segments", type=int, default=4, help="Number of analysis windows.")
    args = parser.parse_args()

    load_env_file(Path(args.env_file).expanduser() if args.env_file else None)
    settings = BardSettings.from_env()
    audio_path = Path(args.audio).expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    segments = analyze_with_gemini(
        audio_path=audio_path,
        settings=settings,
        target_segments=args.segments,
    )

    for segment in segments:
        print(f"{segment.id}: {segment.start_s}-{segment.end_s}s {segment.mood_hint} {segment.music_prompt}")


if __name__ == "__main__":
    main()
