from __future__ import annotations

from ..config import BardSettings
from ..contracts import MOOD_LABELS, MusicSegment, StoryFragment
from ..utils import extract_json


STORY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "fragments": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "INTEGER"},
                    "mood": {"type": "STRING", "enum": MOOD_LABELS},
                    "text": {"type": "STRING"},
                    "image_prompt": {"type": "STRING"},
                    "image_assets": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "role": {"type": "STRING", "enum": ["background", "subject", "symbol"]},
                                "label": {"type": "STRING"},
                                "prompt": {"type": "STRING"},
                                "negative_prompt": {"type": "STRING"},
                            },
                            "required": ["role", "label", "prompt"],
                        },
                    },
                    "visual_motif": {"type": "STRING"},
                    "palette": {"type": "STRING"},
                    "motion": {"type": "STRING"},
                },
                "required": ["id", "mood", "text"],
            },
        },
        "full_story": {"type": "STRING"},
    },
    "required": ["fragments", "full_story"],
}


def generate_story_with_gemini(
    segments: list[MusicSegment],
    settings: BardSettings,
    words_per_fragment: int,
) -> tuple[list[StoryFragment], str]:
    if not settings.gcp_project_id:
        raise RuntimeError("Set BARD_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT before using Vertex story generation.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Vertex story generation requires `pip install -e .[cloud]`.") from exc

    client = genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
    segment_lines = "\n".join(
        f"{seg.id}. time={seg.start_s}-{seg.end_s}, mood_hint={seg.mood_hint}, feeling={seg.music_prompt}"
        for seg in segments
    )
    prompt = f"""
BARD is an after-score: it gives visible narrative form to one unique human performance.
Generate one coherent abstract tale that follows the emotional arc below.

Rules:
- Return JSON only.
- Create exactly {len(segments)} fragments, one per music segment.
- Each fragment should be about {words_per_fragment} words and end with a complete sentence.
- Do not mention instruments, recording technology, audio analysis, CLAP, Gemini, or AI.
- Do not write a literal explanation of music. Treat the performance as a hidden narrative force.
- Keep the tale coherent: same world, protagonist/presence, mystery, and final resolution.
- Pick each mood from: {", ".join(MOOD_LABELS)}.
- Also include image_prompt, visual_motif, palette, motion, and image_assets for future image/video generation.
- image_assets should contain 1 to 3 separate visual layers with roles from: background, subject, symbol.
- Make the assets recognizable but unfinished: rough painterly/sketch texture, soft edges, simple composition.
- If the story mentions an important being/object/place/light source, split them into separate assets when useful.
- For subject and symbol assets, prefer one recognizable object on a dark or plain empty background for live blending.
- Avoid text, letters, logos, watermarks, instruments, or photorealistic finished scenes in image prompts.

Music emotional timeline:
{segment_lines}
"""
    response = client.models.generate_content(
        model=settings.vertex_text_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.75,
            response_mime_type="application/json",
            response_schema=STORY_SCHEMA,
        ),
    )
    parsed = extract_json(response.text or "{}")
    raw_fragments = parsed.get("fragments", []) if isinstance(parsed, dict) else []

    fragments: list[StoryFragment] = []
    by_id = {seg.id: seg for seg in segments}
    for idx, item in enumerate(raw_fragments):
        seg_id = int(item.get("id", idx + 1))
        source_seg = by_id.get(seg_id)
        fragments.append(
            StoryFragment(
                id=seg_id,
                mood=str(item.get("mood", source_seg.mood_hint if source_seg else "CALM")).upper(),
                text=" ".join(str(item.get("text", "")).split()),
                music_prompt=source_seg.music_prompt if source_seg else None,
                start_s=source_seg.start_s if source_seg else None,
                end_s=source_seg.end_s if source_seg else None,
                image_prompt=item.get("image_prompt"),
                visual_motif=item.get("visual_motif"),
                palette=item.get("palette"),
                motion=item.get("motion"),
                image_assets=_parse_image_assets(item.get("image_assets", [])),
            )
        )
    full_story = str(parsed.get("full_story") or "\n\n".join(fragment.text for fragment in fragments)).strip()
    return fragments, full_story


def _parse_image_assets(raw_assets: object):
    from ..contracts import image_assets_from_json

    return image_assets_from_json(raw_assets)
