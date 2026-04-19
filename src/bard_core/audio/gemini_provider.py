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
                },
                "required": ["id", "music_prompt", "mood_hint"],
            },
        }
    },
    "required": ["segments"],
}


def analyze_with_gemini(
    audio_path: Path,
    settings: BardSettings,
    target_segments: int,
) -> list[MusicSegment]:
    if not settings.gcp_project_id:
        raise RuntimeError("Set BARD_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT before using Gemini audio analysis.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Gemini provider requires `pip install -e .[cloud]`.") from exc

    mime_type = mimetypes.guess_type(str(audio_path))[0] or "audio/mpeg"
    client = genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)

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

    prompt = f"""
You are analyzing a live human music performance for BARD, an after-score system.
Split the performance into {target_segments} narrative/emotional segments.
Do not describe the recording technically. Translate musical change into feeling, texture,
tension, pace, and atmosphere. Use these mood labels only: {", ".join(MOOD_LABELS)}.

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
    for idx, item in enumerate(raw_segments):
        segments.append(
            MusicSegment(
                id=int(item.get("id", idx + 1)),
                start_s=item.get("start_s"),
                end_s=item.get("end_s"),
                music_prompt=str(item.get("music_prompt", "")).strip() or "suspended, ambiguous atmosphere",
                mood_hint=str(item.get("mood_hint", "CALM")).upper(),
                confidence=item.get("confidence"),
                source="gemini-audio",
            )
        )
    return segments
