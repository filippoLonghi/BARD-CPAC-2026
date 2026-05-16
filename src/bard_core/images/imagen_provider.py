from __future__ import annotations

from pathlib import Path

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

    client = genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.imagen_location)
    response = client.models.generate_images(
        model=settings.imagen_model,
        prompt=asset.prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio=settings.image_aspect_ratio,
            output_mime_type="image/png",
            person_generation="DONT_ALLOW",
        ),
    )
    if not response.generated_images:
        raise RuntimeError("Imagen returned no generated images. The prompt may have been filtered.")

    image = response.generated_images[0].image
    if image.image_bytes is None:
        raise RuntimeError("Imagen returned an image without inline bytes.")

    output_path = output_base_path.with_suffix(".png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output_path))

    asset.provider = "imagen"
    asset.model = settings.imagen_model
    asset.status = "generated"
    asset.local_path = str(output_path.resolve())
    asset.error = None
    return asset
