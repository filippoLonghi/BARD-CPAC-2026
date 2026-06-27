from __future__ import annotations

from pathlib import Path
import mimetypes
from uuid import uuid4

from ..config import BardSettings
from ..contracts import MOOD_LABELS, MusicSegment
from ..storage import upload_file_to_gcs
from ..utils import extract_json


INLINE_AUDIO_LIMIT_BYTES = 20 * 1024 * 1024


SEGMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "segments": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "INTEGER"},
                    "start_s": {"type": "NUMBER"},
                    "end_s": {"type": "NUMBER"},
                    "music_prompt": {"type": "STRING"},
                    "mood_hint": {"type": "STRING", "enum": MOOD_LABELS},
                    "confidence": {"type": "NUMBER"},
                    "valence": {"type": "NUMBER"},
                    "arousal": {"type": "NUMBER"},
                    "tension": {"type": "NUMBER"},
                    "tempo_bpm": {"type": "NUMBER"},
                    "tempo_description": {"type": "STRING"},
                    "meter": {"type": "STRING"},
                    "mode": {"type": "STRING"},
                    "harmony": {"type": "STRING"},
                    "dynamics": {"type": "STRING"},
                    "texture": {"type": "STRING"},
                    "rhythmic_character": {"type": "STRING"},
                    "instruments": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "genre_candidates": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "notable_events": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": [
                    "id",
                    "music_prompt",
                    "mood_hint",
                    "valence",
                    "arousal",
                    "tension",
                    "tempo_description",
                    "mode",
                    "harmony",
                    "dynamics",
                    "texture",
                    "rhythmic_character",
                    "instruments",
                    "genre_candidates",
                    "notable_events",
                ],
            },
        }
    },
    "required": ["segments"],
}


def analyze_with_gemini(
    audio_path: Path,
    settings: BardSettings,
    target_segments: int,
    duration_s: float | None = None,
) -> list[MusicSegment]:
    if not settings.gcp_project_id:
        raise RuntimeError("Set BARD_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT before using Gemini audio analysis.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Gemini provider requires `pip install -e .[cloud]`.") from exc

    mime_type = mimetypes.guess_type(str(audio_path))[0] or "audio/mpeg"
    client = genai.Client(enterprise=True, project=settings.gcp_project_id, location=settings.gcp_location)

    # For local smoke tests, inline bytes avoid the short delay where a brand-new
    # Vertex service agent cannot yet read objects from Cloud Storage.
    if audio_path.stat().st_size <= INLINE_AUDIO_LIMIT_BYTES:
        audio_part = types.Part.from_bytes(data=audio_path.read_bytes(), mime_type=mime_type)
    elif settings.storage_bucket:
        audio_uri = upload_file_to_gcs(
            local_path=audio_path,
            bucket_name=settings.storage_bucket,
            blob_name=f"inputs/{audio_path.stem}-{uuid4().hex[:8]}{audio_path.suffix}",
        )
        audio_part = types.Part.from_uri(file_uri=audio_uri, mime_type=mime_type)
    else:
        audio_part = types.Part.from_bytes(data=audio_path.read_bytes(), mime_type=mime_type)

    window_instruction = ""
    expected_windows: list[tuple[float, float]] = []
    if duration_s and duration_s > 0:
        window_size = duration_s / target_segments
        expected_windows = [
            (round(index * window_size, 3), round(min(duration_s, (index + 1) * window_size), 3))
            for index in range(target_segments)
        ]
        window_instruction = (
            "Return exactly one segment for each of these fixed time windows, in this order: "
            + ", ".join(f"{start}-{end}s" for start, end in expected_windows)
            + "."
        )

    prompt = f"""
You are analyzing a live human music performance for BARD, an after-score system.
Split the performance into exactly {target_segments} narrative/emotional segments.
{window_instruction}
Do not describe the recording technically. Translate musical change into feeling, texture,
tension, pace, and atmosphere. Use these mood labels only: {", ".join(MOOD_LABELS)}.
For every window also report observable musical evidence:
- valence from -1.0 (very dark/sad) to 1.0 (very bright/joyful)
- arousal and tension from 0.0 to 1.0
- approximate tempo, meter, mode/tonal character, harmony, dynamics, texture, rhythm
- likely instruments and up to three genre candidates
- concrete changes or notable events inside the window
Be cautious: use "uncertain" or an empty list rather than inventing an instrument or genre.

Return JSON only.
"""
    response = client.models.generate_content(
        model=settings.vertex_audio_model,
        contents=[
            prompt,
            audio_part,
        ],
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=SEGMENT_SCHEMA,
        ),
    )
    parsed = extract_json(response.text or "{}")
    raw_segments = parsed.get("segments", []) if isinstance(parsed, dict) else []

    segments: list[MusicSegment] = []
    for idx, item in enumerate(raw_segments[:target_segments]):
        expected_start, expected_end = expected_windows[idx] if expected_windows else (None, None)
        segments.append(
            MusicSegment(
                id=idx + 1,
                start_s=expected_start if expected_start is not None else item.get("start_s"),
                end_s=expected_end if expected_end is not None else item.get("end_s"),
                music_prompt=str(item.get("music_prompt", "")).strip() or "suspended, ambiguous atmosphere",
                mood_hint=str(item.get("mood_hint", "CALM")).upper(),
                confidence=item.get("confidence"),
                source="gemini-audio",
                valence=item.get("valence"),
                arousal=item.get("arousal"),
                tension=item.get("tension"),
                tempo_bpm=item.get("tempo_bpm"),
                tempo_description=item.get("tempo_description"),
                meter=item.get("meter"),
                mode=item.get("mode"),
                harmony=item.get("harmony"),
                dynamics=item.get("dynamics"),
                texture=item.get("texture"),
                rhythmic_character=item.get("rhythmic_character"),
                instruments=_string_list(item.get("instruments")),
                genre_candidates=_string_list(item.get("genre_candidates")),
                notable_events=_string_list(item.get("notable_events")),
            )
        )
    if len(segments) != target_segments:
        raise RuntimeError(f"Gemini returned {len(segments)} audio segments; expected exactly {target_segments}.")
    return segments


def analyze_chunk_with_gemini(
    audio_path: Path,
    settings: BardSettings,
    *,
    segment_id: int,
    start_s: float,
    end_s: float,
) -> MusicSegment:
    segment = analyze_with_gemini(
        audio_path,
        settings,
        target_segments=1,
        duration_s=max(0.001, end_s - start_s),
    )[0]
    segment.id = segment_id
    segment.start_s = start_s
    segment.end_s = end_s
    segment.source = "gemini-audio-chunk"
    return segment


def analyze_chunk_windows_with_gemini(
    audio_path: Path,
    settings: BardSettings,
    *,
    first_segment_id: int,
    start_s: float,
    end_s: float,
    window_s: float,
) -> list[MusicSegment]:
    duration_s = max(0.001, end_s - start_s)
    target_segments = max(1, round(duration_s / max(5.0, window_s)))
    segments = analyze_with_gemini(
        audio_path,
        settings,
        target_segments=target_segments,
        duration_s=duration_s,
    )
    for index, segment in enumerate(segments):
        segment.id = first_segment_id + index
        segment.start_s = start_s + float(segment.start_s or 0.0)
        segment.end_s = min(end_s, start_s + float(segment.end_s or duration_s))
        segment.source = "gemini-audio-grouped-window"
    return segments


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
