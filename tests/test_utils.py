from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import struct
import wave

from bard_core.utils import (
    compute_chunk_and_words,
    detect_audio_duration,
    estimate_segment_count,
    story_chunk_seconds,
    target_story_words,
)


class AudioTimingTests(TestCase):
    def test_wav_duration_drives_chunk_and_segment_count(self) -> None:
        with TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "ten-seconds.wav"
            with wave.open(str(audio_path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(8_000)
                output.writeframes(struct.pack("<h", 0) * 80_000)

            duration = detect_audio_duration(audio_path)
            chunk_s, words = compute_chunk_and_words(duration, "1/5", 180, 30)

        self.assertAlmostEqual(duration or 0, 10.0, places=2)
        self.assertEqual(chunk_s, 2.0)
        self.assertEqual(words, 6)
        self.assertEqual(estimate_segment_count(duration, chunk_s), 5)

    def test_long_chunks_are_not_capped_at_twenty_story_words(self) -> None:
        chunk_s, words = compute_chunk_and_words(300, "1/5", 180, 30)

        self.assertEqual(chunk_s, 60.0)
        self.assertEqual(words, 150)

    def test_story_word_budget_reserves_animation_and_reading_time(self) -> None:
        self.assertEqual(target_story_words(20, 120, 0.72), 29)
        self.assertEqual(target_story_words(2, 120, 0.72), 12)
        self.assertAlmostEqual(story_chunk_seconds(32, 120, 0.72), 22.222, places=3)
