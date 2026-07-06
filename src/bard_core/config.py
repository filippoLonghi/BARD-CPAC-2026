from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import warnings


# Shared project defaults for the active run-fragments pipeline.
# Change these values when the team wants a new committed default behavior.
DEFAULT_STORY_WPM = 70.0
DEFAULT_FRAGMENT_TARGET_S = 60.0
DEFAULT_FRAGMENT_MIN_S = 50.0
DEFAULT_FRAGMENT_MAX_S = 70.0
DEFAULT_SHORT_AUDIO_THRESHOLD_S = 120.0
DEFAULT_MUSIC_WINDOWS_PER_FRAGMENT = 2
DEFAULT_STARTUP_BUFFER_FRAGMENTS = 2

DEFAULT_LIVE_STORY_WPM = 70.0
DEFAULT_LIVE_STORY_SCENE_S = 30.0
DEFAULT_LIVE_MUSIC_WINDOWS_PER_FRAGMENT = 2
DEFAULT_LIVE_STARTUP_BUFFER_FRAGMENTS = 2


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


def env_float_optional(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return None
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
    image_model: str
    image_location: str
    remove_image_background: bool
    background_removal_provider: str
    replicate_api_token: str | None
    replicate_model: str
    imagen_model: str
    imagen_location: str
    osc_host: str
    osc_port: int
    osc_ready_port: int
    osc_ready_bind_host: str
    processing_ready_timeout_s: float
    default_chunk_s: float
    default_wpm: float
    story_wpm: float
    fragment_target_s: float
    fragment_min_s: float
    fragment_max_s: float
    short_audio_threshold_s: float
    story_language: str
    story_level: str
    text_coverage: float
    target_words_per_fragment: int
    music_window_s: float | None
    music_windows_per_fragment: int
    story_scene_s: float
    processing_startup_delay_s: float
    startup_buffer_fragments: int
    live_story_wpm: float
    live_music_windows_per_fragment: int
    live_story_scene_s: float
    live_startup_buffer_fragments: int
    use_4bit: bool

    @classmethod
    def from_env(cls) -> "BardSettings":
        root = repo_root()
        output_dir = Path(env_str("BARD_OUTPUT_DIR", str(root / "runs"))).expanduser()
        labelbank_path = Path(
            env_str("BARD_LABELBANK_PATH", str(root / "data" / "labelbanks" / "clap_unified_labelbank.json"))
        ).expanduser()
        image_model = (
            os.environ.get("BARD_IMAGE_MODEL")
            or os.environ.get("BARD_IMAGEN_MODEL")
            or "imagen-4.0-fast-generate-001"
        )
        image_location = (
            os.environ.get("BARD_IMAGE_LOCATION")
            or os.environ.get("BARD_IMAGEN_LOCATION")
            or os.environ.get("BARD_GCP_LOCATION")
            or os.environ.get("GOOGLE_CLOUD_LOCATION")
            or "europe-west1"
        )
        if os.environ.get("BARD_TEXT_COVERAGE") not in {None, ""}:
            warnings.warn(
                "BARD_TEXT_COVERAGE is deprecated for run-fragments timing. "
                "Use BARD_STORY_WPM or --story-wpm instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        legacy_wpm = os.environ.get("BARD_READING_WPM")
        story_wpm = (
            os.environ.get("BARD_STORY_WPM")
            or os.environ.get("BARD_TARGET_DISPLAY_WPM")
            or legacy_wpm
            or str(DEFAULT_STORY_WPM)
        )
        return cls(
            root_dir=root,
            output_dir=output_dir,
            labelbank_path=labelbank_path,
            audio_provider=env_str("BARD_AUDIO_PROVIDER", "gemini").lower(),
            story_provider=env_str("BARD_STORY_PROVIDER", "vertex").lower(),
            gcp_project_id=os.environ.get("BARD_GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT"),
            gcp_location=env_str("BARD_GCP_LOCATION", os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west1")),
            vertex_text_model=env_str("BARD_VERTEX_TEXT_MODEL", "gemini-2.5-flash"),
            vertex_audio_model=env_str("BARD_VERTEX_AUDIO_MODEL", "gemini-2.5-flash"),
            storage_bucket=os.environ.get("BARD_STORAGE_BUCKET"),
            local_story_model=env_str("BARD_LOCAL_STORY_MODEL", "mistralai/Mistral-7B-Instruct-v0.2"),
            image_provider=env_str("BARD_IMAGE_PROVIDER", "none").lower(),
            max_image_assets=env_int("BARD_MAX_IMAGE_ASSETS", 2),
            image_aspect_ratio=env_str("BARD_IMAGE_ASPECT_RATIO", "1:1"),
            image_timeout_s=env_float("BARD_IMAGE_TIMEOUT_S", 120.0),
            image_model=image_model,
            image_location=image_location,
            remove_image_background=env_bool("BARD_REMOVE_IMAGE_BACKGROUND", True),
            background_removal_provider=env_str("BARD_BACKGROUND_REMOVAL_PROVIDER", "rembg").lower(),
            replicate_api_token=os.environ.get("BARD_REPLICATE_API_TOKEN") or os.environ.get("REPLICATE_API_TOKEN"),
            replicate_model=env_str("BARD_REPLICATE_MODEL", "black-forest-labs/flux-schnell"),
            imagen_model=image_model,
            imagen_location=image_location,
            osc_host=env_str("BARD_OSC_HOST", "127.0.0.1"),
            osc_port=int(env_str("BARD_OSC_PORT", "5005")),
            osc_ready_port=env_int("BARD_OSC_READY_PORT", 5007),
            osc_ready_bind_host=env_str("BARD_OSC_READY_BIND_HOST", "127.0.0.1"),
            processing_ready_timeout_s=env_float("BARD_PROCESSING_READY_TIMEOUT_S", 8.0),
            default_chunk_s=env_float("BARD_DEFAULT_CHUNK_S", 30.0),
            default_wpm=env_float("BARD_READING_WPM", 120.0),
            story_wpm=float(story_wpm),
            fragment_target_s=env_float("BARD_FRAGMENT_TARGET_S", DEFAULT_FRAGMENT_TARGET_S),
            fragment_min_s=env_float("BARD_FRAGMENT_MIN_S", DEFAULT_FRAGMENT_MIN_S),
            fragment_max_s=env_float("BARD_FRAGMENT_MAX_S", DEFAULT_FRAGMENT_MAX_S),
            short_audio_threshold_s=env_float("BARD_SHORT_AUDIO_THRESHOLD_S", DEFAULT_SHORT_AUDIO_THRESHOLD_S),
            story_language=env_str("BARD_STORY_LANGUAGE", "English"),
            story_level=env_str("BARD_STORY_LEVEL", "children"),
            text_coverage=env_float("BARD_TEXT_COVERAGE", 0.72),
            target_words_per_fragment=env_int("BARD_TARGET_WORDS_PER_FRAGMENT", 72),
            music_window_s=env_float_optional("BARD_MUSIC_WINDOW_S"),
            music_windows_per_fragment=env_int("BARD_MUSIC_WINDOWS_PER_FRAGMENT", DEFAULT_MUSIC_WINDOWS_PER_FRAGMENT),
            story_scene_s=env_float("BARD_STORY_SCENE_S", 60.0),
            processing_startup_delay_s=env_float("BARD_PROCESSING_STARTUP_DELAY_S", 1.5),
            startup_buffer_fragments=env_int(
                "BARD_STARTUP_BUFFER_FRAGMENTS",
                DEFAULT_STARTUP_BUFFER_FRAGMENTS,
            ),
            live_story_wpm=env_float("BARD_LIVE_STORY_WPM", DEFAULT_LIVE_STORY_WPM),
            live_music_windows_per_fragment=env_int(
                "BARD_LIVE_MUSIC_WINDOWS_PER_FRAGMENT",
                DEFAULT_LIVE_MUSIC_WINDOWS_PER_FRAGMENT,
            ),
            live_story_scene_s=env_float("BARD_LIVE_STORY_SCENE_S", DEFAULT_LIVE_STORY_SCENE_S),
            live_startup_buffer_fragments=env_int(
                "BARD_LIVE_STARTUP_BUFFER_FRAGMENTS",
                DEFAULT_LIVE_STARTUP_BUFFER_FRAGMENTS,
            ),
            use_4bit=env_bool("BARD_USE_4BIT", True),
        )
