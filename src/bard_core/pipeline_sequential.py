from __future__ import annotations

from math import ceil
from pathlib import Path

from .audio import analyze_chunk_windows_with_gemini, convert_audio_to_wav, split_audio_file
from .config import BardSettings
from .contracts import MusicSegment, PipelineResult, StoryFragment
from .images import generate_images_for_fragments
from .pipeline import make_run_id
from .storage import upload_directory_to_gcs
from .story import (
    create_story_bible,
    generate_story_fragment_with_gemini,
    initial_story_state,
    translate_music_to_story_cues_local,
)
from .transport import ProcessingOscStream, prepare_audio_playback
from .utils import detect_audio_duration, story_chunk_seconds, target_story_words


def run_sequential_pipeline(
    audio_path: Path,
    settings: BardSettings,
    *,
    chunk_s: float | None = None,
    fragment_count: int | None = None,
    planned_duration_s: float | None = None,
    words_per_fragment: int | None = None,
    music_window_s: float | None = None,
    startup_delay_s: float | None = None,
    playback_mode: str = "python",
    generate_images: bool = False,
    image_provider: str | None = None,
    max_image_assets: int = 3,
    send_osc: bool = False,
    output_dir: Path | None = None,
) -> PipelineResult:
    resolved_audio = audio_path.expanduser().resolve()
    if not resolved_audio.exists():
        raise FileNotFoundError(f"Audio file not found: {resolved_audio}")
    if fragment_count is not None:
        chunk_s = None
    elif chunk_s is None:
        chunk_s = max(
            settings.story_scene_s,
            story_chunk_seconds(
                settings.target_words_per_fragment,
                settings.default_wpm,
                settings.text_coverage,
            ),
        )
    analysis_window_s = music_window_s or settings.music_window_s
    processing_delay_s = (
        settings.processing_startup_delay_s if startup_delay_s is None else max(0.0, startup_delay_s)
    )

    run_id = make_run_id()
    destination = output_dir or settings.output_dir / f"{run_id}-sequential"
    chunks = split_audio_file(
        resolved_audio,
        destination / "audio_chunks",
        chunk_s=chunk_s,
        fragment_count=fragment_count,
    )
    if not chunks:
        raise RuntimeError("The audio file did not produce any chunks.")

    actual_duration_s = detect_audio_duration(resolved_audio)
    effective_chunk_s = chunks[0].end_s - chunks[0].start_s
    planned_total = (
        max(len(chunks), ceil(planned_duration_s / effective_chunk_s))
        if planned_duration_s and effective_chunk_s > 0
        else len(chunks)
    )
    chosen_image_provider = (image_provider or settings.image_provider).lower() if generate_images else "none"
    if generate_images and chosen_image_provider in {"", "none"}:
        raise ValueError("Image generation is enabled. Choose imagen, replicate, or openverse.")
    planned_music_segments = sum(
        max(1, round((chunk.end_s - chunk.start_s) / max(5.0, analysis_window_s))) for chunk in chunks
    )
    planned_image_calls = len(chunks) * max_image_assets if generate_images else 0
    print(
        "Hybrid plan: "
        f"{planned_music_segments} fine music observations in {len(chunks)} API audio call(s), "
        f"{len(chunks)} story scene call(s), {planned_image_calls} image call/retrieval(s)."
    )

    music_segments: list[MusicSegment] = []
    fragments: list[StoryFragment] = []
    bible: dict[str, object] = {}
    state: dict[str, object] = {}
    full_story = ""
    image_totals = {
        "planned_image_assets": 0,
        "generated_image_assets": 0,
        "failed_image_assets": 0,
        "estimated_cost_usd": 0.0,
    }
    target_word_counts: list[int] = []
    playback_mode = playback_mode.lower().strip()
    if playback_mode not in {"python", "processing"}:
        raise ValueError("playback_mode must be 'python' or 'processing'.")
    osc = (
        ProcessingOscStream(
            settings.osc_host,
            settings.osc_port,
            slide_duration_s=effective_chunk_s,
            include_images=generate_images,
            ready_port=settings.osc_ready_port,
            ready_bind_host=settings.osc_ready_bind_host,
            path_mapper=_processing_visible_path,
        )
        if send_osc
        else None
    )
    playback = prepare_audio_playback(resolved_audio) if send_osc and playback_mode == "python" else None
    if osc:
        osc.start()
        osc.await_ready(settings.processing_ready_timeout_s)
        if playback_mode == "processing":
            processing_audio = convert_audio_to_wav(resolved_audio, destination / "processing_audio.wav")
            osc.set_processing_audio(_processing_visible_path(processing_audio))

    next_music_segment_id = 1
    for index, chunk in enumerate(chunks):
        scene_music_segments = analyze_chunk_windows_with_gemini(
            chunk.path,
            settings,
            first_segment_id=next_music_segment_id,
            start_s=chunk.start_s,
            end_s=chunk.end_s,
            window_s=analysis_window_s,
        )
        translate_music_to_story_cues_local(scene_music_segments)
        music_segments.extend(scene_music_segments)
        next_music_segment_id += len(scene_music_segments)

        if not bible:
            bible = create_story_bible(scene_music_segments, settings, planned_total)
            state = initial_story_state(bible)

        chunk_words = words_per_fragment or target_story_words(
            chunk.end_s - chunk.start_s,
            settings.default_wpm,
            settings.text_coverage,
        )
        target_word_counts.append(chunk_words)
        fragment, state = generate_story_fragment_with_gemini(
            scene_music_segments[0],
            settings,
            fragment_index=index,
            total_segments=planned_total,
            words_per_fragment=chunk_words,
            bible=bible,
            state=state,
            previous_text=full_story,
            is_final=index == len(chunks) - 1,
            music_timeline=scene_music_segments,
        )
        fragment.id = index + 1
        fragments.append(fragment)
        full_story = "\n\n".join(item.text for item in fragments)

        if generate_images:
            image_metadata = generate_images_for_fragments(
                fragments=[fragment],
                settings=settings,
                output_dir=destination / "images",
                provider=chosen_image_provider,
                max_assets=max_image_assets,
                print_estimate=index == 0,
            )
            for key in image_totals:
                image_totals[key] += image_metadata.get(key, 0) or 0

        _validate_scene_ready(fragment, require_image=generate_images)

        result = _build_result(
            run_id,
            resolved_audio,
            music_segments,
            fragments,
            full_story,
            bible,
            state,
            actual_duration_s,
            effective_chunk_s,
            analysis_window_s,
            planned_duration_s,
            planned_total,
            chosen_image_provider,
            max_image_assets,
            playback_mode,
            image_totals,
            target_word_counts,
            settings,
            complete=index == len(chunks) - 1,
        )
        result.write(destination)
        if osc:
            osc.send(fragment, final=index == len(chunks) - 1)
            if index == 0 and playback:
                if processing_delay_s > 0:
                    osc.settle(processing_delay_s)
                osc.prime(settings.processing_ready_timeout_s)
                osc.play()
                playback.play()
            elif index == 0 and playback_mode == "processing":
                if processing_delay_s > 0:
                    osc.settle(processing_delay_s)
                osc.prime(settings.processing_ready_timeout_s)
                osc.play()

    if playback:
        playback.wait()

    if settings.storage_bucket:
        result.metadata["gcs_uri"] = upload_directory_to_gcs(
            local_dir=destination,
            bucket_name=settings.storage_bucket,
            prefix=f"runs/{run_id}",
        )
        result.write(destination)
    return result


def _build_result(
    run_id: str,
    audio_path: Path,
    music_segments: list[MusicSegment],
    fragments: list[StoryFragment],
    full_story: str,
    bible: dict[str, object],
    state: dict[str, object],
    actual_duration_s: float | None,
    chunk_s: float,
    music_window_s: float,
    planned_duration_s: float | None,
    planned_total: int,
    image_provider: str,
    max_image_assets: int,
    playback_mode: str,
    image_totals: dict[str, int | float],
    target_word_counts: list[int],
    settings: BardSettings,
    *,
    complete: bool,
) -> PipelineResult:
    return PipelineResult(
        run_id=run_id,
        audio_path=str(audio_path),
        music_segments=music_segments,
        fragments=fragments,
        full_story=full_story,
        story_bible=bible,
        story_state=state,
        metadata={
            "execution_mode": "sequential-file" if planned_duration_s is None else "planned-duration-simulation",
            "complete": complete,
            "duration_s": actual_duration_s,
            "planned_duration_s": planned_duration_s,
            "planned_fragment_count": planned_total,
            "completed_fragment_count": len(fragments),
            "chunk_s": chunk_s,
            "story_scene_s": chunk_s,
            "music_window_s": music_window_s,
            "music_segment_count": len(music_segments),
            "story_scene_count": len(fragments),
            "target_word_counts": target_word_counts,
            "processing_slide_duration_s": chunk_s,
            "audio_provider": "gemini",
            "story_provider": "vertex",
            "story_language": settings.story_language,
            "story_level": settings.story_level,
            "reading_wpm": settings.default_wpm,
            "text_coverage": settings.text_coverage,
            "target_words_per_fragment": settings.target_words_per_fragment,
            "image_provider": image_provider,
            "playback_mode": playback_mode,
            "estimated_api_calls": {
                "audio_analysis": planned_total,
                "music_to_story_llm": 0,
                "story_bible": 1,
                "story_scene_generation": planned_total,
                "image_generation_or_retrieval": planned_total * max_image_assets,
            },
            **image_totals,
        },
    )


def _validate_scene_ready(fragment: StoryFragment, *, require_image: bool) -> None:
    if not fragment.text.strip():
        raise RuntimeError(f"Story scene {fragment.id} is empty; playback was not started.")
    if not require_image:
        return
    ready_images = [
        asset
        for asset in fragment.image_assets
        if asset.local_path
        and asset.status in {"generated", "retrieved"}
        and Path(asset.local_path).expanduser().exists()
    ]
    if not ready_images:
        raise RuntimeError(
            f"Story scene {fragment.id} has no usable image. Processing/audio were kept waiting instead of starting blank."
        )


def _processing_visible_path(container_path: Path) -> str:
    import os

    host_workspace = os.environ.get("BARD_HOST_WORKSPACE")
    container_workspace = Path(os.environ.get("BARD_CONTAINER_WORKSPACE", "/workspace"))
    if not host_workspace:
        return container_path.as_posix()
    try:
        relative = container_path.resolve().relative_to(container_workspace.resolve())
    except ValueError as exc:
        raise RuntimeError(
            f"Processing audio {container_path} is not inside mounted workspace {container_workspace}."
        ) from exc
    host_root = host_workspace.replace("\\", "/").rstrip("/")
    return f"{host_root}/{relative.as_posix()}"
