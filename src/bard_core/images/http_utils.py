from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json
import mimetypes


def read_json_url(url: str, *, headers: dict[str, str] | None = None, timeout_s: float = 60.0) -> dict:
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(_http_error_message(exc)) from exc


def post_json_url(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
    timeout_s: float = 60.0,
) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = Request(url, data=body, headers=request_headers, method="POST")
    try:
        with urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(_http_error_message(exc)) from exc


def download_image_url(
    url: str,
    target_without_suffix: Path,
    *,
    headers: dict[str, str] | None = None,
    timeout_s: float = 60.0,
    allowed_mime_types: set[str] | None = None,
) -> tuple[Path, str | None]:
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=timeout_s) as response:
            content_type = response.headers.get_content_type()
            if allowed_mime_types and content_type not in allowed_mime_types:
                raise RuntimeError(f"Downloaded URL returned {content_type}, expected one of {allowed_mime_types}.")
            suffix = _suffix_for_response(url, content_type)
            target_path = target_without_suffix.with_suffix(suffix)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(response.read())
            return target_path, content_type
    except HTTPError as exc:
        raise RuntimeError(_http_error_message(exc)) from exc


def _suffix_for_response(url: str, content_type: str | None) -> str:
    if content_type:
        suffix = mimetypes.guess_extension(content_type)
        if suffix in {".jpe"}:
            return ".jpg"
        if suffix:
            return suffix

    clean_url = url.split("?", 1)[0].lower()
    for suffix in (".png", ".jpg", ".jpeg"):
        if clean_url.endswith(suffix):
            return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"


def _http_error_message(exc: HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    message = f"HTTP {exc.code} {exc.reason}"
    if body:
        message = f"{message}: {body[:500]}"
    return message
