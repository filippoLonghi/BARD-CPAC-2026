from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bard_core.config import (
    DEFAULT_FRAGMENT_MAX_S,
    DEFAULT_FRAGMENT_MIN_S,
    DEFAULT_FRAGMENT_TARGET_S,
    DEFAULT_MUSIC_WINDOWS_PER_FRAGMENT,
    DEFAULT_SHORT_AUDIO_THRESHOLD_S,
    DEFAULT_STORY_WPM,
    BardSettings,
)
from bard_core.audio.gemini_provider import SEGMENT_SCHEMA


class ConfigTests(TestCase):
    def test_active_timing_defaults_are_project_defaults(self) -> None:
        env = {
            "PATH": "",
            "PYTHONPATH": "",
        }

        with patch.dict("os.environ", env, clear=True):
            settings = BardSettings.from_env()

        self.assertEqual(settings.audio_provider, "gemini")
        self.assertEqual(settings.story_provider, "vertex")
        self.assertEqual(settings.story_wpm, DEFAULT_STORY_WPM)
        self.assertEqual(settings.fragment_target_s, DEFAULT_FRAGMENT_TARGET_S)
        self.assertEqual(settings.fragment_min_s, DEFAULT_FRAGMENT_MIN_S)
        self.assertEqual(settings.fragment_max_s, DEFAULT_FRAGMENT_MAX_S)
        self.assertEqual(settings.short_audio_threshold_s, DEFAULT_SHORT_AUDIO_THRESHOLD_S)
        self.assertEqual(settings.music_windows_per_fragment, DEFAULT_MUSIC_WINDOWS_PER_FRAGMENT)

    def test_audio_schema_does_not_require_model_generated_ids_or_old_optional_fields(self) -> None:
        segment_schema = SEGMENT_SCHEMA["properties"]["segments"]["items"]

        self.assertNotIn("id", segment_schema["properties"])
        self.assertNotIn("id", segment_schema["required"])
        self.assertNotIn("confidence", segment_schema["required"])
        self.assertNotIn("tempo_bpm", segment_schema["required"])
