from __future__ import annotations

try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
except ImportError as exc:  # pragma: no cover - import-time deployment guard
    raise RuntimeError("API server requires `pip install -e .[api]`.") from exc


app = FastAPI(title="BARD Pipeline API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs/sync")
async def create_run_sync(
    audio: UploadFile = File(...),
) -> dict:
    raise HTTPException(
        status_code=410,
        detail=(
            "The legacy batch API is disabled in BARD-CPAC-2026 v2.3. "
            "Use the supported CLI command: bard run-fragments."
        ),
    )
