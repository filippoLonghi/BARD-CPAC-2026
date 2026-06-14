from __future__ import annotations

from pathlib import Path
import json
import math
import re
import wave


def parse_ratio(value: str) -> float:
    text = value.strip()
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        denom = float(denominator.strip())
        if denom == 0:
            raise ValueError("Ratio denominator cannot be 0.")
        return float(numerator.strip()) / denom
    return float(text)


def compute_chunk_and_words(duration_s: float | None, ratio: str, reading_wpm: float, default_chunk_s: float) -> tuple[float, int]:
    if duration_s and duration_s > 0:
        ratio_value = max(0.001, min(parse_ratio(ratio), 1.0))
        chunk_s = max(1.0, round(duration_s * ratio_value))
    else:
        chunk_s = max(1.0, default_chunk_s)
    words = min(150, max(6, int(round(chunk_s * (reading_wpm / 60.0)))))
    return float(chunk_s), words


def detect_audio_duration(path: Path) -> float | None:
    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(path)
        if audio is not None and audio.info is not None:
            duration = float(audio.info.length)
            if duration > 0:
                return duration
    except (ImportError, OSError, ValueError):
        pass

    try:
        import soundfile as sf

        info = sf.info(str(path))
        if info.duration > 0:
            return float(info.duration)
    except (ImportError, OSError, RuntimeError):
        pass

    try:
        import librosa
    except ImportError:
        librosa = None
    if librosa is not None:
        try:
            return float(librosa.get_duration(path=str(path)))
        except Exception:
            pass

    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav:
                return wav.getnframes() / float(wav.getframerate())
        except Exception:
            return None
    return None


def estimate_segment_count(duration_s: float | None, chunk_s: float, fallback: int = 5) -> int:
    if duration_s and duration_s > 0 and chunk_s > 0:
        return max(1, int(math.ceil(duration_s / chunk_s)))
    return fallback


def target_story_words(
    duration_s: float,
    reading_wpm: float,
    coverage: float = 0.72,
    *,
    minimum: int = 12,
    maximum: int = 150,
) -> int:
    """Reserve part of the segment for word animation and comprehension."""
    safe_duration = max(1.0, duration_s)
    safe_wpm = max(30.0, reading_wpm)
    safe_coverage = max(0.25, min(coverage, 0.95))
    return max(minimum, min(maximum, round(safe_duration * safe_wpm / 60.0 * safe_coverage)))


def story_chunk_seconds(target_words: int, reading_wpm: float, coverage: float = 0.72) -> float:
    safe_words = max(12, target_words)
    safe_wpm = max(30.0, reading_wpm)
    safe_coverage = max(0.25, min(coverage, 0.95))
    return max(8.0, safe_words * 60.0 / (safe_wpm * safe_coverage))


def parse_time_span(text: str) -> tuple[float | None, float | None]:
    numbers = re.findall(r"\d+(?:\.\d+)?", text or "")
    if len(numbers) >= 2:
        return float(numbers[0]), float(numbers[1])
    return None, None


def extract_json(text: str) -> object:
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start = min([i for i in [stripped.find("{"), stripped.find("[")] if i != -1], default=-1)
    end = max(stripped.rfind("}"), stripped.rfind("]"))
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Model did not return valid JSON: {text[:500]}")
    return json.loads(stripped[start : end + 1])
