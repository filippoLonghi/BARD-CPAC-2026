from __future__ import annotations

from pathlib import Path
import re

from ..config import BardSettings
from ..contracts import ImageAsset, StoryFragment
from .imagen_provider import generate_imagen_image
from .openverse_provider import retrieve_openverse_image
from .planner import ensure_fragment_image_assets
from .replicate_provider import generate_replicate_image


SUPPORTED_IMAGE_PROVIDERS = {"replicate", "imagen", "openverse"}


def generate_images_for_fragments(
    fragments: list[StoryFragment],
    settings: BardSettings,
    output_dir: Path,
    *,
    provider: str,
    max_assets: int,
    print_estimate: bool = True,
) -> dict[str, object]:
    provider = provider.lower().strip()
    if provider not in SUPPORTED_IMAGE_PROVIDERS:
        raise ValueError(f"Unsupported image provider: {provider}")

    output_dir.mkdir(parents=True, exist_ok=True)
    planned_count = 0
    for fragment in fragments:
        planned_count += len(ensure_fragment_image_assets(fragment, max_assets))

    estimate = estimate_image_cost(provider, planned_count)
    if print_estimate:
        print(estimate["message"])

    generated = 0
    failed = 0
    for fragment in fragments:
        for layer_index, asset in enumerate(fragment.image_assets[:max_assets]):
            asset.provider = provider
            asset.model = model_for_provider(provider, settings)
            output_base_path = output_dir / _asset_filename(fragment.id, layer_index, asset)
            try:
                _generate_one(provider, asset, output_base_path, settings)
                generated += 1
            except Exception as exc:
                asset.status = "failed"
                asset.error = str(exc)
                failed += 1

    return {
        "image_provider": provider,
        "planned_image_assets": planned_count,
        "generated_image_assets": generated,
        "failed_image_assets": failed,
        "estimated_cost_usd": estimate["estimated_cost_usd"],
        "estimated_cost_message": estimate["message"],
    }


def estimate_image_cost(provider: str, image_count: int) -> dict[str, object]:
    provider = provider.lower().strip()
    if provider == "replicate":
        cost = image_count * 0.003
        return {
            "estimated_cost_usd": round(cost, 4),
            "message": f"Image estimate: {image_count} Replicate FLUX image(s) at about $3/1000 images ~= ${cost:.4f}.",
        }
    if provider == "imagen":
        cost = image_count * 0.02
        return {
            "estimated_cost_usd": round(cost, 4),
            "message": f"Image estimate: {image_count} Imagen 4 Fast image(s) at about $0.02/image ~= ${cost:.4f}.",
        }
    if provider == "openverse":
        return {
            "estimated_cost_usd": 0.0,
            "message": f"Image estimate: {image_count} Openverse retrieval(s), expected API cost $0.",
        }
    return {
        "estimated_cost_usd": None,
        "message": f"Image estimate unavailable for provider: {provider}",
    }


def model_for_provider(provider: str, settings: BardSettings) -> str:
    if provider == "replicate":
        return settings.replicate_model
    if provider == "imagen":
        return settings.imagen_model
    if provider == "openverse":
        return "openverse-search"
    return provider


def _generate_one(provider: str, asset: ImageAsset, output_base_path: Path, settings: BardSettings) -> ImageAsset:
    if provider == "replicate":
        return generate_replicate_image(asset, output_base_path, settings)
    if provider == "imagen":
        return generate_imagen_image(asset, output_base_path, settings)
    if provider == "openverse":
        return retrieve_openverse_image(asset, output_base_path, settings)
    raise ValueError(f"Unsupported image provider: {provider}")


def _asset_filename(segment_id: int, layer_index: int, asset: ImageAsset) -> str:
    label = _slug(asset.label or asset.role or "asset")
    role = _slug(asset.role or "layer")
    return f"segment_{segment_id:03d}_{layer_index:02d}_{role}_{label}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug[:40] or "asset"
