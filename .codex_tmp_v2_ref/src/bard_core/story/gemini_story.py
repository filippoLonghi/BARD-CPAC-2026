from __future__ import annotations

import hashlib
import json
from typing import Any

from ..config import BardSettings
from ..contracts import ImageAsset, MOOD_LABELS, MusicSegment, StoryFragment, mood_cues_from_music_segments
from ..utils import extract_json

WORLD_PROFILES: dict[str, dict[str, str]] = {
    "medieval_citadel": {
        "setting": "a medieval citadel of bridges, bells, banners, stone gates, and hidden workshops",
        "cast_style": "non-human guardians, talking shields, bell spirits, clock scribes, carts, masks, and animated tools",
        "visual_palette": "stone grey, banner red, tarnished gold, torch amber, rain-washed blue",
        "name_style": "short names that sound carved, heraldic, or bell-like",
        "avoid": "default woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
    "cyberpunk_rooftops": {
        "setting": "a bright future city of rooftop gardens, neon bridges, signal rails, rain collectors, and friendly drones",
        "cast_style": "robots, courier kites, signal spirits, living billboards, repair machines, masks, and gentle vehicles",
        "visual_palette": "electric cyan, hot pink, rain black, chrome silver, soft yellow windows",
        "name_style": "compact names with sparks, circuits, signs, and city sounds",
        "avoid": "default woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
    "clockwork_city": {
        "setting": "a clockwork city of gears, towers, wind-up streets, ticking plazas, and brass observatories",
        "cast_style": "mechanical animals only if clearly clockwork, animated tools, gear spirits, clocks, masks, and small machines",
        "visual_palette": "brass, teal patina, ivory enamel, graphite, warm lamp glow",
        "name_style": "precise names with clicks, chimes, numbers, and workshop sounds",
        "avoid": "organic woodland, meadow, fairy forest, insects, foxes, cats, owls, and natural forest animals",
    },
    "radio_tower": {
        "setting": "a lonely radio tower above quilted fields, cloud rooms, antenna bridges, and humming signal cabins",
        "cast_style": "signal spirits, radio parts, living antennas, messenger balloons, static masks, and helpful machines",
        "visual_palette": "midnight blue, copper wire, signal green, pale cloud grey, warm beacon red",
        "name_style": "names that sound like callsigns, waves, beacons, and clear short radio words",
        "avoid": "default woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
    "underwater_ruins": {
        "setting": "underwater ruins with bubble libraries, coral gates, quiet statues, pearl lamps, and sunken stairways",
        "cast_style": "current spirits, living statues, shell machines, lantern fish-shaped devices, masks, and tide tools",
        "visual_palette": "deep turquoise, sea glass green, pearl white, shadow violet, soft gold",
        "name_style": "flowing names with tides, shells, currents, bells, and ancient stone sounds",
        "avoid": "land woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
    "moon_archive": {
        "setting": "a moon archive of silver shelves, crater courtyards, quiet telescopes, star maps, and floating paper rooms",
        "cast_style": "lunar librarians, animated maps, telescope spirits, paper machines, masks, and gentle moon rovers",
        "visual_palette": "silver, ink blue, soft white, violet shadow, dusty gold",
        "name_style": "quiet names that sound lunar, archival, starry, or written in silver ink",
        "avoid": "default woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
    "desert_caravan": {
        "setting": "a desert caravan crossing singing dunes, lantern tents, glass wells, mirrored rocks, and star trails",
        "cast_style": "sand spirits, walking tents, lantern guardians, map masks, caravan carts, animated tools, and wind machines",
        "visual_palette": "saffron, lapis blue, copper, sand gold, night indigo",
        "name_style": "warm names with wind, lantern, star, glass, and caravan sounds",
        "avoid": "default woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
    "festival_harbor": {
        "setting": "a festival harbor of floating stages, lantern boats, tide bells, rope bridges, and colorful market docks",
        "cast_style": "boats, bell spirits, lantern masks, dock machines, animated flags, and helpful floating tools",
        "visual_palette": "lantern orange, harbor blue, flag red, mint green, pearl white",
        "name_style": "cheerful names with bells, flags, boats, lights, and harbor calls",
        "avoid": "default woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
    "storm_airship": {
        "setting": "a storm airship route above cloud canyons, thunder towers, sail balloons, and lightning kitchens",
        "cast_style": "airships, cloud spirits, storm tools, compass masks, engine helpers, and animated sails",
        "visual_palette": "storm purple, lightning white, brass, cloud grey, emergency red",
        "name_style": "bold names with wind, thunder, sails, compasses, and engine sounds",
        "avoid": "default woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
    "volcanic_workshop": {
        "setting": "a volcanic workshop of lava mills, basalt lifts, glowing anvils, steam pipes, and cooled-crystal paths",
        "cast_style": "forge spirits, animated tools, furnace machines, basalt masks, carts, and gentle elemental helpers",
        "visual_palette": "ember orange, basalt black, molten gold, smoke grey, mineral green",
        "name_style": "sturdy names with sparks, stone, steam, tools, and forge sounds",
        "avoid": "default woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
    "polar_observatory": {
        "setting": "a polar observatory of aurora domes, ice lenses, snow bridges, weather rooms, and star-measuring towers",
        "cast_style": "aurora spirits, telescope machines, weather masks, animated instruments, sled-like vehicles, and ice tools",
        "visual_palette": "aurora green, glacier blue, white, violet night, brass instrument details",
        "name_style": "clear names with stars, ice, auroras, lenses, and north-wind sounds",
        "avoid": "default woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
    "sky_market": {
        "setting": "a sky market of floating stalls, kite bridges, cloud cranes, bell balloons, and sunrise elevators",
        "cast_style": "kite spirits, market carts, animated umbrellas, cloud machines, masks, balloons, and living signboards",
        "visual_palette": "sunrise peach, sky blue, kite red, cream cloud, polished brass",
        "name_style": "light names with kites, bells, markets, clouds, and morning sounds",
        "avoid": "default woodland, meadow, fairy forest, insects, foxes, cats, owls, and small forest animals",
    },
}


BIBLE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "protagonist": {"type": "STRING"},
        "protagonist_trait": {"type": "STRING"},
        "protagonist_flaw": {"type": "STRING"},
        "protagonist_goal": {"type": "STRING"},
        "protagonist_visual_identity": {"type": "STRING"},
        "antagonist": {"type": "STRING"},
        "antagonist_motive": {"type": "STRING"},
        "antagonist_visual_identity": {"type": "STRING"},
        "helper": {"type": "STRING"},
        "helper_visual_identity": {"type": "STRING"},
        "setting": {"type": "STRING"},
        "magical_rule": {"type": "STRING"},
        "central_problem": {"type": "STRING"},
        "stakes": {"type": "STRING"},
        "moral": {"type": "STRING"},
        "ending_target": {"type": "STRING"},
        "beat_plan": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": [
        "title",
        "protagonist",
        "protagonist_trait",
        "protagonist_flaw",
        "protagonist_goal",
        "protagonist_visual_identity",
        "antagonist",
        "antagonist_motive",
        "antagonist_visual_identity",
        "helper",
        "helper_visual_identity",
        "setting",
        "magical_rule",
        "central_problem",
        "stakes",
        "moral",
        "ending_target",
        "beat_plan",
    ],
}


FRAGMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "mood": {"type": "STRING", "enum": MOOD_LABELS},
        "text": {"type": "STRING"},
        "narrative_phase": {"type": "STRING"},
        "story_event": {"type": "STRING"},
        "display_text": {"type": "STRING"},
        "keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "image_prompt": {"type": "STRING"},
        "visual_motif": {"type": "STRING"},
        "palette": {"type": "STRING"},
        "motion": {"type": "STRING"},
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
                "required": ["role", "label", "prompt", "negative_prompt"],
            },
        },
        "state": {
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING"},
                "protagonist_status": {"type": "STRING"},
                "antagonist_status": {"type": "STRING"},
                "helper_status": {"type": "STRING"},
                "magical_object_status": {"type": "STRING"},
                "last_event": {"type": "STRING"},
                "unresolved_threads": {"type": "ARRAY", "items": {"type": "STRING"}},
                "facts_to_preserve": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": [
                "location",
                "protagonist_status",
                "antagonist_status",
                "helper_status",
                "magical_object_status",
                "last_event",
                "unresolved_threads",
                "facts_to_preserve",
            ],
        },
    },
    "required": [
        "mood",
        "text",
        "narrative_phase",
        "story_event",
        "display_text",
        "keywords",
        "image_prompt",
        "visual_motif",
        "palette",
        "motion",
        "image_assets",
        "state",
    ],
}

TEXT_REPAIR_SCHEMA = {
    "type": "OBJECT",
    "properties": {"text": {"type": "STRING"}},
    "required": ["text"],
}


def create_story_bible(
    segments: list[MusicSegment],
    settings: BardSettings,
    total_segments: int,
) -> dict[str, Any]:
    world_profile = choose_world_profile(segments)
    cues = [
        {
            "id": segment.id,
            "energy": segment.story_energy,
            "tension": segment.story_tension,
            "direction": segment.story_direction,
        }
        for segment in segments
    ]
    prompt = f"""
Design a coherent original symbolic adventure story for children aged 6-10, planned for exactly {total_segments} short parts.
Return JSON only.

Story language: {settings.story_language}.
Reading level: {settings.story_level}.
Use a clear protagonist, antagonist, helper, setting, problem, escalating attempts, climax, solution, and moral.
The protagonist, antagonist, and helper must be visually distinctive non-human characters that fit the selected
world profile: robots, machines, masks, vehicles, elemental spirits, living buildings, animated tools, signal
spirits, mechanical animals, or other non-human symbolic beings are welcome. Do not make them children, human
adults, fairies, or ordinary human-like people.
Character names must fit the selected world profile and must not default to bug-like or animal-like names.
Plan the definitive ending now so later fragments cannot wander. The antagonist needs an understandable motive.
For protagonist_visual_identity, antagonist_visual_identity, and helper_visual_identity, define one concise,
immutable English design specification: species/object type, body shape, dominant colors, distinctive markings,
clothing/accessories if any, and one recognizable silhouette feature. Future image prompts must repeat it exactly.
The magical rule must stay consistent. Beat 1 introduces the goal and problem; the final beat resolves every
important thread and shows what changed. Keep danger exciting but never graphic.
Do not default to woodland, meadow, fairy forest, insects, foxes, cats, owls, or small forest animals unless the
selected world profile explicitly requires them.

SELECTED WORLD PROFILE (strong constraint; apply to setting, cast, names, palette, props, and image concepts):
{json.dumps(world_profile, ensure_ascii=False)}

These abstract dramatic directions may shape the arc:
{json.dumps(cues, ensure_ascii=False)}
"""
    bible = _generate_json(prompt, BIBLE_SCHEMA, settings, temperature=0.65)
    bible["world_profile"] = world_profile
    return bible


def choose_world_profile(segments: list[MusicSegment]) -> dict[str, str]:
    """
    Choose a repeatable setting/style from global music descriptors.
    This is intentionally local and deterministic so story variety is stable, cheap, and testable.
    """
    descriptor = _music_descriptor_text(segments)
    lowered = descriptor.lower()
    valence = _average_number(segment.valence for segment in segments)
    arousal = _average_number(segment.arousal for segment in segments)
    tension = _average_number(segment.tension for segment in segments)

    candidates: list[str] = []
    if _contains_any(
        lowered,
        {
            "electronic",
            "mechanical",
            "synthetic",
            "industrial",
            "glitch",
            "digital",
            "machine",
            "robot",
            "techno",
            "synth",
            "metallic",
            "pulse",
        },
    ):
        candidates.extend(["cyberpunk_rooftops", "clockwork_city", "radio_tower"])
    if arousal >= 0.67 and tension >= 0.67:
        candidates.extend(["cyberpunk_rooftops", "storm_airship", "volcanic_workshop"])
    if arousal <= 0.33 and tension >= 0.67:
        candidates.extend(["underwater_ruins", "polar_observatory", "moon_archive"])
    if valence >= 0.30 and arousal >= 0.67:
        candidates.extend(["sky_market", "desert_caravan", "festival_harbor"])
    if valence <= -0.30:
        candidates.extend(["moon_archive", "underwater_ruins", "polar_observatory"])
    if not candidates:
        candidates.extend(["medieval_citadel", "clockwork_city", "radio_tower", "storm_airship"])

    unique_candidates = list(dict.fromkeys(candidates))
    digest = hashlib.sha256(descriptor.encode("utf-8")).hexdigest()
    selected_key = unique_candidates[int(digest[:12], 16) % len(unique_candidates)]
    profile = dict(WORLD_PROFILES[selected_key])
    profile["id"] = selected_key
    profile["selection_basis"] = (
        f"valence={valence:.2f}, arousal={arousal:.2f}, tension={tension:.2f}, "
        f"candidates={', '.join(unique_candidates)}"
    )
    return profile


def initial_story_state(bible: dict[str, Any]) -> dict[str, Any]:
    return {
        "location": str(bible.get("setting", "")),
        "protagonist_status": f"{bible.get('protagonist', 'The hero')} has not yet achieved the goal.",
        "antagonist_status": f"{bible.get('antagonist', 'The antagonist')} is pursuing their motive.",
        "helper_status": f"{bible.get('helper', 'The helper')} has not yet offered decisive help.",
        "magical_object_status": "No magical object has changed hands yet.",
        "last_event": "The tale has not begun.",
        "unresolved_threads": [str(bible.get("central_problem", ""))],
        "facts_to_preserve": [
            f"Goal: {bible.get('protagonist_goal', '')}",
            f"Magical rule: {bible.get('magical_rule', '')}",
            f"Ending target: {bible.get('ending_target', '')}",
        ],
    }


def generate_story_fragment_with_gemini(
    segment: MusicSegment,
    settings: BardSettings,
    *,
    fragment_index: int,
    total_segments: int,
    words_per_fragment: int,
    bible: dict[str, Any],
    state: dict[str, Any],
    previous_text: str,
    is_final: bool,
    music_timeline: list[MusicSegment] | None = None,
) -> tuple[StoryFragment, dict[str, Any]]:
    timeline = music_timeline or [segment]
    timeline_cues = [
        {
            "start_s": item.start_s,
            "end_s": item.end_s,
            "energy": item.story_energy,
            "tension": item.story_tension,
            "direction": item.story_direction,
            "event": item.suggested_event,
            "motion": item.visual_motion,
            "color": item.color_direction,
        }
        for item in timeline
    ]
    phase = narrative_phase(fragment_index, total_segments)
    beat_plan = bible.get("beat_plan", [])
    planned_beat = beat_plan[fragment_index] if fragment_index < len(beat_plan) else phase
    final_rule = (
        "This is the final part. Complete the planned ending, resolve the central problem and all important "
        "threads, and show the moral through action. Do not end on a cliffhanger."
        if is_final
        else "Advance the plot with one consequential event. Do not resolve the final conflict early."
    )
    prompt = f"""
Write part {fragment_index + 1} of {total_segments} of a coherent symbolic adventure story for children.
Return JSON only. The text must contain no more than {words_per_fragment} words. Aim for
{max(8, round(words_per_fragment * 0.82))}-{words_per_fragment} words and end with a complete sentence.
Write the story text in {settings.story_language}, at the "{settings.story_level}" reading level,
letting the dramatic tone follow only the current music-derived energy, tension, and direction.

STORY BIBLE (immutable facts):
{json.dumps(bible, ensure_ascii=False)}

CONTINUITY STATE:
{json.dumps(state, ensure_ascii=False)}

PLANNED BEAT:
{planned_beat}

TIMESTAMPED DRAMATIC DIRECTIONS INSIDE THIS PART:
{json.dumps(timeline_cues, ensure_ascii=False)}

RECENT PROSE:
{previous_text[-1800:] if previous_text else "[The tale has not begun.]"}

Rules:
- Use the same named cast, motives, magical rule, geography, and object state.
- Keep every character, name, prop, palette, and location consistent with STORY BIBLE world_profile.
- Do not drift into woodland, meadow, fairy forest, insects, foxes, cats, owls, or small forest animals unless
  STORY BIBLE world_profile explicitly asks for them.
- Make cause and effect clear. Do not repeat earlier events.
- Follow every timestamped direction in order. Let the prose move through those small emotional changes
  as connected beats inside this one scene, without naming or exposing timestamps to the audience.
- Prefer short sentences, common concrete words, and one clear action at a time. Avoid ornate descriptions,
  stacked adjectives, literary vocabulary, and long subordinate clauses unless the selected reading level requests them.
- Every sentence must be natural and grammatically complete in the selected language. Do not leave a generic
  verb such as "saw", "found", or "went" without the object or destination it requires.
- Never mention music, audio, tempo, rhythm, harmony, chords, mode, instruments, genres, or performance.
- display_text is a short summary in the selected story language; Processing displays the full text.
- keywords contains 3-6 concrete words suitable for animated typography.
- Produce exactly three image assets in this order: background, subject, symbol.
- Every image label, prompt, and negative prompt must be written in English even when the story uses another language.
- Background prompt: a widescreen environment with depth, atmospheric color, no central character, suitable
  for filling the complete screen.
- Subject prompt: repeat the relevant immutable visual identity from the bible word for word, show one full
  non-human character, centered and isolated against a plain solid background, strong clean silhouette,
  generous empty space, no cast shadow, no scenery.
- Symbol prompt: one simple object centered and isolated against a plain solid background, generous empty space.
- All prompts use an unfinished painterly children's-book style with no text.
- Keep every image gentle and suitable for ages 6-10. Antagonists may be mysterious or imposing, but never
  horror-like: no fangs, gore, predatory close-ups, demonic faces, or graphic menace.
- Depict the non-human symbolic cast from the bible without turning them into people.
- Update the compact continuity state after the event.
- {final_rule}
"""
    parsed = _generate_json(prompt, FRAGMENT_SCHEMA, settings, temperature=0.72)
    text = _clean(parsed.get("text"))
    if _word_count(text) > max(words_per_fragment + 8, round(words_per_fragment * 1.12)):
        text = _repair_story_length(
            text,
            settings,
            words_per_fragment=words_per_fragment,
            is_final=is_final,
        )
    assets = [
        ImageAsset(
            role=_clean(item.get("role")).lower() or "background",
            label=_clean(item.get("label")) or "story image",
            prompt=_clean(item.get("prompt")),
            search_query=None,
            negative_prompt=_clean(item.get("negative_prompt")),
        )
        for item in parsed.get("image_assets", [])
        if isinstance(item, dict) and _clean(item.get("prompt"))
    ][:3]
    _stabilize_image_assets(assets, bible)
    fragment = StoryFragment(
        id=segment.id,
        mood=_scene_mood(timeline, parsed.get("mood")),
        text=text,
        music_prompt=" | ".join(item.music_prompt for item in timeline),
        start_s=timeline[0].start_s,
        end_s=timeline[-1].end_s,
        image_prompt=_clean(parsed.get("image_prompt")),
        visual_motif=_clean(parsed.get("visual_motif")),
        palette=_clean(parsed.get("palette")),
        motion=_clean(parsed.get("motion")),
        narrative_phase=_clean(parsed.get("narrative_phase") or phase),
        story_event=_clean(parsed.get("story_event")),
        display_text=_clean(parsed.get("display_text")),
        keywords=_string_list(parsed.get("keywords"))[:6],
        image_assets=assets,
        mood_cues=mood_cues_from_music_segments(timeline, start_s=timeline[0].start_s, end_s=timeline[-1].end_s),
    )
    new_state = parsed.get("state") if isinstance(parsed.get("state"), dict) else state
    return fragment, new_state


def generate_story_with_gemini(
    segments: list[MusicSegment],
    settings: BardSettings,
    words_per_fragment: int,
) -> tuple[list[StoryFragment], str, dict[str, Any], dict[str, Any]]:
    if not segments:
        return [], "", {}, {}
    bible = create_story_bible(segments, settings, len(segments))
    state = initial_story_state(bible)
    fragments: list[StoryFragment] = []
    full_story = ""
    for index, segment in enumerate(segments):
        fragment, state = generate_story_fragment_with_gemini(
            segment,
            settings,
            fragment_index=index,
            total_segments=len(segments),
            words_per_fragment=words_per_fragment,
            bible=bible,
            state=state,
            previous_text=full_story,
            is_final=index == len(segments) - 1,
        )
        fragments.append(fragment)
        full_story = "\n\n".join(item.text for item in fragments)
    return fragments, full_story, bible, state


def narrative_phase(index: int, total: int) -> str:
    if total <= 1 or index == total - 1:
        return "resolution"
    progress = index / max(1, total - 1)
    if index == 0:
        return "opening and problem"
    if progress < 0.45:
        return "rising action"
    if progress < 0.75:
        return "trials and reversal"
    return "climax"


def _generate_json(
    prompt: str,
    schema: dict[str, Any],
    settings: BardSettings,
    *,
    temperature: float,
) -> dict[str, Any]:
    if not settings.gcp_project_id:
        raise RuntimeError("Set BARD_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT before using Vertex story generation.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Vertex story generation requires `pip install -e .[cloud]`.") from exc

    client = genai.Client(enterprise=True, project=settings.gcp_project_id, location=settings.gcp_location)
    response = client.models.generate_content(
        model=settings.vertex_text_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    parsed = extract_json(response.text or "{}")
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini returned an invalid JSON object.")
    return parsed


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _scene_mood(music_timeline: list[MusicSegment] | None, llm_mood: object) -> str:
    durations_by_mood = {label: 0.0 for label in MOOD_LABELS}
    for index, segment in enumerate(music_timeline or []):
        mood = _clean(segment.mood_hint).upper()
        if mood not in durations_by_mood:
            continue
        start = segment.start_s if segment.start_s is not None else float(index)
        end = segment.end_s if segment.end_s is not None else float(index + 1)
        durations_by_mood[mood] += max(0.001, float(end) - float(start))
    dominant = max(durations_by_mood, key=durations_by_mood.get) if durations_by_mood else "CALM"
    if durations_by_mood.get(dominant, 0.0) > 0:
        return dominant

    parsed_mood = _clean(llm_mood).upper()
    return parsed_mood if parsed_mood in MOOD_LABELS else "CALM"


def _music_descriptor_text(segments: list[MusicSegment]) -> str:
    parts: list[str] = []
    for segment in segments:
        parts.extend(
            [
                segment.music_prompt,
                segment.mood_hint,
                segment.tempo_description,
                segment.mode,
                segment.harmony,
                segment.dynamics,
                segment.texture,
                segment.rhythmic_character,
                segment.story_energy,
                segment.story_tension,
                segment.story_direction,
                segment.suggested_event,
                segment.visual_motion,
                segment.color_direction,
            ]
        )
        parts.extend(segment.instruments)
        parts.extend(segment.genre_candidates)
        parts.extend(segment.notable_events)
    descriptor = " | ".join(_clean(part) for part in parts if _clean(part))
    return descriptor or "mixed ambiguous music"


def _average_number(values: object) -> float:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return 0.5
    return sum(numbers) / len(numbers)


def _contains_any(text: str, needles: set[str]) -> bool:
    return any(needle in text for needle in needles)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(item) for item in value if _clean(item)]


def _word_count(value: str) -> int:
    return len(value.split())


def _repair_story_length(
    text: str,
    settings: BardSettings,
    *,
    words_per_fragment: int,
    is_final: bool,
) -> str:
    ending_rule = "Keep the definitive ending and resolution." if is_final else "Keep the scene open for continuation."
    prompt = f"""
Compress this children's symbolic adventure scene to at most {words_per_fragment} words.
Return JSON only. Preserve every consequential event, named character, cause-and-effect link, and continuity fact.
Use short, complete sentences in {settings.story_language} at the "{settings.story_level}" reading level.
Do not summarize vaguely, add new events, mention music, or end mid-sentence. {ending_rule}

SCENE:
{text}
"""
    repaired = _generate_json(prompt, TEXT_REPAIR_SCHEMA, settings, temperature=0.15)
    candidate = _clean(repaired.get("text"))
    return candidate or text


def _stabilize_image_assets(assets: list[ImageAsset], bible: dict[str, Any]) -> None:
    for asset in assets:
        if asset.role == "background":
            asset.prompt = (
                f"{asset.prompt} Widescreen environmental composition, edge-to-edge scenery, layered depth, "
                "no central character."
            )
        elif asset.role == "subject":
            identity = _matching_character_identity(asset, bible)
            asset.prompt = (
                f"{asset.prompt} Character identity reference, repeat exactly in every appearance: {identity}. "
                "Single full-body subject, plain solid background, strong clean silhouette, generous empty "
                "space, no scenery, no cast shadow."
            )
        elif asset.role == "symbol":
            asset.prompt = (
                f"{asset.prompt} One isolated object, plain solid background, generous empty space, "
                "strong clean silhouette, no scenery."
            )


def _matching_character_identity(asset: ImageAsset, bible: dict[str, Any]) -> str:
    haystack = f"{asset.label} {asset.prompt}".lower()
    for character_key, identity_key in (
        ("protagonist", "protagonist_visual_identity"),
        ("antagonist", "antagonist_visual_identity"),
        ("helper", "helper_visual_identity"),
    ):
        character = _clean(bible.get(character_key))
        name = character.split(",", 1)[0].split(" ", 1)[0].lower()
        if name and name in haystack:
            return _clean(bible.get(identity_key))
    return _clean(bible.get("protagonist_visual_identity")) or "the established non-human protagonist design"
