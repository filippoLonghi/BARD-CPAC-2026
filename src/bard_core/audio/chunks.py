from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math


@dataclass(frozen=True)
class AudioChunk:
    id: int
    path: Path
    start_s: float
    end_s: float


@dataclass(frozen=True)
class AudioChunkPlan:
    id: int
    start_frame: int
    end_frame: int
    sample_rate: int
    start_s: float
    end_s: float


def split_audio_file(
    audio_path: Path,
    output_dir: Path,
    *,
    chunk_s: float | None = None,
    fragment_count: int | None = None,
) -> list[AudioChunk]:
    plans = plan_audio_chunks(audio_path, chunk_s=chunk_s, fragment_count=fragment_count)
    return [extract_audio_chunk(audio_path, output_dir, plan) for plan in plans]


def plan_audio_chunks(
    audio_path: Path,
    *,
    chunk_s: float | None = None,
    fragment_count: int | None = None,
) -> list[AudioChunkPlan]:
    try:
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Audio chunking requires `pip install soundfile`.") from exc

    if fragment_count is not None and fragment_count < 1:
        raise ValueError("fragment_count must be at least 1.")
    if chunk_s is not None and chunk_s <= 0:
        raise ValueError("chunk_s must be greater than 0.")
    if fragment_count is None and chunk_s is None:
        raise ValueError("Choose chunk_s or fragment_count.")

    resolved = audio_path.expanduser().resolve()
    info = sf.info(str(resolved))
    total_frames = int(info.frames)
    sample_rate = int(info.samplerate)
    duration_s = total_frames / float(sample_rate)
    if fragment_count is not None:
        frames_per_chunk = max(1, math.ceil(total_frames / fragment_count))
    else:
        frames_per_chunk = max(1, round(float(chunk_s) * sample_rate))

    plans: list[AudioChunkPlan] = []
    chunk_id = 1
    start_frame = 0
    while start_frame < total_frames:
        frame_count = min(frames_per_chunk, total_frames - start_frame)
        end_frame = start_frame + frame_count
        plans.append(
            AudioChunkPlan(
                id=chunk_id,
                start_frame=start_frame,
                end_frame=end_frame,
                sample_rate=sample_rate,
                start_s=start_frame / float(sample_rate),
                end_s=min(duration_s, end_frame / float(sample_rate)),
            )
        )
        start_frame = end_frame
        chunk_id += 1
    return plans


def extract_audio_chunk(audio_path: Path, output_dir: Path, plan: AudioChunkPlan) -> AudioChunk:
    try:
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Audio chunking requires `pip install soundfile`.") from exc

    resolved = audio_path.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = output_dir / f"segment_{plan.id:03d}.wav"
    with sf.SoundFile(str(resolved), "r") as source:
        source.seek(plan.start_frame)
        samples = source.read(plan.end_frame - plan.start_frame, dtype="float32", always_2d=True)
        sf.write(str(chunk_path), samples, plan.sample_rate, subtype="PCM_16")
    return AudioChunk(id=plan.id, path=chunk_path, start_s=plan.start_s, end_s=plan.end_s)


def convert_audio_to_wav(audio_path: Path, output_path: Path) -> Path:
    """Create a PCM WAV that Processing/Java Sound can play without codec plugins."""
    try:
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Audio conversion requires `pip install soundfile`.") from exc

    resolved = audio_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sf.SoundFile(str(resolved), "r") as source:
        with sf.SoundFile(
            str(output_path),
            "w",
            samplerate=source.samplerate,
            channels=source.channels,
            format="WAV",
            subtype="PCM_16",
        ) as target:
            while True:
                block = source.read(65_536, dtype="float32", always_2d=True)
                if len(block) == 0:
                    break
                target.write(block)
    return output_path.resolve()
