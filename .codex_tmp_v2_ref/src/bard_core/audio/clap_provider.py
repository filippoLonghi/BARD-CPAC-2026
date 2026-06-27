from __future__ import annotations

from pathlib import Path
import sys

from ..config import BardSettings
from ..contracts import MusicSegment
from ..utils import parse_time_span


def analyze_with_clap(
    audio_path: Path,
    settings: BardSettings,
    chunk_s: float,
    top_k: int = 1,
) -> list[MusicSegment]:
    if not settings.labelbank_path.exists():
        raise FileNotFoundError(
            f"CLAP labelbank not found: {settings.labelbank_path}. "
            "Run `python -m bard_core.legacy.audio_analysis.build_label_v2` or switch BARD_AUDIO_PROVIDER=gemini."
        )

    root = str(settings.root_dir)
    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        from bard_core.legacy.audio_analysis.clap_local_v2 import run_embeddings
    except ImportError as exc:
        raise RuntimeError(
            "CLAP provider requires the local AI dependencies. Install with `pip install -e .[local-ai]`."
        ) from exc

    raw_results = run_embeddings(
        audio_path=str(audio_path),
        labels=None,
        labelbank_json=str(settings.labelbank_path),
        chunk_s=chunk_s,
        hop_s=None,
        top_k=top_k,
        batch_size=64,
    )

    segments: list[MusicSegment] = []
    for idx, item in enumerate(raw_results):
        top = item.get("top", [])
        best = top[0] if top else {}
        start_s, end_s = parse_time_span(str(item.get("time", "")))
        segments.append(
            MusicSegment(
                id=idx + 1,
                start_s=start_s,
                end_s=end_s,
                music_prompt=str(best.get("label", "uncertain, suspended musical feeling")),
                confidence=best.get("score"),
                source="clap",
            )
        )
    return segments
