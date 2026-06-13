from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bard_core.config import BardSettings
from bard_core.contracts import ImageAsset, PipelineResult, StoryFragment, story_fragments_from_json
from bard_core.cli import (
    fake_story_card_options,
    fake_story_fragments,
    image_manifest_from_fragments,
    normalize_argv,
    scene_cards_from_fragments,
)
from bard_core.images.generator import generate_images_for_fragments
from bard_core.images.openverse_provider import _query_for_asset
from bard_core.images.planner import ensure_fragment_image_assets
from bard_core.transport.osc_sender import send_fragments_to_processing


def test_settings(tmp_path: Path) -> BardSettings:
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
        max_image_assets=3,
        image_aspect_ratio="1:1",
        image_timeout_s=10,
        replicate_api_token="token",
        replicate_model="black-forest-labs/flux-schnell",
        imagen_model="imagen-4.0-fast-generate-001",
        imagen_location="europe-west1",
        osc_host="127.0.0.1",
        osc_port=5005,
        default_chunk_s=30,
        default_wpm=180,
        use_4bit=False,
    )


class ImageAssetTests(TestCase):
    def test_asset_planning_preserves_single_image_prompt(self) -> None:
        fragment = StoryFragment(
            id=1,
            mood="CALM",
            text="A cat waits under the sun.",
            image_prompt="A rough black cat silhouette on a dark background.",
            visual_motif="cat",
        )

        assets = ensure_fragment_image_assets(fragment, max_assets=3)

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].role, "background")
        self.assertEqual(assets[0].label, "cat")
        self.assertEqual(assets[0].prompt, fragment.image_prompt)
        self.assertIn("text", assets[0].negative_prompt or "")

    def test_fake_story_card_has_layered_assets(self) -> None:
        fragments = fake_story_fragments()

        self.assertEqual(len(fragments), 1)
        self.assertEqual([asset.role for asset in fragments[0].image_assets], ["subject", "background", "symbol"])
        self.assertIn("cat", fragments[0].image_assets[0].label)

    def test_fake_story_card_catalog_selects_named_card(self) -> None:
        self.assertIn("boat-fog-lantern", fake_story_card_options())

        fragments = fake_story_fragments("boat-fog-lantern")

        self.assertEqual(fragments[0].visual_motif, "boat in fog with lantern")
        self.assertEqual([asset.label for asset in fragments[0].image_assets], ["wooden boat", "foggy river", "warm lantern"])

    def test_fake_story_card_unknown_name_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown fake card"):
            fake_story_fragments("missing-card")

    def test_empty_env_file_arg_does_not_eat_command(self) -> None:
        argv = normalize_argv(
            [
                "--env-file",
                "generate-images",
                "--fake-card",
                "--fake-card-name",
                "cat-wood-sun",
                "--image-provider",
                "imagen",
            ]
        )

        self.assertEqual(argv[0], "generate-images")
        self.assertIn("cat-wood-sun", argv)

    def test_image_only_helpers_emit_scene_cards_and_manifest(self) -> None:
        fragments = fake_story_fragments("cat-wood-sun")
        fragments[0].image_assets[0].status = "failed"
        fragments[0].image_assets[0].error = "download failed"

        scene_cards = scene_cards_from_fragments(fragments)
        manifest = image_manifest_from_fragments(fragments, {"image_provider": "openverse"})

        self.assertEqual(scene_cards[0]["story_text"], fragments[0].text)
        self.assertEqual(scene_cards[0]["image_assets"][0]["label"], "black cat")
        self.assertEqual(manifest["images"][0]["status"], "failed")
        self.assertEqual(manifest["images"][0]["error"], "download failed")

    def test_provider_dispatch_updates_replicate_asset(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragment = StoryFragment(
                id=1,
                mood="CALM",
                text="A cat waits.",
                image_assets=[ImageAsset(role="subject", label="cat", prompt="cat")],
            )

            def fake_generate(asset: ImageAsset, output_base_path: Path, settings: BardSettings) -> ImageAsset:
                output_path = output_base_path.with_suffix(".png")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"fake")
                asset.status = "generated"
                asset.local_path = str(output_path)
                asset.provider = "replicate"
                asset.model = settings.replicate_model
                return asset

            with patch("bard_core.images.generator.generate_replicate_image", side_effect=fake_generate):
                metadata = generate_images_for_fragments(
                    [fragment],
                    test_settings(tmp_path),
                    tmp_path / "images",
                    provider="replicate",
                    max_assets=3,
                    print_estimate=False,
                )

        self.assertEqual(metadata["image_provider"], "replicate")
        self.assertEqual(metadata["generated_image_assets"], 1)
        self.assertEqual(fragment.image_assets[0].status, "generated")
        self.assertEqual(fragment.image_assets[0].model, "black-forest-labs/flux-schnell")

    def test_openverse_query_uses_clean_label_only(self) -> None:
        query = _query_for_asset(
            ImageAsset(
                role="subject",
                label="black cat",
                prompt="A simple recognizable black cat silhouette on a dark background.",
            )
        )

        self.assertEqual(query, "black cat")

    def test_failed_provider_marks_asset_without_crashing(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragment = StoryFragment(
                id=1,
                mood="CALM",
                text="A cat waits.",
                image_assets=[ImageAsset(role="subject", label="cat", prompt="cat")],
            )
            with patch("bard_core.images.generator.generate_replicate_image", side_effect=RuntimeError("no token")):
                metadata = generate_images_for_fragments(
                    [fragment],
                    test_settings(tmp_path),
                    tmp_path / "images",
                    provider="replicate",
                    max_assets=3,
                    print_estimate=False,
                )

        self.assertEqual(metadata["failed_image_assets"], 1)
        self.assertEqual(fragment.image_assets[0].status, "failed")
        self.assertEqual(fragment.image_assets[0].error, "no token")

    def test_scene_cards_and_story_json_serialize_image_assets(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragment = StoryFragment(
                id=1,
                mood="CALM",
                text="A cat waits.",
                image_assets=[
                    ImageAsset(
                        role="subject",
                        label="cat",
                        prompt="cat",
                        status="generated",
                        local_path=str(tmp_path / "cat.png"),
                    )
                ],
            )
            result = PipelineResult(
                run_id="run",
                audio_path="audio.mp3",
                music_segments=[],
                fragments=[fragment],
                full_story="A cat waits.",
            )
            result.write(tmp_path)

            cards = (tmp_path / "scene_cards.json").read_text(encoding="utf-8")
            self.assertIn('"image_assets"', cards)
            self.assertIn('"story_text": "A cat waits."', cards)

            loaded = story_fragments_from_json(tmp_path / "story.json")
            self.assertEqual(loaded[0].image_assets[0].label, "cat")

    def test_osc_sender_emits_image_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "cat.png"
            image_path.write_bytes(b"fake")
            fragment = StoryFragment(
                id=1,
                mood="CALM",
                text="A cat waits.",
                image_assets=[
                    ImageAsset(
                        role="subject",
                        label="cat",
                        prompt="cat",
                        status="generated",
                        local_path=str(image_path),
                    )
                ],
            )
            sent: list[tuple[str, object]] = []

            class FakeClient:
                def __init__(self, host: str, port: int) -> None:
                    self.host = host
                    self.port = port

                def send_message(self, address: str, payload: object) -> None:
                    sent.append((address, payload))

            fake_pythonosc = SimpleNamespace(udp_client=SimpleNamespace(SimpleUDPClient=FakeClient))
            with patch.dict(sys.modules, {"pythonosc": fake_pythonosc}):
                with patch("bard_core.transport.osc_sender.time.sleep"):
                    send_fragments_to_processing(
                        fragments=[fragment],
                        host="127.0.0.1",
                        port=5005,
                        slide_duration_s=10,
                        start_delay_s=0,
                        include_images=True,
                    )

        image_messages = [payload for address, payload in sent if address == "/image"]
        self.assertEqual(len(image_messages), 1)
        self.assertEqual(image_messages[0][0], 1)
        self.assertEqual(image_messages[0][1], 0)
        self.assertEqual(image_messages[0][2], "subject")
