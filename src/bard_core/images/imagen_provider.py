from __future__ import annotations

from pathlib import Path
import re

from ..config import BardSettings
from ..contracts import ImageAsset


def generate_imagen_image(asset: ImageAsset, output_base_path: Path, settings: BardSettings) -> ImageAsset:
    if not settings.gcp_project_id:
        raise RuntimeError("Set BARD_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT before using the imagen image provider.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Imagen generation requires `pip install -e .[cloud]`.") from exc

    client = genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.image_location)
    try:
        image = _request_image(client, types, asset.prompt, settings)
    except Exception as exc:
        raise RuntimeError(
            f"Imagen generation failed for model {settings.image_model!r} in location {settings.image_location!r}. "
            "Check BARD_IMAGE_MODEL/BARD_IMAGEN_MODEL and BARD_IMAGE_LOCATION/BARD_IMAGEN_LOCATION."
        ) from exc
    if image is None:
        try:
            image = _request_image(client, types, _safe_retry_prompt(asset), settings)
        except Exception as exc:
            raise RuntimeError(
                f"Imagen safer retry failed for model {settings.image_model!r} in location {settings.image_location!r}. "
                "Check that the selected model is available in the configured GCP location."
            ) from exc
    if image is None:
        raise RuntimeError("Imagen returned no image bytes after a safer non-human retry.")

    output_path = output_base_path.with_suffix(".png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output_path))

    asset.provider = "imagen"
    asset.model = settings.image_model
    asset.status = "generated"
    asset.local_path = str(output_path.resolve())
    asset.error = None
    return asset


def _request_image(client, types, prompt: str, settings: BardSettings):
    response = client.models.generate_images(
        model=settings.image_model,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio=settings.image_aspect_ratio,
            output_mime_type="image/png",
            person_generation="DONT_ALLOW",
        ),
    )
    if not response.generated_images:
        return None
    image = response.generated_images[0].image
    return image if image.image_bytes is not None else None


def _safe_retry_prompt(asset: ImageAsset) -> str:
    label = re.sub(
        r"\b(fairy|girl|boy|child|woman|man|person|human|humanoid)\b",
        "symbolic non-human character",
        asset.label,
        flags=re.IGNORECASE,
    )
    subject = (
        "a clearly non-human symbolic character that fits the selected story world, such as a friendly robot, "
        "animated tool, signal spirit, elemental helper, living building, mask, vehicle, or mechanical guide"
        if asset.role == "subject"
        else label
    )
    return (
        "Unfinished painterly children's-book illustration with no text and no people. "
        f"Visual concept: {subject}. Depict only clearly non-human symbolic beings, environments, machines, "
        "vehicles, tools, masks, elemental spirits, living buildings, or gentle objects. "
        "Gentle and suitable for ages 6-10. No humanoid anatomy, human face, hands, clothing, violence, fangs, "
        "demonic features, horror, frightening detail, insects, woodland default, foxes, rabbits, owls, or small forest animals."
    )
