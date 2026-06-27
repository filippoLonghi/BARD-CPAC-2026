from __future__ import annotations

from dataclasses import asdict
import json

from ..config import BardSettings
from ..contracts import MusicSegment
from ..utils import extract_json


CUE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "segments": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "INTEGER"},
                    "story_energy": {"type": "STRING"},
                    "story_tension": {"type": "STRING"},
                    "story_direction": {"type": "STRING"},
                    "suggested_event": {"type": "STRING"},
                    "visual_motion": {"type": "STRING"},
                    "color_direction": {"type": "STRING"},
                },
                "required": [
                    "id",
                    "story_energy",
                    "story_tension",
                    "story_direction",
                    "suggested_event",
                    "visual_motion",
                    "color_direction",
                ],
            },
        }
    },
    "required": ["segments"],
}


def translate_music_to_story_cues(
    segments: list[MusicSegment],
    settings: BardSettings,
) -> list[MusicSegment]:
    """Add child-safe dramatic cues without exposing musical vocabulary to the story writer."""
    if not segments:
        return segments
    if not settings.gcp_project_id:
        raise RuntimeError("Set BARD_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT before translating music cues.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Music cue translation requires `pip install -e .[cloud]`.") from exc

    observations = [
        {
            key: value
            for key, value in asdict(segment).items()
            if key
            in {
                "id",
                "music_prompt",
                "mood_hint",
                "valence",
                "arousal",
                "tension",
                "tempo_bpm",
                "tempo_description",
                "meter",
                "mode",
                "harmony",
                "dynamics",
                "texture",
                "rhythmic_character",
                "instruments",
                "genre_candidates",
                "notable_events",
            }
        }
        for segment in segments
    ]
    prompt = f"""
Convert these musical observations into dramatic directions for a coherent symbolic adventure story for children aged 6-10.
Return exactly one item for every input id and JSON only.

The output is an intermediate story canvas. It must never mention music, audio, tempo, rhythm, harmony,
mode, chords, instruments, genres, performers, or recordings. Translate those observations into:
- story energy and tension
- a change in the plot
- one possible child-safe event
- visual movement and color

Do not invent named characters. The story writer will apply these cues to an existing cast.

INPUT:
{json.dumps(observations, ensure_ascii=False)}
"""
    client = genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
    response = client.models.generate_content(
        model=settings.vertex_text_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.25,
            response_mime_type="application/json",
            response_schema=CUE_SCHEMA,
        ),
    )
    parsed = extract_json(response.text or "{}")
    raw_cues = parsed.get("segments", []) if isinstance(parsed, dict) else []
    by_id = {int(item.get("id", 0)): item for item in raw_cues if isinstance(item, dict)}

    for segment in segments:
        cue = by_id.get(segment.id)
        if not cue:
            raise RuntimeError(f"Gemini did not return a dramatic cue for music segment {segment.id}.")
        segment.story_energy = _clean(cue.get("story_energy"))
        segment.story_tension = _clean(cue.get("story_tension"))
        segment.story_direction = _clean(cue.get("story_direction"))
        segment.suggested_event = _clean(cue.get("suggested_event"))
        segment.visual_motion = _clean(cue.get("visual_motion"))
        segment.color_direction = _clean(cue.get("color_direction"))
    return segments


def translate_music_to_story_cues_local(segments: list[MusicSegment]) -> list[MusicSegment]:
    """Map measured music features to story directions without another API call."""
    previous_tension: float | None = None
    for segment in segments:
        arousal = _number(segment.arousal, 0.5)
        tension = _number(segment.tension, 0.5)
        valence = _number(segment.valence, 0.0)
        segment.story_energy = "high" if arousal >= 0.67 else "low" if arousal <= 0.33 else "medium"
        segment.story_tension = "high" if tension >= 0.67 else "low" if tension <= 0.33 else "medium"
        if previous_tension is None:
            direction = "establish the situation"
        elif tension - previous_tension >= 0.15:
            direction = "increase the obstacle or danger"
        elif previous_tension - tension >= 0.15:
            direction = "offer relief, help, or a useful discovery"
        elif valence >= 0.3:
            direction = "make hopeful progress"
        elif valence <= -0.3:
            direction = "introduce a setback or worry"
        else:
            direction = "continue the journey with a small change"
        segment.story_direction = direction
        segment.suggested_event = direction
        segment.visual_motion = "quick and expanding" if arousal >= 0.67 else "slow and drifting"
        if valence >= 0.3:
            segment.color_direction = "warmer and brighter"
        elif valence <= -0.3:
            segment.color_direction = "cooler and darker"
        else:
            segment.color_direction = "balanced muted colors"
        previous_tension = tension
    return segments


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _number(value: float | None, fallback: float) -> float:
    return fallback if value is None else float(value)
