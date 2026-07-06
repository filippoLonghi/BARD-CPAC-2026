from __future__ import annotations

from dataclasses import replace
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
from bard_core.contracts import ImageAsset, PipelineResult, StoryFragment, story_fragments_from_json, write_json
from bard_core.cli import (
    fake_story_card_options,
    fake_story_fragments,
    image_manifest_from_fragments,
    main,
    normalize_argv,
    scene_cards_from_fragments,
    story_json_from_fragments,
)
from bard_core.images.generator import generate_images_for_fragments
from bard_core.images.background_removal import postprocess_generated_image_asset, remove_background_to_alpha
from bard_core.images.openverse_provider import _query_candidates, _query_for_asset
from bard_core.images.planner import ensure_fragment_image_assets
from bard_core.progress import PipelineTracer
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
        max_image_assets=2,
        image_aspect_ratio="1:1",
        image_timeout_s=10,
        image_model="imagen-4.0-fast-generate-001",
        image_location="europe-west1",
        remove_image_background=False,
        background_removal_provider="fallback",
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


class ImageAssetTests(TestCase):
    def test_asset_planning_expands_single_prompt_to_two_visual_roles(self) -> None:
        fragment = StoryFragment(
            id=1,
            mood="CALM",
            text="A cat waits under the sun.",
            image_prompt="A rough black cat silhouette on a dark background.",
            visual_motif="cat",
        )

        assets = ensure_fragment_image_assets(fragment, max_assets=3)

        self.assertEqual(len(assets), 2)
        self.assertEqual([asset.role for asset in assets], ["background", "subject"])
        self.assertIn("cat", assets[0].label)
        self.assertIn(fragment.image_prompt, assets[0].prompt)
        self.assertIn("text", assets[0].negative_prompt or "")

    def test_asset_planning_deduplicates_filters_and_orders_roles(self) -> None:
        fragment = StoryFragment(
            id=1,
            mood="CALM",
            text="A signal opens.",
            image_assets=[
                ImageAsset(role="subject", label="first helper", prompt="first helper"),
                ImageAsset(role="symbol", label="spark", prompt="spark"),
                ImageAsset(role="background", label="tower", prompt="tower"),
                ImageAsset(role="subject", label="second helper", prompt="second helper"),
            ],
        )

        assets = ensure_fragment_image_assets(fragment, max_assets=3)

        self.assertEqual([asset.role for asset in assets], ["background", "subject"])
        self.assertEqual([asset.label for asset in assets], ["tower", "first helper"])

    def test_fake_story_card_has_layered_assets(self) -> None:
        fragments = fake_story_fragments()

        self.assertEqual(len(fragments), 1)
        self.assertEqual([asset.role for asset in fragments[0].image_assets], ["background", "subject"])
        self.assertIn("clock", fragments[0].image_assets[0].label)

    def test_fake_story_card_catalog_selects_named_card(self) -> None:
        self.assertIn("boat-fog-lantern", fake_story_card_options())

        fragments = fake_story_fragments("boat-fog-lantern")

        self.assertEqual(fragments[0].visual_motif, "boat in fog with lantern")
        self.assertEqual([asset.label for asset in fragments[0].image_assets], ["foggy harbor", "wooden ferry"])

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
        self.assertEqual(scene_cards[0]["image_assets"][0]["label"], "clockwork plaza")
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
        self.assertEqual(metadata["generated_image_assets"], 2)
        self.assertEqual(fragment.image_assets[0].status, "generated")
        self.assertEqual(fragment.image_assets[0].model, "black-forest-labs/flux-schnell")

    def test_image_trace_accepts_asset_label_field(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragment = StoryFragment(
                id=1,
                mood="CALM",
                text="A signal opens.",
                image_assets=[ImageAsset(role="subject", label="signal mask", prompt="signal mask")],
            )
            tracer = PipelineTracer(enabled=False)

            def fake_generate(asset: ImageAsset, output_base_path: Path, settings: BardSettings) -> ImageAsset:
                output_path = output_base_path.with_suffix(".png")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"fake")
                asset.status = "generated"
                asset.local_path = str(output_path)
                return asset

            with patch("bard_core.images.generator.generate_replicate_image", side_effect=fake_generate):
                metadata = generate_images_for_fragments(
                    [fragment],
                    test_settings(tmp_path),
                    tmp_path / "images",
                    provider="replicate",
                    max_assets=2,
                    print_estimate=False,
                    tracer=tracer,
                )

        self.assertEqual(metadata["failed_image_assets"], 0)
        self.assertTrue(any(event.get("asset_label") == "signal mask" for event in tracer.to_json()))

    def test_background_removal_fallback_writes_rgba_png(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.png"
            output_path = tmp_path / "cutout.png"
            image = Image.new("RGB", (16, 16), "white")
            for y in range(5, 11):
                for x in range(5, 11):
                    image.putpixel((x, y), (220, 20, 20))
            image.save(input_path)

            with patch.dict(sys.modules, {"rembg": None}):
                result_path = remove_background_to_alpha(input_path, output_path)

            with Image.open(result_path) as result:
                self.assertEqual(result.mode, "RGBA")
                self.assertLess(result.size[0], 16)
                self.assertLess(result.size[1], 16)
                self.assertEqual(result.getpixel((0, 0))[3], 0)

    def test_generated_subject_images_are_postprocessed_to_alpha_png(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragment = StoryFragment(
                id=1,
                mood="CALM",
                text="A brass helper waits.",
                image_assets=[ImageAsset(role="subject", label="helper", prompt="helper")],
            )
            settings = replace(
                test_settings(tmp_path),
                remove_image_background=True,
                background_removal_provider="fallback",
            )

            def fake_generate(asset: ImageAsset, output_base_path: Path, settings: BardSettings) -> ImageAsset:
                output_path = output_base_path.with_suffix(".png")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image = Image.new("RGB", (16, 16), "white")
                for y in range(5, 11):
                    for x in range(5, 11):
                        image.putpixel((x, y), (20, 80, 220))
                image.save(output_path)
                asset.status = "generated"
                asset.local_path = str(output_path)
                asset.provider = "replicate"
                asset.model = settings.replicate_model
                return asset

            with patch("bard_core.images.generator.generate_replicate_image", side_effect=fake_generate):
                metadata = generate_images_for_fragments(
                    [fragment],
                    settings,
                    tmp_path / "images",
                    provider="replicate",
                    max_assets=2,
                    print_estimate=False,
                )

            subject = next(asset for asset in fragment.image_assets if asset.role == "subject")
            with Image.open(subject.local_path or "") as result:
                self.assertEqual(result.mode, "RGBA")
                self.assertLess(result.size[0], 16)
                self.assertLess(result.size[1], 16)
                self.assertEqual(result.getpixel((0, 0))[3], 0)
            self.assertEqual(metadata["generated_image_assets"], 2)

    def test_background_assets_are_not_background_removed(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_path = tmp_path / "background.png"
            Image.new("RGB", (16, 16), "white").save(image_path)
            asset = ImageAsset(
                role="background",
                label="tower",
                prompt="tower",
                status="generated",
                local_path=str(image_path),
            )
            settings = replace(
                test_settings(tmp_path),
                remove_image_background=True,
                background_removal_provider="fallback",
            )

            postprocess_generated_image_asset(asset, settings)

            self.assertEqual(Path(asset.local_path or ""), image_path)
            with Image.open(asset.local_path or "") as result:
                self.assertEqual(result.mode, "RGB")

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
        try:
            from pythonosc import dispatcher, osc_server, udp_client
        except ImportError:
            self.skipTest("python-osc is not installed")

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

        self.assertEqual(metadata["failed_image_assets"], 2)
        self.assertEqual(fragment.image_assets[0].status, "failed")
        self.assertEqual(fragment.image_assets[0].error, "no token")

    def test_compact_story_and_debug_artifacts_serialize_image_assets(self) -> None:
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

            self.assertTrue((tmp_path / "story.json").exists())
            self.assertTrue((tmp_path / "run_manifest.json").exists())
            self.assertFalse((tmp_path / "scene_cards.json").exists())
            story = (tmp_path / "story.json").read_text(encoding="utf-8")
            self.assertIn('"schema": "bard.replay_story"', story)
            self.assertNotIn("music_prompt", story)

            loaded = story_fragments_from_json(tmp_path / "story.json")
            self.assertEqual(loaded[0].image_assets[0].label, "cat")

            result.write(tmp_path, debug_artifacts=True)
            cards = (tmp_path / "debug" / "scene_cards.json").read_text(encoding="utf-8")
            self.assertIn('"image_assets"', cards)
            self.assertIn('"story_text": "A cat waits."', cards)

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
        self.assertEqual(segment_messages, [[1, "CALM", "A%20cat%20waits.", 0.0, 10.0]])
        self.assertIn(("/config/streaming", 1), sent)
        self.assertEqual(len(image_messages), 1)
        self.assertEqual(image_messages[0][0], 1)
        self.assertEqual(image_messages[0][1], 0)
        self.assertEqual(image_messages[0][2], "subject")

    def test_osc_stream_can_send_images_after_text(self) -> None:
        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "cat.png"
            image_path.write_bytes(b"fake")
            fragment = StoryFragment(
                id=7,
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
                stream = ProcessingOscStream(
                    "127.0.0.1",
                    5005,
                    slide_duration_s=10,
                    include_images=False,
                )
                stream.send(fragment)
                stream.send_images(fragment)

        self.assertIn("/segment", [address for address, _ in sent])
        image_messages = [payload for address, payload in sent if address == "/image"]
        self.assertEqual(len(image_messages), 1)
        self.assertEqual(image_messages[0][0], 7)
        self.assertEqual(image_messages[0][2], "subject")

    def test_osc_sender_sets_processing_audio_path(self) -> None:
        with TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "processing_audio.wav"
            audio_path.write_bytes(b"fake")
            fragment = StoryFragment(id=1, mood="CALM", text="A cat waits.")
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
                        processing_audio_path=audio_path,
                    )

        self.assertIn(("/audio", [audio_path.as_posix()]), sent)
        self.assertLess(
            [address for address, _ in sent].index("/audio"),
            [address for address, _ in sent].index("/segment"),
        )

    def test_send_osc_uses_configured_ready_bind_host(self) -> None:
        with TemporaryDirectory() as tmp:
            story_path = Path(tmp) / "story.json"
            write_json(
                story_path,
                story_json_from_fragments([StoryFragment(id=1, mood="CALM", text="A cat waits.")]),
            )

            with (
                patch.dict(
                    "os.environ",
                    {
                        "BARD_OSC_HOST": "host.docker.internal",
                        "BARD_OSC_PORT": "5005",
                        "BARD_OSC_READY_PORT": "5007",
                        "BARD_OSC_READY_BIND_HOST": "0.0.0.0",
                    },
                    clear=False,
                ),
                patch("bard_core.cli.send_fragments_to_processing") as send,
            ):
                main(["send-osc", "--story-json", str(story_path), "--delay", "0"])

        self.assertEqual(send.call_args.kwargs["host"], "host.docker.internal")
        self.assertEqual(send.call_args.kwargs["ready_port"], 5007)
        self.assertEqual(send.call_args.kwargs["ready_bind_host"], "0.0.0.0")
        self.assertTrue(send.call_args.kwargs["include_images"])

    def test_send_osc_replay_auto_uses_sibling_processing_audio_and_images(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            story_path = tmp_path / "story.json"
            audio_path = tmp_path / "processing_audio.wav"
            audio_path.write_bytes(b"fake")
            write_json(
                story_path,
                story_json_from_fragments([StoryFragment(id=1, mood="CALM", text="A cat waits.")]),
            )

            with patch("bard_core.cli.send_fragments_to_processing") as send:
                main(["send-osc", "--story-json", str(story_path), "--delay", "0"])

        self.assertTrue(send.call_args.kwargs["include_images"])
        self.assertIsNone(send.call_args.kwargs["audio_path"])
        self.assertEqual(send.call_args.kwargs["processing_audio_path"], audio_path.resolve())

    def test_send_osc_processing_playback_converts_audio_for_processing(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            story_path = tmp_path / "story.json"
            audio_path = tmp_path / "source.ogg"
            converted_path = tmp_path / "processing_audio.wav"
            audio_path.write_bytes(b"fake")
            write_json(
                story_path,
                story_json_from_fragments([StoryFragment(id=1, mood="CALM", text="A cat waits.")]),
            )

            with (
                patch("bard_core.cli.convert_audio_to_wav", return_value=converted_path) as convert,
                patch("bard_core.cli.send_fragments_to_processing") as send,
            ):
                main(
                    [
                        "send-osc",
                        "--story-json",
                        str(story_path),
                        "--audio",
                        str(audio_path),
                        "--playback",
                        "processing",
                        "--delay",
                        "0",
                    ]
                )

        convert.assert_called_once_with(audio_path, story_path.parent / "processing_audio.wav")
        self.assertIsNone(send.call_args.kwargs["audio_path"])
        self.assertEqual(send.call_args.kwargs["processing_audio_path"], converted_path)

    def test_send_osc_processing_playback_reuses_existing_processing_wav(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            story_path = tmp_path / "story.json"
            audio_path = tmp_path / "processing_audio.wav"
            audio_path.write_bytes(b"fake")
            write_json(
                story_path,
                story_json_from_fragments([StoryFragment(id=1, mood="CALM", text="A cat waits.")]),
            )

            with (
                patch("bard_core.cli.convert_audio_to_wav") as convert,
                patch("bard_core.cli.send_fragments_to_processing") as send,
            ):
                main(
                    [
                        "send-osc",
                        "--story-json",
                        str(story_path),
                        "--audio",
                        str(audio_path),
                        "--playback",
                        "processing",
                        "--delay",
                        "0",
                    ]
                )

        convert.assert_not_called()
        self.assertIsNone(send.call_args.kwargs["audio_path"])
        self.assertEqual(send.call_args.kwargs["processing_audio_path"], audio_path.resolve())

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
