from __future__ import annotations

from math import ceil
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from .audio import analyze_chunk_windows_with_gemini, convert_audio_to_wav, extract_audio_chunk, plan_audio_chunks
from .config import BardSettings
from .contracts import MusicSegment, PipelineResult, StoryFragment
from .images import generate_images_for_fragments
from .progress import PipelineTracer
from .storage import upload_directory_to_gcs
from .story import (
    create_story_bible,
    generate_story_fragment_with_gemini,
    initial_story_state,
    translate_music_to_story_cues_local,
)
from .transport import ProcessingOscStream, prepare_audio_playback
from .utils import (
    choose_balanced_fragment_count,
    detect_audio_duration,
    make_run_id,
    music_window_plan,
    target_story_words_from_wpm,
)


def run_sequential_pipeline(
    audio_path: Path,
    settings: BardSettings,
    *,
    chunk_s: float | None = None,
    fragment_count: int | None = None,
    planned_duration_s: float | None = None,
    words_per_fragment: int | None = None,
    music_window_s: float | None = None,
    story_wpm: float | None = None,
    fragment_target_s: float | None = None,
    fragment_min_s: float | None = None,
    fragment_max_s: float | None = None,
    short_audio_threshold_s: float | None = None,
    music_windows_per_fragment: int | None = None,
    startup_delay_s: float | None = None,
    playback_mode: str = "python",
    generate_images: bool = False,
    image_provider: str | None = None,
    max_image_assets: int = 2,
    send_osc: bool = False,
    output_dir: Path | None = None,
    debug_artifacts: bool = False,
    keep_audio_chunks: bool = False,
) -> PipelineResult:
    resolved_audio = audio_path.expanduser().resolve()
    if not resolved_audio.exists():
        raise FileNotFoundError(f"Audio file not found: {resolved_audio}")

    run_id = make_run_id()
    destination = output_dir or settings.output_dir / f"{run_id}-sequential"
    tracer = PipelineTracer()
    tracer.log("RUN start", id=run_id, audio=resolved_audio)

    actual_duration_s = detect_audio_duration(resolved_audio)
    duration_for_planning = actual_duration_s
    effective_story_wpm = story_wpm or settings.story_wpm
    effective_fragment_target_s = fragment_target_s or settings.fragment_target_s
    effective_fragment_min_s = fragment_min_s or settings.fragment_min_s
    effective_fragment_max_s = fragment_max_s or settings.fragment_max_s
    effective_short_threshold_s = short_audio_threshold_s or settings.short_audio_threshold_s
    effective_music_windows = music_windows_per_fragment or settings.music_windows_per_fragment
    fixed_music_window_s = music_window_s if music_window_s is not None else settings.music_window_s
    automatic_fragment_count: int | None = None
    if fragment_count is not None:
        chunk_s = None
    elif chunk_s is None:
        automatic_fragment_count = choose_balanced_fragment_count(
            duration_for_planning,
            target_s=effective_fragment_target_s,
            min_s=effective_fragment_min_s,
            max_s=effective_fragment_max_s,
            short_audio_threshold_s=effective_short_threshold_s,
        )
        fragment_count = automatic_fragment_count
    processing_delay_s = (
        settings.processing_startup_delay_s if startup_delay_s is None else max(0.0, startup_delay_s)
    )

    if send_osc and not generate_images:
        raise ValueError("run-fragments --send-osc requires --generate-images so Processing never starts story-only.")

    chunk_plans = plan_audio_chunks(
        resolved_audio,
        chunk_s=chunk_s,
        fragment_count=fragment_count,
    )
    if not chunk_plans:
        raise RuntimeError("The audio file did not produce any chunks.")

    effective_chunk_s = chunk_plans[0].end_s - chunk_plans[0].start_s
    planned_total = (
        max(len(chunk_plans), ceil(planned_duration_s / effective_chunk_s))
        if planned_duration_s and effective_chunk_s > 0
        else len(chunk_plans)
    )
    chosen_image_provider = (image_provider or settings.image_provider).lower() if generate_images else "none"
    if generate_images and chosen_image_provider in {"", "none"}:
        raise ValueError("Image generation is enabled. Choose imagen, replicate, or openverse.")
    music_window_plans = [
        music_window_plan(
            plan.end_s - plan.start_s,
            fixed_window_s=fixed_music_window_s,
            windows_per_fragment=effective_music_windows,
        )
        for plan in chunk_plans
    ]
    planned_music_segments = sum(count for _, count in music_window_plans)
    planned_image_calls = len(chunk_plans) * max_image_assets if generate_images else 0
    tracer.log(
        "CONFIG",
        audio_provider="gemini",
        story_provider="vertex",
        image_provider=chosen_image_provider,
        audio_model=settings.vertex_audio_model,
        story_model=settings.vertex_text_model,
        image_model=settings.image_model if chosen_image_provider == "imagen" else chosen_image_provider,
        playback=playback_mode,
        debug_artifacts=debug_artifacts,
        keep_audio_chunks=keep_audio_chunks,
    )
    tracer.log(
        "AUDIO duration",
        seconds=actual_duration_s,
        fragment_count=len(chunk_plans),
        planned_fragment_count=planned_total,
    )
    tracer.log(
        "FRAGMENTS plan",
        music_windows=planned_music_segments,
        story_scenes=len(chunk_plans),
        planned_images=planned_image_calls,
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
    processing_audio_path: Path | None = None
    playback_started_at: float | None = None
    result: PipelineResult | None = None
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
    playback = None
    if osc:
        tracer.log("OSC setup", host=settings.osc_host, port=settings.osc_port, ready_port=settings.osc_ready_port)
        osc.start()
        tracer.log("OSC handshake start")
        osc.await_ready(settings.processing_ready_timeout_s)
        tracer.log("PROCESSING ready")
        if playback_mode == "processing":
            tracer.log("AUDIO processing conversion start")
            processing_audio = convert_audio_to_wav(resolved_audio, destination / "processing_audio.wav")
            processing_audio_path = processing_audio
            tracer.log("AUDIO processing conversion done", path=processing_audio)
            osc.set_processing_audio(_processing_visible_path(processing_audio))
        else:
            tracer.log("AUDIO python preload start")
            playback = prepare_audio_playback(resolved_audio)
            tracer.log("AUDIO python preload done")

    next_music_segment_id = 1
    chunk_tmp: TemporaryDirectory[str] | None = None
    if keep_audio_chunks:
        chunk_dir = destination / "audio_chunks"
    else:
        chunk_tmp = TemporaryDirectory(prefix="bard-audio-chunks-")
        chunk_dir = Path(chunk_tmp.name)

    try:
        for index, plan in enumerate(chunk_plans):
            fragment_id = index + 1
            tracer.log("FRAGMENT audio prep start", fragment=fragment_id, start_s=plan.start_s, end_s=plan.end_s)
            chunk = extract_audio_chunk(resolved_audio, chunk_dir, plan)
            tracer.log("FRAGMENT audio prep done", fragment=fragment_id, path=chunk.path if keep_audio_chunks else "temp")

            analysis_window_s, target_music_windows = music_window_plans[index]
            tracer.log(
                "FRAGMENT analysis start",
                fragment=fragment_id,
                model=settings.vertex_audio_model,
                windows=target_music_windows,
            )
            scene_music_segments = analyze_chunk_windows_with_gemini(
                chunk.path,
                settings,
                first_segment_id=next_music_segment_id,
                start_s=chunk.start_s,
                end_s=chunk.end_s,
                window_s=analysis_window_s,
                target_segments=target_music_windows if fixed_music_window_s is None else None,
            )
            tracer.log("FRAGMENT analysis done", fragment=fragment_id, segments=len(scene_music_segments))
            if not keep_audio_chunks:
                chunk.path.unlink(missing_ok=True)
                tracer.log("FRAGMENT temp audio removed", fragment=fragment_id)

            translate_music_to_story_cues_local(scene_music_segments)
            music_segments.extend(scene_music_segments)
            next_music_segment_id += len(scene_music_segments)

            if not bible:
                tracer.log("STORY bible start", fragment=fragment_id, model=settings.vertex_text_model)
                bible = create_story_bible(scene_music_segments, settings, planned_total)
                state = initial_story_state(bible)
                tracer.log("STORY bible done", title=bible.get("title"), world=bible.get("world_profile", {}).get("id"))

            chunk_words = words_per_fragment or target_story_words_from_wpm(
                chunk.end_s - chunk.start_s,
                effective_story_wpm,
            )
            target_word_counts.append(chunk_words)
            tracer.log("FRAGMENT story start", fragment=fragment_id, words=chunk_words, model=settings.vertex_text_model)
            tracer.log("FRAGMENT image prompts start", fragment=fragment_id)
            fragment, state = generate_story_fragment_with_gemini(
                scene_music_segments[0],
                settings,
                fragment_index=index,
                total_segments=planned_total,
                words_per_fragment=chunk_words,
                bible=bible,
                state=state,
                previous_text=full_story,
                is_final=index == len(chunk_plans) - 1,
                music_timeline=scene_music_segments,
            )
            fragment.id = fragment_id
            tracer.log("FRAGMENT story done", fragment=fragment_id, words=len(fragment.text.split()))
            tracer.log("FRAGMENT image prompts done", fragment=fragment_id, count=len(fragment.image_assets))
            fragments.append(fragment)
            full_story = "\n\n".join(item.text for item in fragments)
            tracer.log("STORY state updated", fragment=fragment_id, last_event=state.get("last_event"))

            if generate_images:
                tracer.log("FRAGMENT images start", fragment=fragment_id, count=max_image_assets)
                image_metadata = generate_images_for_fragments(
                    fragments=[fragment],
                    settings=settings,
                    output_dir=destination / "images",
                    provider=chosen_image_provider,
                    max_assets=max_image_assets,
                    print_estimate=index == 0,
                    tracer=tracer,
                )
                for key in image_totals:
                    image_totals[key] += image_metadata.get(key, 0) or 0
                tracer.log(
                    "FRAGMENT images done",
                    fragment=fragment_id,
                    ready=_ready_image_count(fragment),
                    failed=image_metadata.get("failed_image_assets", 0),
                )

            require_images = send_osc or generate_images
            scene_ready = _is_scene_ready(fragment, require_image=require_images)
            if index == 0:
                _validate_scene_ready(fragment, require_image=require_images)
                tracer.log("FRAGMENT first ready", fragment=fragment_id)
            elif scene_ready:
                tracer.log("FRAGMENT ready", fragment=fragment_id)
            else:
                tracer.log("FRAGMENT not ready", fragment=fragment_id, action="hold-current-scene")

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
                fixed_music_window_s,
                effective_music_windows,
                automatic_fragment_count,
                effective_story_wpm,
                effective_fragment_target_s,
                effective_fragment_min_s,
                effective_fragment_max_s,
                effective_short_threshold_s,
                planned_duration_s,
                planned_total,
                chosen_image_provider,
                max_image_assets,
                playback_mode,
                image_totals,
                target_word_counts,
                music_window_plans,
                settings,
                debug_artifacts=debug_artifacts,
                keep_audio_chunks=keep_audio_chunks,
                processing_audio_path=processing_audio_path,
                complete=index == len(chunk_plans) - 1,
            )
            tracer.log("ARTIFACTS write", fragment=fragment_id, debug=debug_artifacts)
            result.write(
                destination,
                debug_artifacts=debug_artifacts,
                trace_events=tracer.to_json(),
                processing_audio_path=str(processing_audio_path) if processing_audio_path else None,
            )

            if osc and scene_ready:
                if playback_started_at and fragment.start_s is not None:
                    late_by = monotonic() - playback_started_at - float(fragment.start_s)
                    if late_by > 0.25:
                        tracer.log("FRAGMENT ready late", fragment=fragment_id, delay_s=late_by)
                tracer.log("OSC send fragment", fragment=fragment_id, final=index == len(chunk_plans) - 1)
                osc.send(fragment, final=index == len(chunk_plans) - 1)
                if index == 0:
                    if processing_delay_s > 0:
                        tracer.log("PROCESSING settle", seconds=processing_delay_s)
                        osc.settle(processing_delay_s)
                    tracer.log("OSC prime", fragment=fragment_id)
                    osc.prime(settings.processing_ready_timeout_s)
                    tracer.log("PROCESSING primed", fragment=fragment_id)
                    tracer.log("OSC start")
                    osc.play()
                    playback_started_at = monotonic()
                    if playback:
                        playback.play()
                    tracer.log("AUDIO playback start", mode=playback_mode)
            elif osc and index > 0:
                tracer.log("OSC skip incomplete fragment", fragment=fragment_id)

        if playback:
            tracer.log("AUDIO playback wait start")
            playback.wait()
            tracer.log("AUDIO playback wait done")

        if result is None:
            raise RuntimeError("No result was produced.")
        if settings.storage_bucket:
            tracer.log("STORAGE upload start", bucket=settings.storage_bucket)
            result.metadata["gcs_uri"] = upload_directory_to_gcs(
                local_dir=destination,
                bucket_name=settings.storage_bucket,
                prefix=f"runs/{run_id}",
            )
            tracer.log("STORAGE upload done", uri=result.metadata["gcs_uri"])
        tracer.log("RUN complete", id=run_id, fragments=len(fragments))
        result.write(
            destination,
            debug_artifacts=debug_artifacts,
            trace_events=tracer.to_json(),
            processing_audio_path=str(processing_audio_path) if processing_audio_path else None,
        )
        return result
    finally:
        if chunk_tmp is not None:
            chunk_tmp.cleanup()


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
    music_window_s: float | None,
    music_windows_per_fragment: int,
    automatic_fragment_count: int | None,
    story_wpm: float,
    fragment_target_s: float,
    fragment_min_s: float,
    fragment_max_s: float,
    short_audio_threshold_s: float,
    planned_duration_s: float | None,
    planned_total: int,
    image_provider: str,
    max_image_assets: int,
    playback_mode: str,
    image_totals: dict[str, int | float],
    target_word_counts: list[int],
    music_window_plans: list[tuple[float, int]],
    settings: BardSettings,
    *,
    debug_artifacts: bool,
    keep_audio_chunks: bool,
    processing_audio_path: Path | None,
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
            "music_window_mode": "fixed" if music_window_s is not None else "derived-per-fragment",
            "music_windows_per_fragment": music_windows_per_fragment,
            "music_window_plans": [
                {"window_s": window_s, "count": count} for window_s, count in music_window_plans
            ],
            "music_segment_count": len(music_segments),
            "story_scene_count": len(fragments),
            "target_word_counts": target_word_counts,
            "processing_slide_duration_s": chunk_s,
            "audio_provider": "gemini",
            "story_provider": "vertex",
            "story_language": settings.story_language,
            "story_level": settings.story_level,
            "story_wpm": story_wpm,
            "reading_wpm": settings.default_wpm,
            "text_coverage_deprecated": settings.text_coverage,
            "target_words_per_fragment": settings.target_words_per_fragment,
            "automatic_fragment_count": automatic_fragment_count,
            "fragment_target_s": fragment_target_s,
            "fragment_min_s": fragment_min_s,
            "fragment_max_s": fragment_max_s,
            "short_audio_threshold_s": short_audio_threshold_s,
            "image_provider": image_provider,
            "playback_mode": playback_mode,
            "processing_audio_path": str(processing_audio_path) if processing_audio_path else None,
            "debug_artifacts": debug_artifacts,
            "keep_audio_chunks": keep_audio_chunks,
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
    if require_image and not _has_required_images(fragment):
        raise RuntimeError(
            f"Story scene {fragment.id} does not have ready background and subject images. "
            "Processing/audio were kept waiting instead of starting blank."
        )


def _is_scene_ready(fragment: StoryFragment, *, require_image: bool) -> bool:
    if not fragment.text.strip():
        return False
    return not require_image or _has_required_images(fragment)


def _ready_image_count(fragment: StoryFragment) -> int:
    return len(_ready_image_roles(fragment))


def _has_required_images(fragment: StoryFragment) -> bool:
    return _ready_image_roles(fragment) >= {"background", "subject"}


def _ready_image_roles(fragment: StoryFragment) -> set[str]:
    return {
        str(asset.role or "").strip().lower()
        for asset in fragment.image_assets
        if asset.local_path
        and asset.status in {"generated", "retrieved"}
        and Path(asset.local_path).expanduser().exists()
    }


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
