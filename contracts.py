from pathlib import Path
import sys

src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from bard_core.contracts import *  # noqa: F401,F403
