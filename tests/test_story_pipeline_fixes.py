from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bard_core.config import BardSettings
from bard_core.contracts import MOOD_LABELS, MusicSegment
from bard_core.story.gemini_story import (
    _scene_mood,
    choose_world_profile,
    create_story_bible,
    generate_story_fragment_with_gemini,
)


def make_test_settings(tmp_path: Path) -> BardSettings:
    return BardSettings(
        root_dir=tmp_path,
        output_dir=tmp_path / "runs",
        labelbank_path=tmp_path / "labels.json",
        audio_provider="gemini",
        story_provider="vertex",
        gcp_project_id="project",
        gcp_location="europe-west1",
        vertex_text_model="gemini-2.5-flash",
        vertex_audio_model="gemini-2.5-flash",
        storage_bucket=None,
        local_story_model="mistral",
        image_provider="none",
        max_image_assets=2,
        image_aspect_ratio="1:1",
        image_timeout_s=10,
        image_model="imagen-4.0-fast-generate-001",
        image_location="europe-west1",
        remove_image_background=True,
        background_removal_provider="rembg",
        replicate_api_token=None,
        replicate_model="black-forest-labs/flux-schnell",
        imagen_model="imagen-4.0-fast-generate-001",
        imagen_location="europe-west1",
        osc_host="127.0.0.1",
        osc_port=5005,
        osc_ready_port=5007,
        osc_ready_bind_host="127.0.0.1",
        processing_ready_timeout_s=8,
        default_chunk_s=30,
        default_wpm=180,
        story_wpm=70,
        fragment_target_s=60,
        fragment_min_s=50,
        fragment_max_s=70,
        short_audio_threshold_s=120,
        story_language="English",
        story_level="children",
        text_coverage=0.72,
        target_words_per_fragment=32,
        music_window_s=None,
        music_windows_per_fragment=4,
        story_scene_s=60,
        processing_startup_delay_s=1.5,
        startup_buffer_fragments=2,
        live_story_wpm=70,
        live_music_windows_per_fragment=2,
        live_story_scene_s=30,
        live_startup_buffer_fragments=2,
        use_4bit=False,
    )


def test_processing_mood_table_exactly_matches_python_labels() -> None:
    root = Path(__file__).resolve().parents[1]
    mood_manager = (root / "apps" / "processing" / "bard_story_visuals" / "MoodManager.pde").read_text(
        encoding="utf-8"
    )
    processing_labels = re.findall(r'moods\.put\("([^"]+)"', mood_manager)

    assert processing_labels == MOOD_LABELS
    for old_label in ("ENERGETIC", "SOLO", "DEEP", "DISSONANT"):
        assert old_label not in processing_labels
    assert "src/bard_core/contracts.py::MOOD_LABELS" in mood_manager


def test_old_mood_labels_do_not_remain_in_generation_logic() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "src" / "bard_core" / "audio" / "gemini_provider.py",
        root / "src" / "bard_core" / "story" / "gemini_story.py",
        root / "src" / "bard_core" / "story" / "local_mistral.py",
        root / "src" / "bard_core" / "legacy" / "story" / "story_from_description.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for old_label in ("ENERGETIC", "SOLO", "DEEP", "DISSONANT"):
        assert old_label not in combined


def test_scene_mood_uses_dominant_valid_audio_mood_first() -> None:
    timeline = [
        MusicSegment(id=1, start_s=0, end_s=5, music_prompt="calm", mood_hint="CALM"),
        MusicSegment(id=2, start_s=5, end_s=25, music_prompt="uneasy", mood_hint="ANXIOUS"),
        MusicSegment(id=3, start_s=25, end_s=90, music_prompt="bad", mood_hint="UNKNOWN"),
    ]

    assert _scene_mood(timeline, "BRIGHT") == "ANXIOUS"
    assert _scene_mood([], "BRIGHT") == "BRIGHT"
    assert _scene_mood([], "MYSTERY") == "CALM"


def test_world_profile_selection_is_deterministic_and_descriptor_driven() -> None:
    electronic = [
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

    assert choose_world_profile(electronic) == choose_world_profile(electronic)
    assert choose_world_profile(electronic)["id"] != choose_world_profile(bright)["id"]


def test_story_bible_prompt_includes_world_profile_and_not_fairy_tale_default() -> None:
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
    assert "Use this world as the main setting." in captured["prompt"]
    assert "Characters must fit this cast style." in captured["prompt"]
    assert "Names must fit this name style." in captured["prompt"]
    assert "fairy tale" not in captured["prompt"].lower()


def test_story_fragment_filters_symbol_assets_and_prompt_requests_two_roles() -> None:
    captured: dict[str, str] = {}

    def fake_generate_json(prompt, schema, settings, *, temperature):
        captured["prompt"] = prompt
        return {
            "mood": "BRIGHT",
            "text": "The brass helper opened the signal door.",
            "narrative_phase": "opening",
            "story_event": "The helper opens the door.",
            "display_text": "The signal door opens.",
            "keywords": ["door", "signal"],
            "image_prompt": "signal door",
            "visual_motif": "signal door",
            "palette": "copper and blue",
            "motion": "gentle rise",
            "image_assets": [
                {"role": "background", "label": "tower", "prompt": "radio tower", "negative_prompt": "text"},
                {"role": "subject", "label": "helper", "prompt": "brass helper", "negative_prompt": "text"},
                {"role": "symbol", "label": "spark", "prompt": "spark", "negative_prompt": "text"},
            ],
            "state": {
                "location": "tower",
                "protagonist_status": "moving",
                "antagonist_status": "waiting",
                "helper_status": "helping",
                "magical_object_status": "none",
                "last_event": "door opened",
                "unresolved_threads": [],
                "facts_to_preserve": [],
            },
        }

    bible = {
        "protagonist": "Lumo",
        "protagonist_visual_identity": "small brass signal mask with blue glass eyes",
        "setting": "radio tower",
        "beat_plan": ["open"],
        "world_profile": {
            "setting": "a radio tower",
            "cast_style": "signal spirits and helpful machines",
            "visual_palette": "midnight blue and copper",
            "name_style": "callsigns",
            "avoid": "woodland defaults",
        },
    }
    timeline = [
        MusicSegment(id=1, start_s=0, end_s=10, music_prompt="bright", mood_hint="BRIGHT"),
        MusicSegment(id=2, start_s=10, end_s=30, music_prompt="tense", mood_hint="ANXIOUS"),
    ]

    with TemporaryDirectory() as tmp:
        with patch("bard_core.story.gemini_story._generate_json", side_effect=fake_generate_json):
            fragment, _ = generate_story_fragment_with_gemini(
                timeline[0],
                make_test_settings(Path(tmp)),
                fragment_index=0,
                total_segments=1,
                words_per_fragment=30,
                bible=bible,
                state={},
                previous_text="",
                is_final=True,
                music_timeline=timeline,
            )

    assert "Produce exactly two image assets in this order: background, subject." in captured["prompt"]
    assert "Symbol prompt" not in captured["prompt"]
    assert [asset.role for asset in fragment.image_assets] == ["background", "subject"]
    assert fragment.mood == "ANXIOUS"
