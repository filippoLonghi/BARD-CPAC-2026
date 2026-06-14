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


def split_audio_file(
    audio_path: Path,
    output_dir: Path,
    *,
    chunk_s: float | None = None,
    fragment_count: int | None = None,
) -> list[AudioChunk]:
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

    output_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[AudioChunk] = []
    with sf.SoundFile(str(resolved), "r") as source:
        chunk_id = 1
        start_frame = 0
        while start_frame < total_frames:
            source.seek(start_frame)
            frame_count = min(frames_per_chunk, total_frames - start_frame)
            samples = source.read(frame_count, dtype="float32", always_2d=True)
            chunk_path = output_dir / f"segment_{chunk_id:03d}.wav"
            sf.write(str(chunk_path), samples, sample_rate, subtype="PCM_16")
            end_frame = start_frame + frame_count
            chunks.append(
                AudioChunk(
                    id=chunk_id,
                    path=chunk_path,
                    start_s=start_frame / float(sample_rate),
                    end_s=min(duration_s, end_frame / float(sample_rate)),
                )
            )
            start_frame = end_frame
            chunk_id += 1
    return chunks
