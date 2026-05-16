from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from ..config import BardSettings
from ..contracts import ImageAsset
from .http_utils import download_image_url, read_json_url


OPENVERSE_IMAGES_URL = "https://api.openverse.engineering/v1/images/"
OPENVERSE_USER_AGENT = "BARD-CPAC-2026/0.1 university-project"


def retrieve_openverse_image(asset: ImageAsset, output_base_path: Path, settings: BardSettings) -> ImageAsset:
    query = _query_for_asset(asset)
    search_url = f"{OPENVERSE_IMAGES_URL}?{urlencode({'q': query, 'page_size': 10})}"
    data = read_json_url(
        search_url,
        headers={"User-Agent": OPENVERSE_USER_AGENT},
        timeout_s=settings.image_timeout_s,
    )
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"Openverse returned no image results for query: {query}")

    last_error: Exception | None = None
    for result in results[:6]:
        for url_field in ("url", "thumbnail"):
            image_url = result.get(url_field)
            if not image_url:
                continue
            try:
                local_path, _ = download_image_url(
                    image_url,
                    output_base_path,
                    headers={"User-Agent": OPENVERSE_USER_AGENT},
                    timeout_s=settings.image_timeout_s,
                    allowed_mime_types={"image/png", "image/jpeg"},
                )
                asset.provider = "openverse"
                asset.model = "openverse-search"
                asset.status = "retrieved"
                asset.local_path = str(local_path.resolve())
                asset.remote_url = image_url
                asset.source_url = result.get("foreign_landing_url") or result.get("url")
                asset.license = result.get("license") or result.get("license_url")
                asset.creator = result.get("creator")
                asset.error = None
                return asset
            except Exception as exc:
                last_error = exc

    raise RuntimeError(f"Openverse found results but none downloaded as PNG/JPEG: {last_error}")


def _query_for_asset(asset: ImageAsset) -> str:
    label = " ".join((asset.label or "").split())
    if label:
        return label
    return " ".join((asset.prompt or asset.role or "image").split()[:8])
