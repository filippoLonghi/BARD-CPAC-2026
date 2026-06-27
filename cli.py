from __future__ import annotations

"""Compatibility wrapper for the package CLI.

The maintained command implementation lives in src/bard_core/cli.py.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))

from bard_core.cli import main


if __name__ == "__main__":
    main()
