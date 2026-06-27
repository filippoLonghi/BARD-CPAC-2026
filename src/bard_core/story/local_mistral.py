from __future__ import annotations

import random
import sys

from ..config import BardSettings
from ..contracts import MusicSegment, StoryFragment, normalize_mood_label


def generate_story_with_local_mistral(
    segments: list[MusicSegment],
    settings: BardSettings,
    words_per_fragment: int,
    temperature: float = 0.65,
    top_p: float = 0.9,
    seed: int | None = None,
) -> tuple[list[StoryFragment], str]:
    root = str(settings.root_dir)
    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        import torch
        from bard_core.legacy.story import story_from_description as legacy_story
    except ImportError as exc:
        raise RuntimeError(
            "Local Mistral story generation requires the local AI dependencies. "
            "Install with `pip install -e .[local-ai]`, or set BARD_STORY_PROVIDER=vertex."
        ) from exc

    if seed is not None:
        random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    model, tokenizer = legacy_story.load_model(settings.local_story_model, use_4bit=settings.use_4bit)
    base_max_new_tokens = legacy_story.estimate_max_new_tokens(words_per_fragment)
    fragments: list[StoryFragment] = []
    story_parts: list[str] = []
    prev_text = ""
    facts = ""

    for idx, seg in enumerate(segments):
        is_last = idx == len(segments) - 1
        prompt = (
            legacy_story.build_prompt_first(seg.music_prompt, words_per_fragment)
            if idx == 0
            else legacy_story.build_prompt_next(prev_text, facts, seg.music_prompt, words_per_fragment, is_last)
        )
        raw = legacy_story.generate_once(
            model=model,
            tokenizer=tokenizer,
            prompt=prompt,
            max_new_tokens=base_max_new_tokens + (60 if idx == 0 else 0) + (40 if is_last else 0),
            temperature=temperature,
            top_p=top_p,
        )
        mood, text, new_facts = legacy_story.parse_block(raw)
        if idx == 0 and new_facts.strip():
            facts = new_facts
        text = " ".join(legacy_story.truncate_to_words(text, words_per_fragment).split())
        prev_text = text
        fragments.append(
            StoryFragment(
                id=seg.id,
                mood=normalize_mood_label(mood),
                text=text,
                music_prompt=seg.music_prompt,
                start_s=seg.start_s,
                end_s=seg.end_s,
            )
        )
        story_parts.append(text)

    full_story = "\n\n".join(story_parts).strip()
    return fragments, full_story
