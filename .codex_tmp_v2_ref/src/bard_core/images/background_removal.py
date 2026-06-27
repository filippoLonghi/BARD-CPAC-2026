from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

from ..contracts import ImageAsset

if TYPE_CHECKING:
    from ..config import BardSettings


CUTOUT_ROLES = {"subject", "symbol"}


def remove_background_to_alpha(input_path: Path, output_path: Path) -> Path:
    """
    Load image, remove background, save transparent PNG.
    Preserve alpha if already present.
    Return output_path.
    """
    if _has_alpha_channel(input_path):
        image = _open_rgba(input_path)
        return _save_rgba(image, output_path)

    image = _open_rgba(input_path)

    try:
        from rembg import remove
    except ImportError:
        return _save_rgba(_edge_flood_fill_to_alpha(image), output_path)

    cutout = remove(image).convert("RGBA")
    return _save_rgba(cutout, output_path)


def postprocess_image_asset(asset: ImageAsset, image_path: Path, settings: "BardSettings") -> Path:
    if not settings.remove_image_background:
        return image_path

    output_path = image_path.with_suffix(".png")
    role = (asset.role or "").strip().lower()
    if settings.background_removal_provider != "rembg":
        return _save_rgba(_open_rgba(image_path), output_path)
    if role in CUTOUT_ROLES:
        return remove_background_to_alpha(image_path, output_path)
    return _save_rgba(_open_rgba(image_path), output_path)


def _open_rgba(path: Path):
    from PIL import Image

    with Image.open(path) as image:
        return image.convert("RGBA")


def _save_rgba(image, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    return output_path


def _has_alpha_channel(path: Path) -> bool:
    from PIL import Image

    with Image.open(path) as image:
        return image.mode in {"RGBA", "LA"} or "transparency" in image.info


def _edge_flood_fill_to_alpha(image):
    """Small offline fallback for simple solid/near-solid edge backgrounds."""
    pixels = image.load()
    width, height = image.size
    visited = set()
    queue: deque[tuple[int, int]] = deque()

    edge_samples: list[tuple[int, int, int]] = []
    for x in range(width):
        edge_samples.append(pixels[x, 0][:3])
        edge_samples.append(pixels[x, height - 1][:3])
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        edge_samples.append(pixels[0, y][:3])
        edge_samples.append(pixels[width - 1, y][:3])
        queue.append((0, y))
        queue.append((width - 1, y))

    bg = tuple(round(sum(channel) / len(edge_samples)) for channel in zip(*edge_samples))
    tolerance = 42
    while queue:
        x, y = queue.popleft()
        if (x, y) in visited or x < 0 or y < 0 or x >= width or y >= height:
            continue
        visited.add((x, y))
        rgb = pixels[x, y][:3]
        if _color_distance(rgb, bg) > tolerance:
            continue
        pixels[x, y] = (rgb[0], rgb[1], rgb[2], 0)
        queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return image


def _color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return sum((left[index] - right[index]) ** 2 for index in range(3)) ** 0.5
