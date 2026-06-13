from __future__ import annotations

import re

from ..contracts import ImageAsset, StoryFragment


VALID_IMAGE_ROLES = {"background", "subject", "symbol"}


def ensure_fragment_image_assets(fragment: StoryFragment, max_assets: int) -> list[ImageAsset]:
    """Return planned assets, preserving old single-prompt story outputs."""
    limit = max(1, max_assets)
    existing = [normalize_asset(asset) for asset in fragment.image_assets if asset.prompt.strip()]
    if existing:
        fragment.image_assets = existing[:limit]
        return fragment.image_assets

    if fragment.image_prompt:
        fragment.image_assets = [
            ImageAsset(
                role="background",
                label=_label_from_fragment(fragment),
                prompt=fragment.image_prompt,
                negative_prompt=default_negative_prompt(),
            )
        ][:limit]
        return fragment.image_assets

    fragment.image_assets = [fallback_asset_from_fragment(fragment)]
    return fragment.image_assets[:limit]


def normalize_asset(asset: ImageAsset) -> ImageAsset:
    role = (asset.role or "background").strip().lower()
    asset.role = role if role in VALID_IMAGE_ROLES else "background"
    asset.label = (asset.label or asset.role or "visual asset").strip()
    asset.prompt = " ".join(asset.prompt.split())
    if not asset.negative_prompt:
        asset.negative_prompt = default_negative_prompt()
    return asset


def default_negative_prompt() -> str:
    return "text, letters, watermark, logo, photorealistic, extra limbs, distorted anatomy, musical instruments"


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
