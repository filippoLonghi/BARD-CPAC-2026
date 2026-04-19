from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .audio import analyze_with_clap, analyze_with_gemini
from .config import BardSettings
from .contracts import PipelineResult
from .story import generate_story_with_gemini, generate_story_with_local_mistral
from .storage import upload_directory_to_gcs
from .transport import send_fragments_to_processing
from .utils import compute_chunk_and_words, detect_audio_duration, estimate_segment_count


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_pipeline(
    audio_path: Path,
    settings: BardSettings,
    ratio: str = "1/5",
    audio_provider: str | None = None,
    story_provider: str | None = None,
    send_osc: bool = False,
    output_dir: Path | None = None,
) -> PipelineResult:
    resolved_audio = audio_path.expanduser().resolve()
    if not resolved_audio.exists():
        raise FileNotFoundError(f"Audio file not found: {resolved_audio}")

    duration_s = detect_audio_duration(resolved_audio)
    chunk_s, words_per_fragment = compute_chunk_and_words(
        duration_s=duration_s,
        ratio=ratio,
        reading_wpm=settings.default_wpm,
        default_chunk_s=settings.default_chunk_s,
    )

    chosen_audio_provider = (audio_provider or settings.audio_provider).lower()
    chosen_story_provider = (story_provider or settings.story_provider).lower()

    if chosen_audio_provider == "clap":
        music_segments = analyze_with_clap(resolved_audio, settings, chunk_s=chunk_s, top_k=1)
    elif chosen_audio_provider == "gemini":
        music_segments = analyze_with_gemini(
            resolved_audio,
            settings,
            target_segments=estimate_segment_count(duration_s, chunk_s),
        )
    else:
        raise ValueError(f"Unsupported audio provider: {chosen_audio_provider}")

    if chosen_story_provider in {"vertex", "gemini"}:
        fragments, full_story = generate_story_with_gemini(music_segments, settings, words_per_fragment)
    elif chosen_story_provider in {"local", "mistral"}:
        fragments, full_story = generate_story_with_local_mistral(music_segments, settings, words_per_fragment)
    else:
        raise ValueError(f"Unsupported story provider: {chosen_story_provider}")

    run_id = make_run_id()
    result = PipelineResult(
        run_id=run_id,
        audio_path=str(resolved_audio),
        music_segments=music_segments,
        fragments=fragments,
        full_story=full_story,
        metadata={
            "duration_s": duration_s,
            "chunk_s": chunk_s,
            "words_per_fragment": words_per_fragment,
            "audio_provider": chosen_audio_provider,
            "story_provider": chosen_story_provider,
        },
    )

    destination = output_dir or (settings.output_dir / run_id)
    result.write(destination)
    if settings.storage_bucket:
        gcs_uri = upload_directory_to_gcs(
            local_dir=destination,
            bucket_name=settings.storage_bucket,
            prefix=f"runs/{run_id}",
        )
        result.metadata["gcs_uri"] = gcs_uri
        result.write(destination)

    if send_osc:
        send_fragments_to_processing(
            fragments=fragments,
            host=settings.osc_host,
            port=settings.osc_port,
            slide_duration_s=chunk_s,
        )
    return result
