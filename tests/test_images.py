from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import socket
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bard_core.config import BardSettings
from bard_core.contracts import ImageAsset, PipelineResult, StoryFragment, story_fragments_from_json
from bard_core.cli import (
    fake_story_card_options,
    fake_story_fragments,
    image_manifest_from_fragments,
    normalize_argv,
    scene_cards_from_fragments,
    story_json_from_fragments,
)
from bard_core.images.generator import generate_images_for_fragments
from bard_core.images.openverse_provider import _query_candidates, _query_for_asset
from bard_core.images.planner import ensure_fragment_image_assets
from bard_core.transport.osc_sender import ProcessingOscStream, prepare_audio_playback, send_fragments_to_processing


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


class ImageAssetTests(TestCase):
    def test_asset_planning_expands_single_prompt_to_three_visual_roles(self) -> None:
        fragment = StoryFragment(
            id=1,
            mood="CALM",
            text="A cat waits under the sun.",
            image_prompt="A rough black cat silhouette on a dark background.",
            visual_motif="cat",
        )

        assets = ensure_fragment_image_assets(fragment, max_assets=3)

        self.assertEqual(len(assets), 3)
        self.assertEqual([asset.role for asset in assets], ["background", "subject", "symbol"])
        self.assertIn("cat", assets[0].label)
        self.assertIn(fragment.image_prompt, assets[0].prompt)
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
        story_json = story_json_from_fragments(fragments)
        manifest = image_manifest_from_fragments(fragments, {"image_provider": "openverse"})

        self.assertEqual(scene_cards[0]["story_text"], fragments[0].text)
        self.assertEqual(story_json["fragments"][0]["image_assets"][0]["error"], "download failed")
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
        self.assertEqual(metadata["generated_image_assets"], 3)
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

    def test_openverse_query_candidates_simplify_abstract_labels(self) -> None:
        candidates = _query_candidates(
            ImageAsset(
                role="background",
                label="Solitary light form, ephemeral tendrils, deep void",
                prompt="A solitary shimmering light in a dark empty space.",
            )
        )

        self.assertEqual(candidates[0], "solitary light")
        self.assertIn("background", candidates)
        self.assertLessEqual(len(candidates[0].split()), 2)

    def test_stream_sends_fragment_before_explicit_play(self) -> None:
        sent: list[tuple[str, object]] = []

        class FakeClient:
            def __init__(self, host: str, port: int) -> None:
                self.host = host
                self.port = port

            def send_message(self, address: str, payload: object) -> None:
                sent.append((address, payload))

        fake_pythonosc = SimpleNamespace(udp_client=SimpleNamespace(SimpleUDPClient=FakeClient))
        with patch.dict(sys.modules, {"pythonosc": fake_pythonosc}):
            stream = ProcessingOscStream(
                "127.0.0.1",
                5005,
                slide_duration_s=10,
                include_images=False,
            )
            stream.start()
            stream.send(StoryFragment(id=1, mood="CALM", text="C'era una città luminosa."))

            self.assertNotIn("/start", [address for address, _ in sent])
            stream.play()
            stream.play()

        self.assertEqual([address for address, _ in sent].count("/start"), 1)
        self.assertLess(
            [address for address, _ in sent].index("/segment"),
            [address for address, _ in sent].index("/start"),
        )

    def test_processing_readiness_handshake(self) -> None:
        from pythonosc import dispatcher, osc_server, udp_client

        def free_udp_port() -> int:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(("127.0.0.1", 0))
                return int(sock.getsockname()[1])

        processing_port = free_udp_port()
        ready_port = free_udp_port()
        receiver = dispatcher.Dispatcher()

        def answer(address: str, response_port: int) -> None:
            response_address = "/ready" if address == "/prepare" else "/primed"
            client = udp_client.SimpleUDPClient("127.0.0.1", int(response_port))
            try:
                client.send_message(response_address, [1])
            finally:
                client._sock.close()

        receiver.map("/prepare", answer)
        receiver.map("/prime", answer)
        server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", processing_port), receiver)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            stream = ProcessingOscStream(
                "127.0.0.1",
                processing_port,
                slide_duration_s=60,
                include_images=False,
                ready_port=ready_port,
            )
            stream.await_ready(2)
            stream.prime(2)
            stream.client._sock.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

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

        self.assertEqual(metadata["failed_image_assets"], 3)
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
                with (
                    patch("bard_core.transport.osc_sender.time.sleep"),
                    patch.object(ProcessingOscStream, "await_ready"),
                    patch.object(ProcessingOscStream, "prime"),
                ):
                    send_fragments_to_processing(
                        fragments=[fragment],
                        host="127.0.0.1",
                        port=5005,
                        slide_duration_s=10,
                        start_delay_s=0,
                        include_images=True,
                    )

        image_messages = [payload for address, payload in sent if address == "/image"]
        segment_messages = [payload for address, payload in sent if address == "/segment"]
        self.assertEqual(sent[0][0], "/reset")
        self.assertEqual(segment_messages, [[1, "CALM", "A cat waits.", 0.0, 10.0]])
        self.assertIn(("/config/streaming", 1), sent)
        self.assertEqual(len(image_messages), 1)
        self.assertEqual(image_messages[0][0], 1)
        self.assertEqual(image_messages[0][1], 0)
        self.assertEqual(image_messages[0][2], "subject")

    def test_audio_playback_is_loaded_started_and_waited(self) -> None:
        with TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "audio.ogg"
            audio_path.write_bytes(b"fake")
            events: list[str] = []
            busy_values = iter([True, False])

            fake_music = SimpleNamespace(
                load=lambda path: events.append(f"load:{Path(path).name}"),
                play=lambda: events.append("play"),
                get_busy=lambda: next(busy_values),
            )
            fake_pygame = SimpleNamespace(
                mixer=SimpleNamespace(init=lambda: events.append("init"), music=fake_music),
                time=SimpleNamespace(Clock=lambda: SimpleNamespace(tick=lambda fps: events.append(f"tick:{fps}"))),
            )

            with patch.dict(sys.modules, {"pygame": fake_pygame}):
                playback = prepare_audio_playback(audio_path)
                playback.play()
                playback.wait()

        self.assertEqual(events[:3], ["init", "load:audio.ogg", "play"])
        self.assertIn("tick:30", events)
