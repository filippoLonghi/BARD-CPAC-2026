from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil
from pathlib import Path
from queue import Queue
from threading import Event, Thread
from time import monotonic
from typing import Iterator

from .audio import analyze_chunk_windows_with_gemini
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
from .transport import ProcessingOscStream
from .utils import make_run_id, music_window_plan, target_story_words_from_wpm


@dataclass(frozen=True)
class LiveAudioChunk:
    id: int
    path: Path
    start_s: float
    end_s: float
    final_available: bool = False


def run_live_pipeline(
    *,
    settings: BardSettings,
    duration_seconds: float,
    input_device: str | None = None,
    sample_rate: int = 44_100,
    chunk_s: float | None = None,
    words_per_fragment: int | None = None,
    music_window_s: float | None = None,
    story_wpm: float | None = None,
    music_windows_per_fragment: int | None = None,
    startup_delay_s: float | None = None,
    startup_buffer_fragments: int | None = None,
    generate_images: bool = False,
    image_provider: str | None = None,
    max_image_assets: int = 2,
    output_dir: Path | None = None,
    debug_artifacts: bool = False,
    keep_audio_chunks: bool = False,
) -> PipelineResult:
    if duration_seconds <= 0:
        raise ValueError("--duration-seconds must be greater than 0.")

    effective_chunk_s = max(0.001, float(chunk_s if chunk_s is not None else settings.live_story_scene_s))
    planned_total = max(1, ceil(duration_seconds / effective_chunk_s))
    effective_story_wpm = story_wpm or settings.live_story_wpm
    effective_music_windows = music_windows_per_fragment or settings.live_music_windows_per_fragment
    fixed_music_window_s = music_window_s if music_window_s is not None else settings.music_window_s
    processing_delay_s = settings.processing_startup_delay_s if startup_delay_s is None else max(0.0, startup_delay_s)
    effective_startup_buffer_fragments = max(
        1,
        int(
            startup_buffer_fragments
            if startup_buffer_fragments is not None
            else settings.live_startup_buffer_fragments
        ),
    )

    chosen_image_provider = (image_provider or settings.image_provider).lower() if generate_images else "none"
    if generate_images and chosen_image_provider in {"", "none"}:
        raise ValueError("Image generation is enabled. Choose imagen or openverse.")

    _ensure_microphone_dependencies()

    run_id = make_run_id()
    destination = output_dir or settings.output_dir / f"{run_id}-live"
    tracer = PipelineTracer()
    source_mode = "microphone"
    tracer.log(
        "LIVE run start",
        id=run_id,
        source=source_mode,
        input_device=input_device,
        planned_duration_s=duration_seconds,
        chunk_s=effective_chunk_s,
        planned_fragment_count=planned_total,
    )
    tracer.log(
        "CONFIG",
        audio_provider="gemini",
        story_provider="vertex",
        image_provider=chosen_image_provider,
        audio_model=settings.vertex_audio_model,
        story_model=settings.vertex_text_model,
        image_model=settings.image_model if chosen_image_provider == "imagen" else chosen_image_provider,
        playback="none",
        debug_artifacts=debug_artifacts,
        keep_audio_chunks=keep_audio_chunks,
        startup_buffer_fragments=effective_startup_buffer_fragments,
    )

    osc = ProcessingOscStream(
        settings.osc_host,
        settings.osc_port,
        slide_duration_s=effective_chunk_s,
        include_images=False,
        ready_port=settings.osc_ready_port,
        ready_bind_host=settings.osc_ready_bind_host,
        path_mapper=_processing_visible_path,
    )
    tracer.log("OSC setup", host=settings.osc_host, port=settings.osc_port, ready_port=settings.osc_ready_port)
    osc.start()
    tracer.log("OSC handshake start")
    osc.await_ready(settings.processing_ready_timeout_s)
    tracer.log("PROCESSING ready")

    music_segments: list[MusicSegment] = []
    fragments: list[StoryFragment] = []
    bible: dict[str, object] = {}
    state: dict[str, object] = {}
    full_story = ""
    target_word_counts: list[int] = []
    music_window_plans: list[dict[str, object]] = []
    image_totals = {
        "planned_image_assets": 0,
        "generated_image_assets": 0,
        "failed_image_assets": 0,
        "estimated_cost_usd": 0.0,
    }
    next_music_segment_id = 1
    result: PipelineResult | None = None
    visual_started_at: float | None = None
    visual_delay_s: float | None = None
    stream_finished = False
    source_started_at = monotonic()
    recorded_audio_path: Path | None = None
    recorded_chunk_paths: list[Path] = []
    chunk_dir = destination / "recorded_audio_chunks"

    try:
        chunks = _record_live_chunks(
            chunk_dir,
            chunk_s=effective_chunk_s,
            planned_duration_s=duration_seconds,
            planned_total=planned_total,
            input_device=input_device,
            sample_rate=sample_rate,
            tracer=tracer,
        )

        try:
            for chunk in chunks:
                fragment_id = chunk.id
                tracer.log(
                    "LIVE fragment ready from source",
                    fragment=fragment_id,
                    start_s=chunk.start_s,
                    end_s=chunk.end_s,
                )
                analysis_window_s, target_music_windows = music_window_plan(
                    chunk.end_s - chunk.start_s,
                    fixed_window_s=fixed_music_window_s,
                    windows_per_fragment=effective_music_windows,
                )
                music_window_plans.append(
                    {
                        "fragment": fragment_id,
                        "window_s": analysis_window_s,
                        "count": target_music_windows,
                    }
                )
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
                recorded_chunk_paths.append(chunk.path)

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
                fragment, state = generate_story_fragment_with_gemini(
                    scene_music_segments[0],
                    settings,
                    fragment_index=fragment_id - 1,
                    total_segments=planned_total,
                    words_per_fragment=chunk_words,
                    bible=bible,
                    state=state,
                    previous_text=full_story,
                    is_final=chunk.final_available,
                    music_timeline=scene_music_segments,
                )
                fragment.id = fragment_id
                fragments.append(fragment)
                full_story = "\n\n".join(item.text for item in fragments)
                tracer.log("FRAGMENT story done", fragment=fragment_id, words=len(fragment.text.split()))

                if generate_images:
                    tracer.log("FRAGMENT images start", fragment=fragment_id, count=max_image_assets)
                    image_metadata = generate_images_for_fragments(
                        [fragment],
                        settings,
                        destination / "images",
                        provider=chosen_image_provider,
                        max_assets=max_image_assets,
                        print_estimate=fragment_id == 1,
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

                result = _build_live_result(
                    run_id=run_id,
                    audio_path="live-microphone",
                    music_segments=music_segments,
                    fragments=fragments,
                    full_story=full_story,
                    bible=bible,
                    state=state,
                    source_mode=source_mode,
                    planned_duration_s=duration_seconds,
                    completed_duration_s=fragments[-1].end_s if fragments else 0.0,
                    chunk_s=effective_chunk_s,
                    fixed_music_window_s=fixed_music_window_s,
                    effective_music_windows=effective_music_windows,
                    effective_story_wpm=effective_story_wpm,
                    planned_total=planned_total,
                    image_provider=chosen_image_provider,
                    max_image_assets=max_image_assets,
                    image_totals=image_totals,
                    target_word_counts=target_word_counts,
                    music_window_plans=music_window_plans,
                    settings=settings,
                    debug_artifacts=debug_artifacts,
                    keep_audio_chunks=keep_audio_chunks,
                    visual_delay_s=visual_delay_s,
                    complete=_is_planned_complete(fragments, planned_total, duration_seconds),
                    startup_buffer_fragments=effective_startup_buffer_fragments,
                    recorded_audio_path=recorded_audio_path,
                    recorded_chunks_dir=chunk_dir,
                )
                tracer.log("ARTIFACTS write", fragment=fragment_id, debug=debug_artifacts)
                result.write(destination, debug_artifacts=debug_artifacts, trace_events=tracer.to_json())

                osc_fragment = _fragment_for_live_visual_clock(
                    fragment,
                    visual_started_at=visual_started_at,
                    chunk_s=effective_chunk_s,
                    tracer=tracer,
                )
                tracer.log("OSC send fragment", fragment=fragment_id, final=False)
                osc.send(osc_fragment, final=False)
                if generate_images:
                    tracer.log("OSC send images", fragment=fragment_id)
                    osc.send_images(osc_fragment)
                if visual_started_at is None and (
                    len(fragments) >= effective_startup_buffer_fragments or chunk.final_available
                ):
                    tracer.log("STARTUP buffer ready", fragments=len(fragments))
                    if processing_delay_s > 0:
                        tracer.log("PROCESSING settle", seconds=processing_delay_s)
                        osc.settle(processing_delay_s)
                    tracer.log("OSC prime", fragment=fragments[0].id if fragments else fragment_id)
                    osc.prime(settings.processing_ready_timeout_s)
                    tracer.log("PROCESSING primed", fragment=fragment_id)
                    tracer.log("OSC start")
                    osc.play()
                    visual_started_at = monotonic()
                    visual_delay_s = visual_started_at - source_started_at
                    tracer.log("LIVE visual clock start", delay_s=visual_delay_s)
                if chunk.final_available:
                    osc.finish()
                    stream_finished = True

                if chunk.final_available:
                    break
        except KeyboardInterrupt:
            tracer.log("LIVE interrupted", processed_fragments=len(fragments))
            if fragments and not stream_finished:
                osc.finish()
                stream_finished = True

        if not fragments:
            raise RuntimeError("Live input ended before any audio fragment was processed.")

        if not stream_finished:
            osc.finish()
            stream_finished = True

        recorded_audio_path = _combine_recorded_chunks(recorded_chunk_paths, destination / "recorded_audio.wav", tracer)

        result = _build_live_result(
            run_id=run_id,
            audio_path="live-microphone",
            music_segments=music_segments,
            fragments=fragments,
            full_story=full_story,
            bible=bible,
            state=state,
            source_mode=source_mode,
            planned_duration_s=duration_seconds,
            completed_duration_s=fragments[-1].end_s if fragments else 0.0,
            chunk_s=effective_chunk_s,
            fixed_music_window_s=fixed_music_window_s,
            effective_music_windows=effective_music_windows,
            effective_story_wpm=effective_story_wpm,
            planned_total=planned_total,
            image_provider=chosen_image_provider,
            max_image_assets=max_image_assets,
            image_totals=image_totals,
            target_word_counts=target_word_counts,
            music_window_plans=music_window_plans,
            settings=settings,
            debug_artifacts=debug_artifacts,
            keep_audio_chunks=keep_audio_chunks,
            visual_delay_s=visual_delay_s,
            complete=_is_planned_complete(fragments, planned_total, duration_seconds),
            startup_buffer_fragments=effective_startup_buffer_fragments,
            recorded_audio_path=recorded_audio_path,
            recorded_chunks_dir=chunk_dir,
        )

        if settings.storage_bucket:
            tracer.log("STORAGE upload start", bucket=settings.storage_bucket)
            result.metadata["gcs_uri"] = upload_directory_to_gcs(
                local_dir=destination,
                bucket_name=settings.storage_bucket,
                prefix=f"runs/{run_id}",
            )
            tracer.log("STORAGE upload done", uri=result.metadata["gcs_uri"])

        tracer.log("LIVE run complete", id=run_id, fragments=len(fragments), complete=result.metadata["complete"])
        result.write(destination, debug_artifacts=debug_artifacts, trace_events=tracer.to_json())
        return result
    finally:
        pass


def _record_live_chunks(
    output_dir: Path,
    *,
    chunk_s: float,
    planned_duration_s: float,
    planned_total: int,
    input_device: str | None,
    sample_rate: int,
    tracer: PipelineTracer,
) -> Iterator[LiveAudioChunk]:
    queue: Queue[LiveAudioChunk | BaseException | None] = Queue()
    stop_event = Event()
    thread = Thread(
        target=_recording_worker,
        args=(
            queue,
            stop_event,
            output_dir,
            chunk_s,
            planned_duration_s,
            planned_total,
            input_device,
            sample_rate,
            tracer,
        ),
        daemon=True,
    )
    thread.start()
    try:
        while True:
            item = queue.get()
            if item is None:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        stop_event.set()
        thread.join(timeout=2.0)


def _recording_worker(
    queue: Queue[LiveAudioChunk | BaseException | None],
    stop_event: Event,
    output_dir: Path,
    chunk_s: float,
    planned_duration_s: float,
    planned_total: int,
    input_device: str | None,
    sample_rate: int,
    tracer: PipelineTracer,
) -> None:
    try:
        import sounddevice as sd
        import soundfile as sf

        output_dir.mkdir(parents=True, exist_ok=True)
        channels = 1
        device = _parse_sounddevice_device(input_device)
        for index in range(planned_total):
            if stop_event.is_set():
                break
            start_s = index * chunk_s
            remaining_s = planned_duration_s - start_s
            if remaining_s <= 0:
                break
            duration_s = min(chunk_s, remaining_s)
            frames = max(1, round(duration_s * sample_rate))
            path = output_dir / f"segment_{index + 1:03d}.wav"
            tracer.log("LIVE record start", fragment=index + 1, seconds=duration_s, input_device=input_device)
            data = sd.rec(frames, samplerate=sample_rate, channels=channels, dtype="float32", device=device)
            sd.wait()
            if stop_event.is_set():
                break
            sf.write(str(path), data, sample_rate, subtype="PCM_16")
            tracer.log("LIVE record done", fragment=index + 1, path=path)
            queue.put(
                LiveAudioChunk(
                    id=index + 1,
                    path=path,
                    start_s=start_s,
                    end_s=start_s + duration_s,
                    final_available=index + 1 == planned_total or start_s + duration_s >= planned_duration_s,
                )
            )
    except BaseException as exc:
        queue.put(exc)
    finally:
        queue.put(None)


def _ensure_microphone_dependencies() -> None:
    try:
        import sounddevice  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Microphone mode requires the `sounddevice` package. Install project dependencies, "
            "then retry `run-live`."
        ) from exc


def list_audio_input_devices() -> list[str]:
    _ensure_microphone_dependencies()
    import sounddevice as sd

    devices = sd.query_devices()
    lines: list[str] = []
    for index, device in enumerate(devices):
        max_inputs = int(device.get("max_input_channels", 0))
        if max_inputs <= 0:
            continue
        default_rate = device.get("default_samplerate", "")
        lines.append(f"{index}: {device.get('name', 'unknown')} ({max_inputs} input channel(s), {default_rate} Hz)")
    return lines


def test_audio_input_device(
    *,
    input_device: str | None = None,
    sample_rate: int = 44_100,
    seconds: float = 3.0,
) -> dict[str, float]:
    _ensure_microphone_dependencies()
    import numpy as np
    import sounddevice as sd

    duration_s = max(0.1, float(seconds))
    data = sd.rec(
        int(sample_rate * duration_s),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=_parse_sounddevice_device(input_device),
    )
    sd.wait()
    return {
        "duration_s": duration_s,
        "rms": float(np.sqrt(np.mean(data**2))),
        "peak": float(np.max(np.abs(data))),
    }


def _parse_sounddevice_device(value: str | None) -> int | str | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    return int(text) if text.isdigit() else text


def _combine_recorded_chunks(
    chunk_paths: list[Path],
    output_path: Path,
    tracer: PipelineTracer,
) -> Path | None:
    if not chunk_paths:
        return None
    try:
        import soundfile as sf

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with sf.SoundFile(str(chunk_paths[0]), mode="r") as first_file:
            samplerate = int(first_file.samplerate)
            channels = int(first_file.channels)
        with sf.SoundFile(str(output_path), mode="w", samplerate=samplerate, channels=channels, subtype="PCM_16") as out_file:
            for chunk_path in chunk_paths:
                with sf.SoundFile(str(chunk_path), mode="r") as in_file:
                    _write_soundfile_data(in_file, out_file)
        tracer.log("LIVE recorded audio saved", path=output_path)
        return output_path
    except Exception as exc:
        tracer.log("LIVE recorded audio combine failed", error=str(exc), chunks=len(chunk_paths))
        return None


def _fragment_for_live_visual_clock(
    fragment: StoryFragment,
    *,
    visual_started_at: float | None,
    chunk_s: float,
    tracer: PipelineTracer,
) -> StoryFragment:
    if visual_started_at is None or fragment.start_s is None or fragment.end_s is None:
        return fragment
    elapsed_s = monotonic() - visual_started_at
    remaining_s = float(fragment.end_s) - elapsed_s
    minimum_display_s = min(chunk_s, max(6.0, chunk_s * 0.75))
    if remaining_s >= minimum_display_s:
        return fragment
    start_s = elapsed_s + 0.05
    end_s = start_s + max(0.1, chunk_s)
    tracer.log(
        "OSC reschedule late fragment",
        fragment=fragment.id,
        original_start_s=fragment.start_s,
        original_end_s=fragment.end_s,
        new_start_s=start_s,
        new_end_s=end_s,
        remaining_s=remaining_s,
    )
    return replace(fragment, start_s=start_s, end_s=end_s)


def _write_soundfile_data(in_file, out_file) -> None:
    while True:
        data = in_file.read(65_536, dtype="float32", always_2d=True)
        if len(data) == 0:
            break
        out_file.write(data)


def _build_live_result(
    *,
    run_id: str,
    audio_path: str,
    music_segments: list[MusicSegment],
    fragments: list[StoryFragment],
    full_story: str,
    bible: dict[str, object],
    state: dict[str, object],
    source_mode: str,
    planned_duration_s: float,
    completed_duration_s: float | None,
    chunk_s: float,
    fixed_music_window_s: float | None,
    effective_music_windows: int,
    effective_story_wpm: float,
    planned_total: int,
    image_provider: str,
    max_image_assets: int,
    image_totals: dict[str, int | float],
    target_word_counts: list[int],
    music_window_plans: list[dict[str, object]],
    settings: BardSettings,
    debug_artifacts: bool,
    keep_audio_chunks: bool,
    visual_delay_s: float | None,
    complete: bool,
    startup_buffer_fragments: int,
    recorded_audio_path: Path | None,
    recorded_chunks_dir: Path,
) -> PipelineResult:
    return PipelineResult(
        run_id=run_id,
        audio_path=audio_path,
        music_segments=music_segments,
        fragments=fragments,
        full_story=full_story,
        story_bible=bible,
        story_state=state,
        metadata={
            "execution_mode": "live",
            "source_mode": source_mode,
            "complete": complete,
            "duration_s": completed_duration_s,
            "planned_duration_s": planned_duration_s,
            "planned_fragment_count": planned_total,
            "completed_fragment_count": len(fragments),
            "chunk_s": chunk_s,
            "story_scene_s": chunk_s,
            "music_window_s": fixed_music_window_s,
            "music_window_mode": "fixed" if fixed_music_window_s is not None else "derived-per-fragment",
            "music_windows_per_fragment": effective_music_windows,
            "music_window_plans": music_window_plans,
            "music_segment_count": len(music_segments),
            "story_scene_count": len(fragments),
            "target_word_counts": target_word_counts,
            "processing_slide_duration_s": chunk_s,
            "visual_delay_s": visual_delay_s,
            "startup_buffer_fragments": startup_buffer_fragments,
            "recorded_audio_path": str(recorded_audio_path) if recorded_audio_path else None,
            "recorded_audio_chunks_dir": str(recorded_chunks_dir),
            "recorded_audio_chunks_saved": recorded_chunks_dir.exists(),
            "audio_provider": "gemini",
            "story_provider": "vertex",
            "story_language": settings.story_language,
            "story_level": settings.story_level,
            "story_wpm": effective_story_wpm,
            "live_story_scene_s": settings.live_story_scene_s,
            "image_provider": image_provider,
            "playback_mode": "none",
            "debug_artifacts": debug_artifacts,
            "keep_audio_chunks": keep_audio_chunks,
            "estimated_api_calls": {
                "audio_analysis": planned_total,
                "music_to_story_llm": 0,
                "story_bible": 1,
                "story_scene_generation": planned_total,
                "image_generation_or_retrieval": planned_total * max_image_assets if image_provider != "none" else 0,
            },
            **image_totals,
        },
    )


def _ready_image_count(fragment: StoryFragment) -> int:
    return sum(1 for asset in fragment.image_assets if asset.local_path and asset.status in {"generated", "retrieved"})


def _is_planned_complete(
    fragments: list[StoryFragment],
    planned_total: int,
    planned_duration_s: float,
) -> bool:
    if len(fragments) < planned_total:
        return False
    last_end = fragments[-1].end_s
    return bool(last_end is not None and float(last_end) >= planned_duration_s - 0.001)


def _processing_visible_path(container_path: Path) -> str:
    import os

    host_workspace = os.environ.get("BARD_HOST_WORKSPACE")
    container_workspace = Path(os.environ.get("BARD_CONTAINER_WORKSPACE", "/workspace"))
    if not host_workspace:
        return container_path.as_posix()
    try:
        relative = container_path.resolve().relative_to(container_workspace.resolve())
    except ValueError:
        return container_path.as_posix()
    host_root = host_workspace.replace("\\", "/").rstrip("/")
    return f"{host_root}/{relative.as_posix()}"
