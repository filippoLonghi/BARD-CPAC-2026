from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

from .config import BardSettings, load_env_file
from .contracts import ImageAsset, PipelineResult, StoryFragment, story_fragments_from_json, write_json
from .audio import convert_audio_to_wav
from .images import generate_images_for_fragments
from .pipeline_sequential import run_sequential_pipeline
from .transport import send_fragments_to_processing
from .utils import make_run_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BARD cloud-ready pipeline tools.")
    parser.add_argument("--env-file", default=None, help="Optional .env file. Keep real secret paths outside git.")
    sub = parser.add_subparsers(dest="command", required=True)

    sequential = sub.add_parser(
        "run-fragments",
        help="Process an uploaded audio file one saved fragment at a time.",
    )
    sequential.add_argument("--audio", required=True, help="Audio file path.")
    size = sequential.add_mutually_exclusive_group()
    size.add_argument(
        "--chunk-seconds",
        type=float,
        default=None,
        help="Debug override for story-scene length; otherwise BARD uses the configured scene duration.",
    )
    size.add_argument("--fragments", type=int, default=None, help="Split the complete file into exactly N fragments.")
    sequential.add_argument(
        "--planned-duration",
        type=float,
        default=None,
        help="Optional planned live duration in seconds; file end still forces the ending.",
    )
    sequential.add_argument(
        "--words-per-fragment",
        type=int,
        default=None,
        help="Override automatic duration/readability word budgeting.",
    )
    sequential.add_argument(
        "--music-window-seconds",
        type=float,
        default=None,
        help="Length of fine musical observations inside each longer story scene.",
    )
    sequential.add_argument(
        "--fragment-target-seconds",
        type=float,
        default=None,
        help="Target automatic story-fragment duration. Ignored by explicit --fragments or --chunk-seconds.",
    )
    sequential.add_argument(
        "--fragment-min-seconds",
        type=float,
        default=None,
        help="Preferred minimum automatic story-fragment duration for longer audio.",
    )
    sequential.add_argument(
        "--fragment-max-seconds",
        type=float,
        default=None,
        help="Preferred maximum automatic story-fragment duration for longer audio.",
    )
    sequential.add_argument(
        "--short-audio-threshold-seconds",
        type=float,
        default=None,
        help="Duration below which automatic splitting chooses only one or two balanced fragments.",
    )
    sequential.add_argument(
        "--music-windows-per-fragment",
        type=int,
        default=None,
        help="Fine music observations per story fragment when --music-window-seconds is not set.",
    )
    sequential.add_argument(
        "--startup-delay",
        type=float,
        default=None,
        help="Seconds to let Processing ingest the first complete scene before audio starts.",
    )
    sequential.add_argument(
        "--playback",
        choices=["python", "processing"],
        default="python",
        help="Play audio with local Python or inside host Processing (required for Docker Desktop).",
    )
    _add_story_style_arguments(sequential)
    sequential.add_argument("--generate-images", action="store_true")
    sequential.add_argument("--image-provider", choices=["replicate", "imagen", "openverse"], default=None)
    sequential.add_argument("--max-image-assets", type=int, default=2)
    sequential.add_argument("--send-osc", action="store_true")
    sequential.add_argument(
        "--debug-artifacts",
        action="store_true",
        help="Write verbose debug files under debug/ in addition to compact story.json and run_manifest.json.",
    )
    sequential.add_argument(
        "--keep-audio-chunks",
        action="store_true",
        help="Keep per-fragment WAV chunks under audio_chunks/ for debugging.",
    )
    sequential.add_argument("--out-dir", default=None)

    images = sub.add_parser("generate-images", help="Generate/retrieve image assets without running audio/story.")
    images.add_argument("--story-json", default=None, help="Existing story.json to use as input.")
    images.add_argument("--fake-card", action="store_true", help="Use a built-in fake story card for quick testing.")
    images.add_argument("--fake-card-name", default="cat-wood-sun", help="Built-in fake card name.")
    images.add_argument("--list-fake-cards", action="store_true", help="List available built-in fake cards.")
    images.add_argument(
        "--write-input-only",
        action="store_true",
        help="Write debug/scene_cards.json and exit without images.",
    )
    images.add_argument("--image-provider", choices=["replicate", "imagen", "openverse"], required=True)
    images.add_argument("--max-image-assets", type=int, default=None, help="Maximum image assets per fragment.")
    images.add_argument("--send-osc", action="store_true", help="Send the generated image assets to Processing.")
    images.add_argument("--duration", type=float, default=10.0, help="OSC slide duration when --send-osc is used.")
    images.add_argument(
        "--debug-artifacts",
        action="store_true",
        help="Write verbose image debugging files under debug/.",
    )
    images.add_argument("--out-dir", default=None, help="Optional output directory for this image-only run.")

    osc = sub.add_parser("send-osc", help="Send an existing story.json to Processing.")
    osc.add_argument("--story-json", required=True, help="Path to story.json.")
    osc.add_argument("--duration", type=float, default=10.0, help="Slide duration in seconds.")
    osc.add_argument("--host", default=None)
    osc.add_argument("--port", type=int, default=None)
    osc.add_argument("--delay", type=float, default=2.0)
    osc.add_argument("--include-images", action="store_true", help="Also send /image messages for local image assets.")
    osc.add_argument("--audio", default=None, help="Optional source audio to play in sync with /start.")
    osc.add_argument(
        "--playback",
        choices=["python", "processing"],
        default="python",
        help="Play audio with local Python or inside host Processing (required for Docker Desktop).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    argv = normalize_argv(argv if argv is not None else sys.argv[1:])
    args = parser.parse_args(argv)
    load_env_file(Path(args.env_file).expanduser() if args.env_file else None)
    settings = BardSettings.from_env()
    settings = _settings_with_story_overrides(settings, args)

    if args.command == "run-fragments":
        result = run_sequential_pipeline(
            audio_path=Path(args.audio),
            settings=settings,
            chunk_s=args.chunk_seconds,
            fragment_count=args.fragments,
            planned_duration_s=args.planned_duration,
            words_per_fragment=args.words_per_fragment,
            music_window_s=args.music_window_seconds,
            story_wpm=args.story_wpm,
            fragment_target_s=args.fragment_target_seconds,
            fragment_min_s=args.fragment_min_seconds,
            fragment_max_s=args.fragment_max_seconds,
            short_audio_threshold_s=args.short_audio_threshold_seconds,
            music_windows_per_fragment=args.music_windows_per_fragment,
            startup_delay_s=args.startup_delay,
            playback_mode=args.playback,
            generate_images=args.generate_images,
            image_provider=args.image_provider,
            max_image_assets=args.max_image_assets,
            send_osc=args.send_osc,
            output_dir=Path(args.out_dir).expanduser() if args.out_dir else None,
            debug_artifacts=args.debug_artifacts,
            keep_audio_chunks=args.keep_audio_chunks,
        )
        print(f"Sequential run complete: {result.run_id}")
        print(f"Fragments: {len(result.fragments)}")
        print(f"Output directory: {args.out_dir or settings.output_dir}")
        return

    if args.command == "generate-images":
        if args.list_fake_cards:
            print("Available fake cards:")
            for name, description in fake_story_card_options().items():
                print(f"- {name}: {description}")
            return

        if not args.fake_card and not args.story_json:
            parser.error("generate-images requires --fake-card or --story-json.")
        if args.fake_card and args.story_json:
            parser.error("Use either --fake-card or --story-json, not both.")

        fragments = (
            fake_story_fragments(args.fake_card_name)
            if args.fake_card
            else story_fragments_from_json(Path(args.story_json).expanduser())
        )
        run_id = make_run_id()
        destination = Path(args.out_dir).expanduser() if args.out_dir else settings.output_dir / f"{run_id}-images"
        if args.write_input_only:
            scene_cards_path = destination / "debug" / "scene_cards.json"
            write_json(scene_cards_path, scene_cards_from_fragments(fragments))
            print(f"Wrote image input scene cards: {scene_cards_path}")
            return

        metadata = generate_images_for_fragments(
            fragments=fragments,
            settings=settings,
            output_dir=destination / "images",
            provider=args.image_provider,
            max_assets=args.max_image_assets or settings.max_image_assets,
        )
        result = PipelineResult(
            run_id=run_id,
            audio_path="image-only",
            music_segments=[],
            fragments=fragments,
            full_story="\n\n".join(fragment.text for fragment in fragments),
            metadata={"execution_mode": "image-only", **metadata},
        )
        result.write(destination, debug_artifacts=args.debug_artifacts)
        if args.send_osc:
            send_fragments_to_processing(
                fragments=fragments,
                host=settings.osc_host,
                port=settings.osc_port,
                slide_duration_s=args.duration,
                include_images=True,
                ready_port=settings.osc_ready_port,
                ready_bind_host=settings.osc_ready_bind_host,
                ready_timeout_s=settings.processing_ready_timeout_s,
            )
        print(f"Image-only run complete: {run_id}")
        print(f"Fragments: {len(fragments)}")
        print(f"Output directory: {destination}")
        print(f"Images directory: {destination / 'images'}")
        print(f"Manifest: {destination / 'run_manifest.json'}")
        return

    if args.command == "send-osc":
        story_json_path = Path(args.story_json).expanduser()
        fragments = story_fragments_from_json(story_json_path)
        audio_path = Path(args.audio).expanduser() if args.audio else None
        processing_audio_path = None
        if args.playback == "processing":
            if not audio_path:
                parser.error("send-osc --playback processing requires --audio.")
            target_audio_path = story_json_path.parent / "processing_audio.wav"
            if audio_path.expanduser().resolve() == target_audio_path.expanduser().resolve():
                processing_audio_path = audio_path.expanduser().resolve()
            else:
                processing_audio_path = convert_audio_to_wav(audio_path, target_audio_path)
            audio_path = None
        send_fragments_to_processing(
            fragments=fragments,
            host=args.host or settings.osc_host,
            port=args.port or settings.osc_port,
            slide_duration_s=args.duration,
            start_delay_s=args.delay,
            include_images=args.include_images,
            audio_path=audio_path,
            processing_audio_path=processing_audio_path,
            ready_port=settings.osc_ready_port,
            ready_bind_host=settings.osc_ready_bind_host,
            ready_timeout_s=settings.processing_ready_timeout_s,
        )
        print(f"Sent {len(fragments)} fragments to {args.host or settings.osc_host}:{args.port or settings.osc_port}")
        return

    parser.error(f"Unsupported command: {args.command}")


def normalize_argv(argv: list[str]) -> list[str]:
    commands = {"run-fragments", "generate-images", "send-osc"}
    normalized: list[str] = []
    idx = 0
    while idx < len(argv):
        item = argv[idx]
        if item == "--env-file" and idx + 1 < len(argv):
            value = argv[idx + 1]
            if value == "" or value in commands:
                idx += 1 if value == "" else 0
                idx += 1
                continue
        normalized.append(item)
        idx += 1
    return normalized


def _add_story_style_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--story-language", default=None, help="Audience-facing story language, for example Italian.")
    parser.add_argument(
        "--story-level",
        choices=["early-reader", "children", "general", "literary"],
        default=None,
        help="Vocabulary and sentence-complexity level.",
    )
    parser.add_argument("--reading-wpm", type=float, default=None, help="Legacy alias for --story-wpm.")
    parser.add_argument("--story-wpm", type=float, default=None, help="Target displayed story words per minute.")
    parser.add_argument(
        "--target-words-per-fragment",
        type=int,
        default=None,
        help="Preferred minimum words used when calculating an automatic story-scene duration.",
    )
    parser.add_argument(
        "--text-coverage",
        type=float,
        default=None,
        help="Deprecated for run-fragments; use --story-wpm instead.",
    )


def _settings_with_story_overrides(settings: BardSettings, args: argparse.Namespace) -> BardSettings:
    values: dict[str, object] = {}
    for arg_name, setting_name in (
        ("story_language", "story_language"),
        ("story_level", "story_level"),
        ("reading_wpm", "default_wpm"),
        ("story_wpm", "story_wpm"),
        ("text_coverage", "text_coverage"),
        ("target_words_per_fragment", "target_words_per_fragment"),
    ):
        value = getattr(args, arg_name, None)
        if value is not None:
            values[setting_name] = value
    if getattr(args, "reading_wpm", None) is not None and getattr(args, "story_wpm", None) is None:
        values["story_wpm"] = args.reading_wpm
    return replace(settings, **values) if values else settings


def fake_story_card_options() -> dict[str, str]:
    return {
        "cat-wood-sun": "Clockwork subject plus plaza background.",
        "girl-tower-moon": "Signal mask subject plus moon archive background.",
        "boat-fog-lantern": "Vehicle subject plus foggy harbor background.",
        "fox-snow-fire": "Forge helper subject plus volcanic workshop background.",
        "door-garden-key": "Living door subject plus folk village background.",
    }


def fake_story_fragments(name: str = "cat-wood-sun") -> list[StoryFragment]:
    catalog = {
        "cat-wood-sun": StoryFragment(
            id=1,
            mood="CALM",
            text="A brass clock helper crosses a ticking plaza while the town bells wake.",
            start_s=0.0,
            end_s=10.0,
            image_prompt="A brass clock helper in a clockwork city plaza, unfinished painterly style.",
            visual_motif="clock helper in ticking plaza",
            palette="brass, teal patina, warm lamp glow",
            motion="slow drifting layers with soft blur",
            image_assets=[
                _fake_asset("background", "clockwork plaza", "A loose unfinished painted clockwork city plaza, brass towers and ticking street lines, no characters, no text."),
                _fake_asset("subject", "brass clock helper", "A simple recognizable brass clock helper, round body, teal glass face, unfinished painterly sketch texture, plain simple background, no text."),
            ],
        ),
        "girl-tower-moon": StoryFragment(
            id=1,
            mood="ANXIOUS",
            text="A silver signal mask waits beside a moon archive tower as star maps flutter.",
            start_s=0.0,
            end_s=10.0,
            image_prompt="A silver signal mask near a moon archive tower in an unfinished storybook texture.",
            visual_motif="signal mask near moon archive",
            palette="ink blue, pale grey, muted violet",
            motion="nervous vertical drift",
            image_assets=[
                _fake_asset("background", "moon archive tower", "A loose unfinished painted moon archive tower, silver shelves and star maps, night atmosphere, no characters, no text."),
                _fake_asset("subject", "silver signal mask", "A simple recognizable silver signal mask with blue glass eyes, unfinished charcoal and paint texture, plain simple background, no text."),
            ],
        ),
        "boat-fog-lantern": StoryFragment(
            id=1,
            mood="DARK",
            text="A wooden ferry crosses a foggy harbor while its small cabin light keeps the route alive.",
            start_s=0.0,
            end_s=10.0,
            image_prompt="A rough wooden ferry and foggy harbor background.",
            visual_motif="boat in fog with lantern",
            palette="blue grey, dark teal, warm gold",
            motion="slow horizontal drift",
            image_assets=[
                _fake_asset("background", "foggy harbor", "A loose unfinished painted foggy harbor at night, blue grey mist, soft blurred docks, no boats, no text."),
                _fake_asset("subject", "wooden ferry", "A simple recognizable wooden ferry with a tiny warm cabin light, unfinished painterly texture, plain simple background, no people, no text."),
            ],
        ),
        "fox-snow-fire": StoryFragment(
            id=1,
            mood="BRIGHT",
            text="An ember cart rolls through a volcanic workshop while cooled crystals ring under its wheels.",
            start_s=0.0,
            end_s=10.0,
            image_prompt="An ember cart in a volcanic workshop, unfinished painted style.",
            visual_motif="ember cart in volcanic workshop",
            palette="basalt black, ember orange, mineral green",
            motion="quick diagonal flicker",
            image_assets=[
                _fake_asset("background", "volcanic workshop", "A loose unfinished painted volcanic workshop, basalt lifts, glowing anvils, steam pipes, no characters, no text."),
                _fake_asset("subject", "ember cart", "A simple recognizable ember cart with small copper wheels, unfinished painterly sketch texture, plain simple background, no text."),
            ],
        ),
        "door-garden-key": StoryFragment(
            id=1,
            mood="DENSE",
            text="A blue living door listens in a folk village square while market bells answer from the roofs.",
            start_s=0.0,
            end_s=10.0,
            image_prompt="A rough blue living door in a folk village square, unfinished surreal style.",
            visual_motif="blue living door in folk village",
            palette="moss green, oxidized blue, brass yellow",
            motion="uneven pulsing reveal",
            image_assets=[
                _fake_asset("background", "folk village square", "A loose unfinished painted European folk village square with painted doors, tiled roofs, market bells, no characters, no text."),
                _fake_asset("subject", "blue living door", "A simple recognizable blue living door with brass hinges and a listening keyhole, unfinished painterly texture, plain simple background, no text."),
            ],
        ),
    }
    try:
        return [catalog[name]]
    except KeyError as exc:
        options = ", ".join(fake_story_card_options())
        raise ValueError(f"Unknown fake card: {name}. Available fake cards: {options}") from exc


def _fake_asset(role: str, label: str, prompt: str) -> ImageAsset:
    return ImageAsset(
        role=role,
        label=label,
        prompt=prompt,
        negative_prompt="text, letters, logo, watermark, instrument, photorealistic, distorted anatomy",
    )


def scene_cards_from_fragments(fragments: list[StoryFragment]) -> list[dict[str, object]]:
    return PipelineResult(
        run_id="image-only-input",
        audio_path="image-only",
        music_segments=[],
        fragments=fragments,
        full_story="\n\n".join(fragment.text for fragment in fragments),
    ).scene_cards()


def image_manifest_from_fragments(fragments: list[StoryFragment], metadata: dict[str, object]) -> dict[str, object]:
    return {
        "metadata": metadata,
        "images": [
            {
                "segment_id": fragment.id,
                "layer_index": layer_index,
                "role": asset.role,
                "label": asset.label,
                "status": asset.status,
                "local_path": asset.local_path,
                "remote_url": asset.remote_url,
                "source_url": asset.source_url,
                "license": asset.license,
                "creator": asset.creator,
                "error": asset.error,
            }
            for fragment in fragments
            for layer_index, asset in enumerate(fragment.image_assets)
        ],
    }


def story_json_from_fragments(fragments: list[StoryFragment]) -> dict[str, object]:
    return PipelineResult(
        run_id="story-fragments",
        audio_path="unknown",
        music_segments=[],
        fragments=fragments,
        full_story="\n\n".join(fragment.text for fragment in fragments),
    ).replay_story_json()
