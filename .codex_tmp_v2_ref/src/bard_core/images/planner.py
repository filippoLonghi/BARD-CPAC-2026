from __future__ import annotations

import re

from ..contracts import ImageAsset, StoryFragment


VALID_IMAGE_ROLES = {"background", "subject", "symbol"}


def ensure_fragment_image_assets(fragment: StoryFragment, max_assets: int) -> list[ImageAsset]:
    """Return planned assets, preserving old single-prompt story outputs."""
    limit = max(1, max_assets)
    existing = [normalize_asset(asset) for asset in fragment.image_assets if asset.prompt.strip()]
    if existing:
        existing_roles = {asset.role for asset in existing}
        supplements = [
            asset for asset in default_assets_from_fragment(fragment) if asset.role not in existing_roles
        ]
        fragment.image_assets = (existing + supplements)[:limit]
        return fragment.image_assets

    fragment.image_assets = default_assets_from_fragment(fragment)
    return fragment.image_assets[:limit]


def normalize_asset(asset: ImageAsset) -> ImageAsset:
    role = (asset.role or "background").strip().lower()
    asset.role = role if role in VALID_IMAGE_ROLES else "background"
    asset.label = (asset.label or asset.role or "visual asset").strip()
    if not asset.search_query:
        asset.search_query = asset.label
    asset.prompt = " ".join(asset.prompt.split())
    if not asset.negative_prompt:
        asset.negative_prompt = default_negative_prompt()
    return asset


def default_negative_prompt() -> str:
    return (
        "text, letters, watermark, logo, photorealistic, extra limbs, distorted anatomy, musical instruments, "
        "horror, gore, fangs, demonic face, graphic menace, border, frame, white border, black border, margin, passepartout"
    )


def fallback_asset_from_fragment(fragment: StoryFragment) -> ImageAsset:
    motif = _label_from_fragment(fragment)
    palette = f", {fragment.palette}" if fragment.palette else ""
    prompt = (
        f"Recognizable unfinished painterly image of {motif}{palette}, inspired by this story moment: "
        f"{fragment.text[:220]}. Simple composition, soft rough edges, dark empty background, useful as a live "
        "video layer, no text."
    )
    return ImageAsset(
        role="background",
        label=motif,
        prompt=" ".join(prompt.split()),
        negative_prompt=default_negative_prompt(),
    )


def default_assets_from_fragment(fragment: StoryFragment) -> list[ImageAsset]:
    motif = _label_from_fragment(fragment)
    base_prompt = fragment.image_prompt or (
        f"An unfinished painterly children's-book scene inspired by this event: {fragment.text[:220]}."
    )
    return [
        ImageAsset(
            role="background",
            label=f"{motif} environment",
            prompt=f"{base_prompt} Environment only, no characters, no text.",
            search_query=f"{motif} landscape",
            negative_prompt=default_negative_prompt(),
        ),
        ImageAsset(
            role="subject",
            label=f"{motif} subject",
            prompt=(
                f"One recognizable non-human symbolic adventure subject from this scene: {fragment.text[:180]}. "
                "Isolated unfinished painterly children's-book style, plain solid background, no text."
            ),
            search_query=motif,
            negative_prompt=default_negative_prompt(),
        ),
        ImageAsset(
            role="symbol",
            label=f"{motif} symbol",
            prompt=(
                f"One simple magical symbol or object representing {fragment.visual_motif or fragment.text[:120]}. "
                "Isolated unfinished painterly children's-book style, plain solid background, no text."
            ),
            search_query=motif,
            negative_prompt=default_negative_prompt(),
        ),
    ]


def _label_from_fragment(fragment: StoryFragment) -> str:
    if fragment.visual_motif:
        return fragment.visual_motif.strip()

    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", fragment.text)
    stopwords = {
        "the",
        "and",
        "with",
        "into",
        "from",
        "that",
        "this",
        "while",
        "through",
        "their",
        "there",
        "then",
        "when",
        "story",
    }
    for word in words:
        if word.lower() not in stopwords:
            return word.lower()
    return "story image"
