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
    """Legacy helper kept for older entry points that still pass text coverage."""
    safe_duration = max(1.0, duration_s)
    safe_wpm = max(30.0, reading_wpm)
    safe_coverage = max(0.25, min(coverage, 0.95))
    return max(minimum, min(maximum, round(safe_duration * safe_wpm / 60.0 * safe_coverage)))


def target_story_words_from_wpm(
    duration_s: float,
    story_wpm: float,
    *,
    minimum: int = 12,
    maximum: int = 150,
) -> int:
    safe_duration = max(1.0, duration_s)
    safe_wpm = max(20.0, story_wpm)
    return max(minimum, min(maximum, round(safe_duration * safe_wpm / 60.0)))


def story_chunk_seconds(target_words: int, reading_wpm: float, coverage: float = 0.72) -> float:
    safe_words = max(12, target_words)
    safe_wpm = max(30.0, reading_wpm)
    safe_coverage = max(0.25, min(coverage, 0.95))
    return max(8.0, safe_words * 60.0 / (safe_wpm * safe_coverage))


def choose_balanced_fragment_count(
    duration_s: float | None,
    *,
    target_s: float = 60.0,
    min_s: float = 50.0,
    max_s: float = 70.0,
    short_audio_threshold_s: float = 120.0,
) -> int:
    if duration_s is None or duration_s <= 0:
        return 1
    safe_target = max(1.0, target_s)
    safe_min = max(1.0, min_s)
    safe_max = max(safe_min, max_s)
    safe_short = max(safe_target, short_audio_threshold_s)

    if duration_s <= safe_short:
        return 1 if duration_s <= safe_target * 1.25 else 2

    estimated = max(1, round(duration_s / safe_target))
    upper = max(estimated + 3, math.ceil(duration_s / safe_min) + 1)
    candidates = range(max(1, estimated - 3), upper + 1)

    def score(count: int) -> tuple[float, int]:
        fragment_s = duration_s / count
        penalty = abs(fragment_s - safe_target)
        if fragment_s < safe_min:
            penalty += (safe_min - fragment_s) * 3.0
        if fragment_s > safe_max:
            penalty += (fragment_s - safe_max) * 3.0
        return penalty, count

    return min(candidates, key=score)


def music_window_plan(
    fragment_duration_s: float,
    *,
    fixed_window_s: float | None,
    windows_per_fragment: int,
) -> tuple[float, int]:
    duration = max(0.001, fragment_duration_s)
    if fixed_window_s is not None:
        window_s = max(0.001, fixed_window_s)
        return window_s, max(1, round(duration / window_s))
    count = max(1, windows_per_fragment)
    return duration / count, count


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
