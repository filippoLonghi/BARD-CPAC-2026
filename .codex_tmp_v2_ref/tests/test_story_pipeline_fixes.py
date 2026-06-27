from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bard_core.config import BardSettings
from bard_core.contracts import MOOD_LABELS, MusicSegment, mood_cues_from_music_segments
from bard_core.story.gemini_story import choose_world_profile, create_story_bible, _scene_mood


def make_test_settings(tmp_path: Path) -> BardSettings:
    return BardSettings(
        root_dir=tmp_path,
        output_dir=tmp_path / "runs",
        labelbank_path=tmp_path / "labels.json",
        audio_provider="gemini",
        story_provider="vertex",
        gcp_project_id="project",
        gcp_location="global",
        vertex_text_model="gemini-2.5-flash",
        vertex_audio_model="gemini-2.5-flash",
        storage_bucket=None,
        local_story_model="mistral",
        image_provider="none",
        max_image_assets=3,
        image_aspect_ratio="1:1",
        image_timeout_s=10,
        image_model="gemini-2.5-flash-image",
        image_location="global",
        remove_image_background=True,
        background_removal_provider="rembg",
        replicate_api_token=None,
        replicate_model="black-forest-labs/flux-schnell",
        imagen_model="gemini-2.5-flash-image",
        imagen_location="global",
        osc_host="127.0.0.1",
        osc_port=5005,
        osc_ready_port=5007,
        osc_ready_bind_host="127.0.0.1",
        processing_ready_timeout_s=8,
        default_chunk_s=30,
        default_wpm=180,
        story_language="English",
        story_level="children",
        text_coverage=0.72,
        target_words_per_fragment=32,
        music_window_s=15,
        story_scene_s=60,
        processing_startup_delay_s=1.5,
        use_4bit=False,
    )


def test_processing_mood_table_contains_python_labels_and_aliases() -> None:
    mood_manager = (
        Path(__file__).resolve().parents[1] / "apps" / "processing" / "bard_story_visuals" / "MoodManager.pde"
    ).read_text(encoding="utf-8")

    for label in MOOD_LABELS:
        assert f'moods.put("{label}"' in mood_manager
    for alias in ("DARK", "DENSE", "RISING TENSION", "RISING_TENSION", "RELEASE", "BRIGHT", "SPARSE"):
        assert f'moods.put("{alias}"' in mood_manager
    assert "src/bard_core/contracts.py::MOOD_LABELS" in mood_manager


def test_scene_mood_uses_dominant_valid_audio_mood() -> None:
    timeline = [
        MusicSegment(id=1, start_s=0, end_s=5, music_prompt="bright", mood_hint="ENERGETIC"),
        MusicSegment(id=2, start_s=5, end_s=25, music_prompt="uneasy", mood_hint="ANXIOUS"),
        MusicSegment(id=3, start_s=25, end_s=30, music_prompt="bad", mood_hint="UNKNOWN"),
    ]

    assert _scene_mood(timeline, "CALM") == "ANXIOUS"
    assert _scene_mood([], "DEEP") == "DEEP"
    assert _scene_mood([], "MYSTERY") == "CALM"


def test_music_mood_cues_preserve_fine_audio_changes() -> None:
    timeline = [
        MusicSegment(id=1, start_s=0, end_s=15, music_prompt="solo", mood_hint="SOLO"),
        MusicSegment(id=2, start_s=15, end_s=30, music_prompt="deep", mood_hint="DEEP"),
        MusicSegment(id=3, start_s=30, end_s=45, music_prompt="bright", mood_hint="ENERGETIC"),
        MusicSegment(id=4, start_s=45, end_s=60, music_prompt="brighter", mood_hint="ENERGETIC"),
    ]

    assert mood_cues_from_music_segments(timeline, start_s=0, end_s=60) == [
        {"mood": "SOLO", "start_s": 0.0, "end_s": 15.0},
        {"mood": "DEEP", "start_s": 15.0, "end_s": 30.0},
        {"mood": "ENERGETIC", "start_s": 30.0, "end_s": 60.0},
    ]


def test_processing_accepts_mood_cues_and_snaps_words_for_reading() -> None:
    root = Path(__file__).resolve().parents[1]
    osc_handler = (root / "apps" / "processing" / "bard_story_visuals" / "OscHandler.pde").read_text(
        encoding="utf-8"
    )
    director = (root / "apps" / "processing" / "bard_story_visuals" / "StoryDirector.pde").read_text(
        encoding="utf-8"
    )
    sentence_display = (
        root / "apps" / "processing" / "bard_story_visuals" / "SentenceDisplay.pde"
    ).read_text(encoding="utf-8")

    assert 'message.checkAddrPattern("/mood")' in osc_handler
    assert "updateTimedMood()" in director
    assert "word.lockToTarget();" in sentence_display


def test_world_profile_selection_is_deterministic() -> None:
    segments = [
        MusicSegment(
            id=1,
            music_prompt="glitchy synthetic pulse with metallic percussion",
            valence=0.1,
            arousal=0.9,
            tension=0.8,
            texture="industrial electronic layers",
            instruments=["synthesizer", "drum machine"],
            genre_candidates=["techno"],
        )
    ]

    assert choose_world_profile(segments) == choose_world_profile(segments)


def test_world_profile_changes_for_different_music_descriptors() -> None:
    bright = [
        MusicSegment(
            id=1,
            music_prompt="fast joyful brass and clapping festival rhythm",
            valence=0.8,
            arousal=0.9,
            tension=0.2,
            instruments=["brass", "hand claps"],
            genre_candidates=["festival music"],
        )
    ]
    dark = [
        MusicSegment(
            id=1,
            music_prompt="slow cold minor drones with suspended pressure",
            valence=-0.8,
            arousal=0.2,
            tension=0.8,
            texture="sparse icy drone",
            genre_candidates=["ambient"],
        )
    ]

    assert choose_world_profile(bright)["id"] != choose_world_profile(dark)["id"]


def test_story_bible_prompt_includes_world_profile_and_anti_woodland_constraint() -> None:
    captured: dict[str, str] = {}

    def fake_generate_json(prompt, schema, settings, *, temperature):
        captured["prompt"] = prompt
        return {
            "title": "The Signal Door",
            "protagonist": "Lumo",
            "protagonist_trait": "curious",
            "protagonist_flaw": "rushes",
            "protagonist_goal": "repair the beacon",
            "protagonist_visual_identity": "small brass signal mask with blue glass eyes",
            "antagonist": "The Static Gate",
            "antagonist_motive": "wants quiet",
            "antagonist_visual_identity": "tall folded antenna gate with red warning lights",
            "helper": "Pip Relay",
            "helper_visual_identity": "round radio cart with copper wheels",
            "setting": "a radio tower",
            "magical_rule": "signals become bridges when shared kindly",
            "central_problem": "the beacon is silent",
            "stakes": "messages cannot find homes",
            "moral": "listen before fixing",
            "ending_target": "the beacon returns",
            "beat_plan": ["start", "finish"],
        }

    segments = [
        MusicSegment(
            id=1,
            music_prompt="synthetic radio static and pulsing signals",
            valence=0.1,
            arousal=0.7,
            tension=0.5,
            texture="electronic",
        )
    ]
    with TemporaryDirectory() as tmp:
        with patch("bard_core.story.gemini_story._generate_json", side_effect=fake_generate_json):
            bible = create_story_bible(segments, make_test_settings(Path(tmp)), 2)

    assert bible["world_profile"]["id"] in captured["prompt"]
    assert "symbolic adventure story for children aged 6-10" in captured["prompt"]
    assert "Do not default to woodland, meadow, fairy forest, insects, foxes, cats, owls" in captured["prompt"]
    assert "robots, machines, masks, vehicles, elemental spirits" in captured["prompt"]
