from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import urlencode

from ..config import BardSettings
from ..contracts import ImageAsset
from .http_utils import download_image_url, read_json_url


OPENVERSE_IMAGES_URL = "https://api.openverse.engineering/v1/images/"
OPENVERSE_USER_AGENT = "BARD-CPAC-2026/0.1 university-project"


def retrieve_openverse_image(asset: ImageAsset, output_base_path: Path, settings: BardSettings) -> ImageAsset:
    query = ""
    results = []
    attempted_queries: list[str] = []
    for candidate in _query_candidates(asset):
        query = candidate
        attempted_queries.append(query)
        search_url = f"{OPENVERSE_IMAGES_URL}?{urlencode({'q': query, 'page_size': 10})}"
        data = read_json_url(
            search_url,
            headers={"User-Agent": OPENVERSE_USER_AGENT},
            timeout_s=settings.image_timeout_s,
        )
        results = data.get("results") or []
        if results:
            break
    if not results:
        raise RuntimeError(f"Openverse returned no image results for queries: {attempted_queries}")

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
    if asset.search_query:
        return _short_query(asset.search_query)
    return _short_query(asset.label or asset.role or "image")


def _query_candidates(asset: ImageAsset) -> list[str]:
    label = _query_for_asset(asset)
    candidates = [
        label,
        _short_query(asset.role or "image"),
    ]
    unique: list[str] = []
    for candidate in candidates:
        cleaned = candidate.strip(" ,.;:")
        if cleaned and cleaned.lower() not in {item.lower() for item in unique}:
            unique.append(cleaned)
    return unique


def _short_query(value: str) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", value)
    stopwords = {
        "and",
        "with",
        "the",
        "a",
        "an",
        "of",
        "in",
        "at",
        "on",
        "restored",
        "enchanted",
        "magical",
        "scene",
        "agreement",
    }
    useful = [word.lower() for word in words if word.lower() not in stopwords]
    return " ".join(useful[:2]) or "image"
