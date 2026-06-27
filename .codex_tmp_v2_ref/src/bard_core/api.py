from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from .config import BardSettings
from .pipeline import run_pipeline

try:
    from fastapi import FastAPI, File, Query, UploadFile
except ImportError as exc:  # pragma: no cover - import-time deployment guard
    raise RuntimeError("API server requires `pip install -e .[api]`.") from exc


app = FastAPI(title="BARD Pipeline API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs/sync")
async def create_run_sync(
    audio: UploadFile = File(...),
    ratio: str = Query("1/5"),
    audio_provider: str = Query("gemini", pattern="^(clap|gemini)$"),
    story_provider: str = Query("vertex", pattern="^(local|mistral|vertex|gemini)$"),
    generate_images: bool = Query(False),
    image_provider: str = Query("none", pattern="^(none|replicate|imagen|openverse)$"),
    max_image_assets: int = Query(3, ge=1, le=6),
) -> dict:
    settings = BardSettings.from_env()
    work_dir = Path(tempfile.mkdtemp(prefix="bard-api-"))
    suffix = Path(audio.filename or "performance.mp3").suffix or ".mp3"
    audio_path = work_dir / f"input{suffix}"
    with audio_path.open("wb") as f:
        shutil.copyfileobj(audio.file, f)

    result = run_pipeline(
        audio_path=audio_path,
        settings=settings,
        ratio=ratio,
        audio_provider=audio_provider,
        story_provider=story_provider,
        generate_images=generate_images,
        image_provider=image_provider,
        max_image_assets=max_image_assets,
        send_osc=False,
    )
    return result.to_dict()
