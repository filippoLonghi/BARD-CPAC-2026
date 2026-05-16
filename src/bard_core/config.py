from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env_file(path: Path | None) -> None:
    if not path:
        return
    if not path.exists():
        raise FileNotFoundError(f"Env file not found: {path}")
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("Install python-dotenv or avoid --env-file.") from exc
    load_dotenv(dotenv_path=path, override=False)


def env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BardSettings:
    root_dir: Path
    output_dir: Path
    labelbank_path: Path
    audio_provider: str
    story_provider: str
    gcp_project_id: str | None
    gcp_location: str
    vertex_text_model: str
    vertex_audio_model: str
    storage_bucket: str | None
    local_story_model: str
    image_provider: str
    max_image_assets: int
    image_aspect_ratio: str
    image_timeout_s: float
    replicate_api_token: str | None
    replicate_model: str
    imagen_model: str
    imagen_location: str
    osc_host: str
    osc_port: int
    default_chunk_s: float
    default_wpm: float
    use_4bit: bool

    @classmethod
    def from_env(cls) -> "BardSettings":
        root = repo_root()
        output_dir = Path(env_str("BARD_OUTPUT_DIR", str(root / "runs"))).expanduser()
        labelbank_path = Path(
            env_str("BARD_LABELBANK_PATH", str(root / "data" / "labelbanks" / "clap_unified_labelbank.json"))
        ).expanduser()
        return cls(
            root_dir=root,
            output_dir=output_dir,
            labelbank_path=labelbank_path,
            audio_provider=env_str("BARD_AUDIO_PROVIDER", "clap").lower(),
            story_provider=env_str("BARD_STORY_PROVIDER", "local").lower(),
            gcp_project_id=os.environ.get("BARD_GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT"),
            gcp_location=env_str("BARD_GCP_LOCATION", os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west1")),
            vertex_text_model=env_str("BARD_VERTEX_TEXT_MODEL", "gemini-2.5-flash"),
            vertex_audio_model=env_str("BARD_VERTEX_AUDIO_MODEL", "gemini-2.5-flash"),
            storage_bucket=os.environ.get("BARD_STORAGE_BUCKET"),
            local_story_model=env_str("BARD_LOCAL_STORY_MODEL", "mistralai/Mistral-7B-Instruct-v0.2"),
            image_provider=env_str("BARD_IMAGE_PROVIDER", "none").lower(),
            max_image_assets=env_int("BARD_MAX_IMAGE_ASSETS", 3),
            image_aspect_ratio=env_str("BARD_IMAGE_ASPECT_RATIO", "1:1"),
            image_timeout_s=env_float("BARD_IMAGE_TIMEOUT_S", 120.0),
            replicate_api_token=os.environ.get("BARD_REPLICATE_API_TOKEN") or os.environ.get("REPLICATE_API_TOKEN"),
            replicate_model=env_str("BARD_REPLICATE_MODEL", "black-forest-labs/flux-schnell"),
            imagen_model=env_str("BARD_IMAGEN_MODEL", "imagen-4.0-fast-generate-001"),
            imagen_location=env_str(
                "BARD_IMAGEN_LOCATION",
                env_str("BARD_GCP_LOCATION", os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west1")),
            ),
            osc_host=env_str("BARD_OSC_HOST", "127.0.0.1"),
            osc_port=int(env_str("BARD_OSC_PORT", "5005")),
            default_chunk_s=env_float("BARD_DEFAULT_CHUNK_S", 30.0),
            default_wpm=env_float("BARD_READING_WPM", 180.0),
            use_4bit=env_bool("BARD_USE_4BIT", True),
        )
