from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
import re

from ..config import BardSettings
from ..contracts import ImageAsset
from .background_removal import postprocess_image_asset


def generate_imagen_image(asset: ImageAsset, output_base_path: Path, settings: BardSettings) -> ImageAsset:
    if not settings.gcp_project_id:
        raise RuntimeError("Set BARD_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT before using the imagen image provider.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Gemini image generation requires `pip install -e .[cloud]`.") from exc

    client = genai.Client(enterprise=True, project=settings.gcp_project_id, location=settings.image_location)
    image = _request_image(client, types, asset.prompt, settings)
    if image is None:
        image = _request_image(client, types, _safe_retry_prompt(asset), settings)
    if image is None:
        raise RuntimeError("Gemini image model returned no image bytes after a safer non-human retry.")

    output_path = output_base_path.with_suffix(".png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _save_image(image, output_path)
    output_path = postprocess_image_asset(asset, output_path, settings)

    asset.provider = "imagen"
    asset.model = settings.image_model
    asset.status = "generated"
    asset.local_path = str(output_path.resolve())
    asset.error = None
    return asset


def _save_image(image, output_path: Path) -> None:
    try:
        image.save(output_path, format="PNG")
    except TypeError:
        image.save(str(output_path))


def _request_image(client, types, prompt: str, settings: BardSettings):
    response = client.models.generate_content(
        model=settings.image_model,
        contents=_image_prompt(prompt),
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=settings.image_aspect_ratio),
        ),
    )
    return _first_inline_image(response)


def _first_inline_image(response):
    for part in _response_parts(response):
        inline_data = getattr(part, "inline_data", None)
        if inline_data is None:
            continue
        if hasattr(part, "as_image"):
            image = part.as_image()
            if image is not None:
                return image
        data = getattr(inline_data, "data", None)
        if data is None:
            continue
        image_bytes = base64.b64decode(data) if isinstance(data, str) else bytes(data)
        from PIL import Image

        return Image.open(BytesIO(image_bytes)).convert("RGBA")
    return None


def _response_parts(response) -> list[object]:
    direct_parts = getattr(response, "parts", None)
    if direct_parts:
        return list(direct_parts)
    parts: list[object] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        parts.extend(getattr(content, "parts", []) or [])
    return parts


def _image_prompt(prompt: str) -> str:
    return (
        f"{prompt}\n\n"
        "Generate one gentle image for a children's symbolic adventure story. No text, captions, logos, "
        "watermarks, frightening gore, realistic injury, or human people. Use a clean isolated composition "
        "when the prompt asks for a subject or symbol."
    )


def _safe_retry_prompt(asset: ImageAsset) -> str:
    label = re.sub(
        r"\b(fairy|girl|boy|child|woman|man|person|human|humanoid)\b",
        "symbolic non-human character",
        asset.label,
        flags=re.IGNORECASE,
    )
    subject = (
        "a clearly non-human symbolic character that fits the planned story world, such as a friendly robot, "
        "animated tool, mask, vehicle, signal spirit, elemental helper, or living building"
        if asset.role == "subject"
        else label
    )
    return (
        "Unfinished painterly children's-book illustration with no text and no people. "
        f"Visual concept: {subject}. Depict only clearly non-human symbolic beings, environments, machines, "
        "vehicles, tools, masks, elemental spirits, or magical objects. "
        "Gentle and suitable for ages 6-10. No humanoid anatomy, human face, hands, clothing, violence, fangs, "
        "demonic features, horror, frightening detail, woodland default, insects, foxes, cats, owls, or small forest animals."
    )
