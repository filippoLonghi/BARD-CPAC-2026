from __future__ import annotations

import json
import random
from typing import Any

from ..config import BardSettings
from ..contracts import ImageAsset, MOOD_LABELS, MusicSegment, StoryFragment
from ..utils import extract_json


# ---------------------------------------------------------------------------
# JSON schemas
# ---------------------------------------------------------------------------

BIBLE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title":                        {"type": "STRING"},
        "protagonist":                  {"type": "STRING"},
        "protagonist_trait":            {"type": "STRING"},
        "protagonist_flaw":             {"type": "STRING"},
        "protagonist_goal":             {"type": "STRING"},
        "protagonist_visual_identity":  {"type": "STRING"},
        "antagonist":                   {"type": "STRING"},
        "antagonist_motive":            {"type": "STRING"},
        "antagonist_visual_identity":   {"type": "STRING"},
        "helper":                       {"type": "STRING"},
        "helper_visual_identity":       {"type": "STRING"},
        "setting":                      {"type": "STRING"},
        "magical_rule":                 {"type": "STRING"},
        "central_problem":              {"type": "STRING"},
        "stakes":                       {"type": "STRING"},
        "moral":                        {"type": "STRING"},
        "ending_target":                {"type": "STRING"},
        "beat_plan":                    {"type": "ARRAY", "items": {"type": "STRING"}},
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
        "mood":             {"type": "STRING", "enum": MOOD_LABELS},
        "text":             {"type": "STRING"},
        "narrative_phase":  {"type": "STRING"},
        "story_event":      {"type": "STRING"},
        "display_text":     {"type": "STRING"},
        "keywords":         {"type": "ARRAY", "items": {"type": "STRING"}},
        "image_prompt":     {"type": "STRING"},
        "visual_motif":     {"type": "STRING"},
        "palette":          {"type": "STRING"},
        "motion":           {"type": "STRING"},
        "image_assets": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "role":             {"type": "STRING", "enum": ["background", "subject", "symbol"]},
                    "label":            {"type": "STRING"},
                    "prompt":           {"type": "STRING"},
                    "negative_prompt":  {"type": "STRING"},
                },
                "required": ["role", "label", "prompt", "negative_prompt"],
            },
        },
        "state": {
            "type": "OBJECT",
            "properties": {
                "location":               {"type": "STRING"},
                "protagonist_status":     {"type": "STRING"},
                "antagonist_status":      {"type": "STRING"},
                "helper_status":          {"type": "STRING"},
                "magical_object_status":  {"type": "STRING"},
                "last_event":             {"type": "STRING"},
                "unresolved_threads":     {"type": "ARRAY", "items": {"type": "STRING"}},
                "facts_to_preserve":      {"type": "ARRAY", "items": {"type": "STRING"}},
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


# ---------------------------------------------------------------------------
# Narrative seeds — sorteggiati per ogni run per variare la struttura del plot
# ---------------------------------------------------------------------------

_NARRATIVE_SEEDS: list[str] = [
    "The protagonist's greatest flaw is also their greatest strength — let this tension drive the whole arc.",
    "The antagonist genuinely believes they are in the right; their motive should be understandable by the end.",
    "The magical rule of this world must be broken or reinterpreted to solve the final problem.",
    "The helper knows the solution from the beginning but can only reveal it when the protagonist is ready.",
    "The protagonist fails at their first two attempts and only succeeds by changing their approach entirely.",
    "Two characters who start as strangers must cooperate to overcome the antagonist.",
    "The setting is not neutral — the location itself shifts or creates obstacles at a key moment.",
    "The story's moral reveals itself through the antagonist's fate, not just the protagonist's success.",
    "The final solution requires the protagonist to give up something they value to gain what they truly need.",
    "The key to the climax is hidden in plain sight in the very first scene.",
    "Every main character wants the same thing for a different reason; this creates both conflict and resolution.",
    "The protagonist must choose between two goods, not between good and evil.",
    "The antagonist's vulnerability is the mirror image of the protagonist's flaw.",
    "The story ends with the world changed in a small but permanent way, not just the characters.",
    "A detail that seems unimportant in the opening turns out to be the key to the resolution.",
    "The story has no antagonist — the obstacle is a misunderstanding between two characters who both want the right thing.",
    "The protagonist achieves their goal in the first half, then discovers the goal was not what they truly needed.",
    "The protagonist solves the problem not through courage or cleverness, but through patience and stillness.",
    "The story is about a very small event — not a great quest — that turns out to matter enormously.",
    "The protagonist fails completely and the resolution comes from an unexpected source they had ignored.",
]


# ---------------------------------------------------------------------------
# Vincoli di mondo derivati dall'audio — versione compatta
# ---------------------------------------------------------------------------

def _world_constraints_from_segments(segments: list[MusicSegment]) -> str:
    """Deriva vincoli narrativi di mondo e protagonista dall'arco musicale.

    Usa i valori numerici (provider Gemini) quando disponibili.
    Ricade su story_energy/story_tension come proxy (provider CLAP).
    Versione compatta: produce 3-4 righe per non saturare il contesto della bible.
    """
    arousals = [s.arousal for s in segments if s.arousal is not None]
    tensions  = [s.tension  for s in segments if s.tension  is not None]
    valences  = [s.valence  for s in segments if s.valence  is not None]

    # --- arousal ---
    if not arousals:
        counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        for s in segments:
            e = (s.story_energy or "").lower()
            if any(w in e for w in ("high", "urgent", "powerful", "burst", "racing", "force")):
                counts["high"] += 1
            elif any(w in e for w in ("low", "quiet", "gentle", "drift", "hushed", "subdued")):
                counts["low"] += 1
            else:
                counts["medium"] += 1
        dominant = max(counts, key=counts.get)
        avg_arousal = 0.8 if dominant == "high" else (0.2 if dominant == "low" else 0.5)
    else:
        avg_arousal = sum(arousals) / len(arousals)

    # --- tension ---
    if not tensions:
        tcounts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        for s in segments:
            t = (s.story_tension or "").lower()
            if any(w in t for w in ("high", "edge", "pressure", "breaking", "decisive", "wound")):
                tcounts["high"] += 1
            elif any(w in t for w in ("low", "ease", "calm", "clear", "free", "open")):
                tcounts["low"] += 1
            else:
                tcounts["medium"] += 1
        dominant_t = max(tcounts, key=tcounts.get)
        avg_tension = 0.8 if dominant_t == "high" else (0.2 if dominant_t == "low" else 0.5)
        tension_arc = "stable"
    else:
        avg_tension = sum(tensions) / len(tensions)
        tension_arc = (
            "rising"  if tensions[-1] - tensions[0] >= 0.20 else
            "falling" if tensions[0] - tensions[-1] >= 0.20 else
            "stable"
        )

    avg_valence = sum(valences) / len(valences) if valences else 0.0

    # --- scala (arousal) ---
    scale = (
        "vast and in constant motion" if avg_arousal >= 0.67 else
        "very small and enclosed"     if avg_arousal <= 0.33 else
        "moderate with hidden depths"
    )

    # --- pericolo (tension + arc) ---
    if avg_tension >= 0.67:
        danger = (
            "rising threat that must be faced directly" if tension_arc == "rising"
            else "constant pressure from an unstoppable force"
        )
    elif avg_tension <= 0.33:
        danger = "subtle internal problem that slowly becomes impossible to ignore"
    else:
        danger = (
            "unstable balance tipping toward danger" if tension_arc == "rising"
            else "uneasy equilibrium that could break either way"
        )

    # --- luce (valence) ---
    light = (
        "warm and bright"              if avg_valence >= 0.4  else
        "mostly warm"                  if avg_valence >= 0.15 else
        "dark with one point of light" if avg_valence <= -0.4 else
        "muted and cool"               if avg_valence <= -0.15 else
        "ambiguous, neither bright nor dark"
    )

    # --- protagonista (combinazione di tutti i valori) ---
    if avg_tension >= 0.6 and avg_valence < 0:
        protagonist = "something displaced or lost that must find its way back before something is permanently lost"
    elif avg_tension <= 0.3 and avg_valence >= 0.2:
        protagonist = "something very small that contains far more than it appears to hold"
    elif avg_arousal >= 0.7:
        protagonist = "something that cannot stop moving and must travel far before the problem resolves"
    elif avg_arousal <= 0.3:
        protagonist = "something ancient and patient that has waited a long time for this moment"
    elif tension_arc == "rising":
        protagonist = "something fragile that must become resilient without losing what makes it itself"
    else:
        protagonist = "something with a hidden quality that even it does not yet know it possesses"

    return (
        f"World: {scale}, {light}, with {danger}. "
        f"Give it one specific physical property that makes it unlike a forest, ocean, sky, cave, or generic kingdom. "
        f"Protagonist: {protagonist}. "
        f"Not a mammal, bird, reptile, or humanoid. Must belong to this world and could not exist elsewhere."
    )


# ---------------------------------------------------------------------------
# Bible
# ---------------------------------------------------------------------------

def _arc_summary_for_bible(segments: list[MusicSegment]) -> str:
    """Produce un riassunto compatto dell'arco per il prompt della bible.

    Non usa le stringhe lunghe dei pool — serve solo l'andamento globale,
    non i dettagli per-segmento che verrebbero trasmessi ai frammenti.
    """
    n = len(segments)

    # energia media (da valori numerici o da etichette)
    arousals = [s.arousal for s in segments if s.arousal is not None]
    if arousals:
        avg = sum(arousals) / len(arousals)
        energy = "high" if avg >= 0.67 else "low" if avg <= 0.33 else "medium"
    else:
        counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        for s in segments:
            e = (s.story_energy or "").lower()
            if any(w in e for w in ("high", "urgent", "powerful", "burst", "racing")):
                counts["high"] += 1
            elif any(w in e for w in ("low", "quiet", "gentle", "drift", "hushed")):
                counts["low"] += 1
            else:
                counts["medium"] += 1
        energy = max(counts, key=counts.get)

    # arco della tensione
    tensions = [s.tension for s in segments if s.tension is not None]
    if len(tensions) >= 2:
        delta = tensions[-1] - tensions[0]
        arc = "rising" if delta >= 0.2 else "falling" if delta <= -0.2 else "stable"
        tension_level = "high" if sum(tensions) / len(tensions) >= 0.6 else \
                        "low"  if sum(tensions) / len(tensions) <= 0.35 else "medium"
    else:
        arc = "stable"
        tension_level = "medium"

    # valenza globale
    valences = [s.valence for s in segments if s.valence is not None]
    if valences:
        avg_v = sum(valences) / len(valences)
        tone = "predominantly bright and positive" if avg_v >= 0.3 else \
               "predominantly dark and tense"      if avg_v <= -0.3 else \
               "mixed, shifting between light and shadow"
    else:
        tone = "mixed, shifting between light and shadow"

    return (
        f"{n} parts total. Overall energy: {energy}. "
        f"Tension: {tension_level}, arc {arc} across the performance. "
        f"Emotional tone: {tone}."
    )

def create_story_bible(
    segments: list[MusicSegment],
    settings: BardSettings,
    total_segments: int,
) -> dict[str, Any]:
    # FIX: la bible riceve un riassunto compatto dell'arco invece del JSON
    # per-segmento con le stringhe lunghe dei pool — queste saturavano il payload
    # e causavano RemoteProtocolError. I dettagli per-segmento vengono inviati
    # a ciascun frammento separatamente, dove sono effettivamente necessari.
    arc_summary       = _arc_summary_for_bible(segments)
    narrative_seed    = random.choice(_NARRATIVE_SEEDS)
    world_constraints = _world_constraints_from_segments(segments)

    prompt = f"""
Design a coherent original fairy tale for children aged 6-10, planned for exactly {total_segments} short parts.
Return JSON only.

MANDATORY WORLD AND PROTAGONIST (derived from the music — constraints, not suggestions):
{world_constraints}

Narrative seed (shape your structural choices without stating it literally):
"{narrative_seed}"

Story language: {settings.story_language}. Reading level: {settings.story_level}.
Use a clear protagonist, antagonist, helper, setting, problem, escalating attempts, climax, solution, and moral.
Characters must belong to the mandatory world above and be visually distinctive.
Plan the definitive ending now. The antagonist needs an understandable motive.
For protagonist_visual_identity, antagonist_visual_identity, and helper_visual_identity: one concise immutable
English design spec — species/object type, body shape, dominant colors, distinctive markings, silhouette feature.
Future image prompts must repeat this spec exactly.
Beat_plan: one concrete irreversible event per part, not just a direction. Final beat resolves everything.

Forbidden defaults:
- Forest, woods, or trees as primary setting.
- Fox, rabbit, bear, deer, owl, or common woodland animal as protagonist or antagonist.
- Witch, wizard, or generic evil sorcerer as antagonist.
- Quest to retrieve a stolen object as the sole plot.
- Moral about friendship or courage stated explicitly at the end.
- Any setting or character that belongs to a standard European folk tale.

Dramatic arc of the music this story will accompany:
{arc_summary}
"""
    return _generate_json(prompt, BIBLE_SCHEMA, settings, temperature=0.85)

# ---------------------------------------------------------------------------
# Stato iniziale
# ---------------------------------------------------------------------------

def initial_story_state(bible: dict[str, Any]) -> dict[str, Any]:
    return {
        "location":              str(bible.get("setting", "")),
        "protagonist_status":    f"{bible.get('protagonist', 'The hero')} has not yet achieved the goal.",
        "antagonist_status":     f"{bible.get('antagonist', 'The antagonist')} is pursuing their motive.",
        "helper_status":         f"{bible.get('helper', 'The helper')} has not yet offered decisive help.",
        "magical_object_status": "No magical object has changed hands yet.",
        "last_event":            "The tale has not begun.",
        "unresolved_threads":    [str(bible.get("central_problem", ""))],
        "facts_to_preserve": [
            f"Goal: {bible.get('protagonist_goal', '')}",
            f"Magical rule: {bible.get('magical_rule', '')}",
            f"Ending target: {bible.get('ending_target', '')}",
        ],
    }


# ---------------------------------------------------------------------------
# Generazione frammento
# ---------------------------------------------------------------------------

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

    # Cue con mood_hint incluso — essenziale per variare l'atmosfera Processing
    timeline_cues = [
        {
            "start_s":        item.start_s,
            "end_s":          item.end_s,
            "mood":           item.mood_hint,
            "energy":         item.story_energy,
            "tension":        item.story_tension,
            "direction":      item.story_direction,
            "suggested_event": item.suggested_event,
            "motion":         item.visual_motion,
            "color":          item.color_direction,
        }
        for item in timeline
    ]

    phase      = narrative_phase(fragment_index, total_segments)
    beat_plan  = bible.get("beat_plan", [])
    planned_beat = beat_plan[fragment_index] if fragment_index < len(beat_plan) else phase

    final_rule = (
        "This is the final part. Complete the planned ending, resolve the central problem and all important "
        "threads, and show the moral through action. Do not end on a cliffhanger."
        if is_final
        else "Advance the plot with one consequential event. Do not resolve the final conflict early."
    )

    # Riassunto strutturato degli eventi già accaduti — mantiene continuità
    # anche quando previous_text è troncato e le scene iniziali sono sparite dalla finestra
    events_lines: list[str] = []
    last_event = state.get("last_event", "")
    if last_event and last_event not in ("The tale has not begun.", ""):
        events_lines.append(f"- Last event: {last_event}")
    unresolved = state.get("unresolved_threads", [])
    if unresolved:
        events_lines.append(f"- Open threads: {'; '.join(str(t) for t in unresolved)}")
    preserve = state.get("facts_to_preserve", [])
    if preserve:
        events_lines.append(f"- Facts to preserve: {'; '.join(str(f) for f in preserve)}")
    events_summary = "\n".join(events_lines) if events_lines else "[The tale has not begun.]"

    # Prosa recente ridotta a 900 char — il riassunto strutturato sopra
    # garantisce continuità anche per le scene che escono dalla finestra
    recent_prose = previous_text[-900:] if previous_text else ""

    prompt = f"""
Write part {fragment_index + 1} of {total_segments} of a coherent children's fairy tale.
Return JSON only. The text must contain no more than {words_per_fragment} words. Aim for
{max(8, round(words_per_fragment * 0.82))}-{words_per_fragment} words and end with a complete sentence.
Write the story text in {settings.story_language}, at the "{settings.story_level}" reading level,
letting the dramatic tone follow the current music-derived energy, tension, and direction.

STORY BIBLE (immutable facts):
{json.dumps(bible, ensure_ascii=False)}

CONTINUITY STATE:
{json.dumps(state, ensure_ascii=False)}

PLANNED BEAT:
{planned_beat}

TIMESTAMPED DRAMATIC DIRECTIONS INSIDE THIS PART:
{json.dumps(timeline_cues, ensure_ascii=False)}

WHAT HAS ALREADY HAPPENED (do not repeat these events):
{events_summary}

RECENT PROSE (style reference, last scene only):
{recent_prose if recent_prose else "[The tale has not begun.]"}

Rules:
- Use the same named cast, motives, magical rule, geography, and object state from the bible.
- Make cause and effect clear. Do not repeat earlier events.
- Follow every timestamped direction in order as connected emotional beats inside this scene,
  without naming or exposing timestamps to the audience.
- Prefer short sentences, common concrete words, and one clear action at a time. Avoid ornate
  descriptions, stacked adjectives, and long subordinate clauses unless the reading level requests them.
- Every sentence must be grammatically complete. Do not leave a verb without its object or destination.
- Never mention music, audio, tempo, rhythm, harmony, chords, mode, instruments, genres, or performance.
- display_text is a short summary in the story language for on-screen display.
- keywords: 3-6 concrete words suitable for animated typography.
- Produce exactly three image assets in order: background, subject, symbol.
- Every image label, prompt, and negative_prompt must be written in English even when the story uses another language.
- Background prompt: widescreen environment, depth, atmospheric color, no central character, full-screen fill.
- Subject prompt: repeat the relevant immutable visual identity from the bible word for word; one full
  non-human character, centered on pure black background, strong clean silhouette, generous empty space,
  no cast shadow, no scenery.
- Symbol prompt: one simple isolated object on pure black background, generous empty space.
- All prompts: unfinished painterly children's-book style, no text.
- Keep every image gentle and suitable for ages 6-10. Antagonists may be imposing but never horror-like:
  no fangs, gore, demonic faces, or graphic menace.
- Update the compact continuity state after the event.
- {final_rule}
"""
    # FIX: era 0.72 — alzato a 0.80 per più varietà nella prosa tra run diverse
    parsed = _generate_json(prompt, FRAGMENT_SCHEMA, settings, temperature=0.80)

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
        mood=_clean(parsed.get("mood")).upper(),
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
    )

    new_state = parsed.get("state") if isinstance(parsed.get("state"), dict) else state
    return fragment, new_state


# ---------------------------------------------------------------------------
# Entry point completo (usato da pipeline_sequential quando non è streaming)
# ---------------------------------------------------------------------------

def generate_story_with_gemini(
    segments: list[MusicSegment],
    settings: BardSettings,
    words_per_fragment: int,
) -> tuple[list[StoryFragment], str, dict[str, Any], dict[str, Any]]:
    if not segments:
        return [], "", {}, {}
    bible    = create_story_bible(segments, settings, len(segments))
    state    = initial_story_state(bible)
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


# ---------------------------------------------------------------------------
# Fase narrativa
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Utility interne
# ---------------------------------------------------------------------------

def _generate_json(
    prompt: str,
    schema: dict[str, Any],
    settings: BardSettings,
    *,
    temperature: float,
) -> dict[str, Any]:
    if not settings.gcp_project_id:
        raise RuntimeError(
            "Set BARD_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT before using Vertex story generation."
        )
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Vertex story generation requires `pip install -e .[cloud]`.") from exc

    client = genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
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
    ending_rule = (
        "Keep the definitive ending and resolution."
        if is_final
        else "Keep the scene open for continuation."
    )
    prompt = f"""
Compress this children's fairy-tale scene to at most {words_per_fragment} words.
Return JSON only. Preserve every consequential event, named character, cause-and-effect link, and continuity fact.
Use short, complete sentences in {settings.story_language} at the "{settings.story_level}" reading level.
Do not summarize vaguely, add new events, mention music, or end mid-sentence. {ending_rule}

SCENE:
{text}
"""
    repaired  = _generate_json(prompt, TEXT_REPAIR_SCHEMA, settings, temperature=0.15)
    candidate = _clean(repaired.get("text"))
    return candidate or text


def _stabilize_image_assets(assets: list[ImageAsset], bible: dict[str, Any]) -> None:
    for asset in assets:
        if asset.role == "background":
            asset.prompt = (
                f"{asset.prompt} Widescreen environmental composition, edge-to-edge scenery, "
                "layered depth, no central character."
            )
        elif asset.role == "subject":
            identity = _matching_character_identity(asset, bible)
            asset.prompt = (
                f"{asset.prompt} Character identity reference, repeat exactly in every appearance: {identity}. "
                "Single full-body subject, pure black background, strong clean silhouette, "
                "generous empty black space, no scenery, no cast shadow."
            )
        elif asset.role == "symbol":
            asset.prompt = (
                f"{asset.prompt} One isolated object, pure black background, "
                "generous empty black space, strong clean silhouette, no scenery."
            )


def _matching_character_identity(asset: ImageAsset, bible: dict[str, Any]) -> str:
    haystack = f"{asset.label} {asset.prompt}".lower()
    for character_key, identity_key in (
        ("protagonist",  "protagonist_visual_identity"),
        ("antagonist",   "antagonist_visual_identity"),
        ("helper",       "helper_visual_identity"),
    ):
        character = _clean(bible.get(character_key))
        name = character.split(",", 1)[0].split(" ", 1)[0].lower()
        if name and name in haystack:
            return _clean(bible.get(identity_key))
    return _clean(bible.get("protagonist_visual_identity")) or "the established non-human protagonist design"