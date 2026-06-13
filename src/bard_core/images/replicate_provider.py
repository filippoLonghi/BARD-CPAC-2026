from __future__ import annotations

from pathlib import Path
import time

from ..config import BardSettings
from ..contracts import ImageAsset
from .http_utils import download_image_url, post_json_url, read_json_url


REPLICATE_API_URL = "https://api.replicate.com/v1/predictions"


def generate_replicate_image(asset: ImageAsset, output_base_path: Path, settings: BardSettings) -> ImageAsset:
    if not settings.replicate_api_token:
        raise RuntimeError("Set REPLICATE_API_TOKEN or BARD_REPLICATE_API_TOKEN before using the replicate image provider.")

    headers = {
        "Authorization": f"Bearer {settings.replicate_api_token}",
        "Prefer": "wait=60",
    }
    payload = {
        "version": settings.replicate_model,
        "input": {
            "prompt": asset.prompt,
            "num_outputs": 1,
            "aspect_ratio": settings.image_aspect_ratio,
            "output_format": "png",
            "output_quality": 85,
            "num_inference_steps": 4,
            "go_fast": True,
        },
    }
    response = post_json_url(REPLICATE_API_URL, payload, headers=headers, timeout_s=settings.image_timeout_s)
    response = _wait_for_prediction(response, headers=headers, timeout_s=settings.image_timeout_s)

    output_url = _first_output_url(response.get("output"))
    if not output_url:
        raise RuntimeError(f"Replicate prediction succeeded without an image URL: {response}")

    local_path, _ = download_image_url(
        output_url,
        output_base_path,
        headers={"Authorization": f"Bearer {settings.replicate_api_token}"},
        timeout_s=settings.image_timeout_s,
        allowed_mime_types={"image/png", "image/jpeg"},
    )
    asset.provider = "replicate"
    asset.model = settings.replicate_model
    asset.status = "generated"
    asset.remote_url = output_url
    asset.local_path = str(local_path.resolve())
    asset.error = None
    return asset


def _wait_for_prediction(response: dict, *, headers: dict[str, str], timeout_s: float) -> dict:
    status = response.get("status")
    if status == "succeeded":
        return response
    if status in {"failed", "canceled"}:
        raise RuntimeError(f"Replicate prediction {status}: {response.get('error')}")

    get_url = (response.get("urls") or {}).get("get")
    if not get_url:
        raise RuntimeError(f"Replicate prediction did not include a polling URL: {response}")

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        time.sleep(1.0)
        response = read_json_url(get_url, headers=headers, timeout_s=timeout_s)
        status = response.get("status")
        if status == "succeeded":
            return response
        if status in {"failed", "canceled"}:
            raise RuntimeError(f"Replicate prediction {status}: {response.get('error')}")
    raise RuntimeError(f"Replicate prediction did not finish within {timeout_s:.0f}s.")


def _first_output_url(output: object) -> str | None:
    if isinstance(output, str) and output.startswith("http"):
        return output
    if isinstance(output, list):
        for item in output:
            found = _first_output_url(item)
            if found:
                return found
    if isinstance(output, dict):
        for item in output.values():
            found = _first_output_url(item)
            if found:
                return found
    return None
