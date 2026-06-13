from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import BardSettings, load_env_file
from .contracts import ImageAsset, PipelineResult, StoryFragment, story_fragments_from_json, write_json
from .images import generate_images_for_fragments
from .pipeline import make_run_id, run_pipeline
from .transport import send_fragments_to_processing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BARD cloud-ready pipeline tools.")
    parser.add_argument("--env-file", default=None, help="Optional .env file. Keep real secret paths outside git.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run-local", help="Run audio analysis, story generation, and optional OSC output.")
    run.add_argument("--audio", required=True, help="Audio file path.")
    run.add_argument("--ratio", default="1/5", help="Chunk size as ratio of duration, for example 1/5.")
    run.add_argument("--audio-provider", choices=["clap", "gemini"], default=None)
    run.add_argument("--story-provider", choices=["local", "mistral", "vertex", "gemini"], default=None)
    run.add_argument("--generate-images", action="store_true", help="Generate or retrieve image assets after story output.")
    run.add_argument("--image-provider", choices=["replicate", "imagen", "openverse"], default=None)
    run.add_argument("--max-image-assets", type=int, default=None, help="Maximum image assets per fragment.")
    run.add_argument("--send-osc", action="store_true", help="Send generated story fragments to Processing.")
    run.add_argument("--out-dir", default=None, help="Optional output directory for this run.")

    images = sub.add_parser("generate-images", help="Generate/retrieve image assets without running audio/story.")
    images.add_argument("--story-json", default=None, help="Existing story.json to use as input.")
    images.add_argument("--fake-card", action="store_true", help="Use a built-in fake story card for quick testing.")
    images.add_argument("--fake-card-name", default="cat-wood-sun", help="Built-in fake card name.")
    images.add_argument("--list-fake-cards", action="store_true", help="List available built-in fake cards.")
    images.add_argument("--write-input-only", action="store_true", help="Write scene_cards.json and exit without images.")
    images.add_argument("--image-provider", choices=["replicate", "imagen", "openverse"], required=True)
    images.add_argument("--max-image-assets", type=int, default=None, help="Maximum image assets per fragment.")
    images.add_argument("--send-osc", action="store_true", help="Send the generated image assets to Processing.")
    images.add_argument("--duration", type=float, default=10.0, help="OSC slide duration when --send-osc is used.")
    images.add_argument("--out-dir", default=None, help="Optional output directory for this image-only run.")

    osc = sub.add_parser("send-osc", help="Send an existing story.json to Processing.")
    osc.add_argument("--story-json", required=True, help="Path to story.json.")
    osc.add_argument("--duration", type=float, default=10.0, help="Slide duration in seconds.")
    osc.add_argument("--host", default=None)
    osc.add_argument("--port", type=int, default=None)
    osc.add_argument("--delay", type=float, default=2.0)
    osc.add_argument("--include-images", action="store_true", help="Also send /image messages for local image assets.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    argv = normalize_argv(argv if argv is not None else sys.argv[1:])
    args = parser.parse_args(argv)
    load_env_file(Path(args.env_file).expanduser() if args.env_file else None)
    settings = BardSettings.from_env()

    if args.command == "run-local":
        result = run_pipeline(
            audio_path=Path(args.audio),
            settings=settings,
            ratio=args.ratio,
            audio_provider=args.audio_provider,
            story_provider=args.story_provider,
            generate_images=args.generate_images,
            image_provider=args.image_provider,
            max_image_assets=args.max_image_assets,
            send_osc=args.send_osc,
            output_dir=Path(args.out_dir).expanduser() if args.out_dir else None,
        )
        print(f"Run complete: {result.run_id}")
        print(f"Fragments: {len(result.fragments)}")
        print(f"Output root: {settings.output_dir}")
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
        scene_cards_path = destination / "scene_cards.json"
        write_json(scene_cards_path, scene_cards_from_fragments(fragments))
        if args.write_input_only:
            print(f"Wrote image input scene cards: {scene_cards_path}")
            return

        metadata = generate_images_for_fragments(
            fragments=fragments,
            settings=settings,
            output_dir=destination / "images",
            provider=args.image_provider,
            max_assets=args.max_image_assets or settings.max_image_assets,
        )
        write_json(scene_cards_path, scene_cards_from_fragments(fragments))
        write_json(destination / "image_manifest.json", image_manifest_from_fragments(fragments, metadata))
        if args.send_osc:
            send_fragments_to_processing(
                fragments=fragments,
                host=settings.osc_host,
                port=settings.osc_port,
                slide_duration_s=args.duration,
                include_images=True,
            )
        print(f"Image-only run complete: {run_id}")
        print(f"Fragments: {len(fragments)}")
        print(f"Output directory: {destination}")
        print(f"Images directory: {destination / 'images'}")
        print(f"Manifest: {destination / 'image_manifest.json'}")
        return

    if args.command == "send-osc":
        fragments = story_fragments_from_json(Path(args.story_json).expanduser())
        send_fragments_to_processing(
            fragments=fragments,
            host=args.host or settings.osc_host,
            port=args.port or settings.osc_port,
            slide_duration_s=args.duration,
            start_delay_s=args.delay,
            include_images=args.include_images,
        )
        print(f"Sent {len(fragments)} fragments to {args.host or settings.osc_host}:{args.port or settings.osc_port}")
        return

    parser.error(f"Unsupported command: {args.command}")


def normalize_argv(argv: list[str]) -> list[str]:
    commands = {"run-local", "generate-images", "send-osc"}
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


def fake_story_card_options() -> dict[str, str]:
    return {
        "cat-wood-sun": "Recognizable animal + background + light symbol.",
        "girl-tower-moon": "Human character silhouette + architecture + moon symbol.",
        "boat-fog-lantern": "Object/vehicle + atmospheric background + glowing symbol.",
        "fox-snow-fire": "Animal + seasonal landscape + warm symbolic element.",
        "door-garden-key": "Mystery object + environment + small symbolic prop.",
    }


def fake_story_fragments(name: str = "cat-wood-sun") -> list[StoryFragment]:
    catalog = {
        "cat-wood-sun": StoryFragment(
            id=1,
            mood="CALM",
            text="A black cat enters a small wood while a low sun opens behind the branches.",
            start_s=0.0,
            end_s=10.0,
            image_prompt="A rough black cat, a quiet wood, and a low warm sun in an unfinished painterly style.",
            visual_motif="cat in the wood at sunset",
            palette="deep green, charcoal black, muted amber",
            motion="slow drifting layers with soft blur",
            image_assets=[
                _fake_asset("subject", "black cat", "A simple recognizable black cat silhouette, unfinished painterly sketch texture, soft rough edges, plain dark empty background, no text."),
                _fake_asset("background", "small wood", "A loose unfinished painted woodland background, simple tree trunks, dark green shadows, soft blur, no animals, no text."),
                _fake_asset("symbol", "low sun", "A simple warm glowing sun disk, rough painterly texture, soft amber edges, isolated on dark empty background, no text."),
            ],
        ),
        "girl-tower-moon": StoryFragment(
            id=1,
            mood="ANXIOUS",
            text="A small girl waits beside a leaning tower as the moon rises like a quiet witness.",
            start_s=0.0,
            end_s=10.0,
            image_prompt="A rough girl silhouette, a leaning tower, and a pale moon in an unfinished storybook texture.",
            visual_motif="girl near tower under moon",
            palette="ink blue, pale grey, muted violet",
            motion="nervous vertical drift",
            image_assets=[
                _fake_asset("subject", "small girl silhouette", "A simple recognizable child silhouette in a coat, unfinished charcoal and paint texture, plain dark empty background, no face detail, no text."),
                _fake_asset("background", "leaning tower", "A loose unfinished painted leaning stone tower, simple architecture, night atmosphere, soft blur, no people, no text."),
                _fake_asset("symbol", "pale moon", "A pale round moon disk with rough cloudy edges, isolated on dark empty background, no text."),
            ],
        ),
        "boat-fog-lantern": StoryFragment(
            id=1,
            mood="DEEP",
            text="A wooden boat crosses a foggy river while a lantern keeps one warm point alive.",
            start_s=0.0,
            end_s=10.0,
            image_prompt="A rough wooden boat, foggy river background, and warm lantern glow.",
            visual_motif="boat in fog with lantern",
            palette="blue grey, dark teal, warm gold",
            motion="slow horizontal drift",
            image_assets=[
                _fake_asset("subject", "wooden boat", "A simple recognizable wooden rowboat, unfinished painterly texture, soft rough edges, plain dark empty background, no people, no text."),
                _fake_asset("background", "foggy river", "A loose unfinished painted foggy river at night, blue grey mist, soft blurred banks, no boats, no text."),
                _fake_asset("symbol", "warm lantern", "A small warm lantern glow, simple recognizable lantern shape, rough painterly amber light, isolated on dark empty background, no text."),
            ],
        ),
        "fox-snow-fire": StoryFragment(
            id=1,
            mood="ENERGETIC",
            text="A red fox cuts across a white field while a small fire trembles against the snow.",
            start_s=0.0,
            end_s=10.0,
            image_prompt="A rough red fox, snowy field, and small fire in an unfinished painted style.",
            visual_motif="fox in snow near fire",
            palette="snow white, rust red, ember orange",
            motion="quick diagonal flicker",
            image_assets=[
                _fake_asset("subject", "red fox", "A simple recognizable red fox silhouette, unfinished painterly sketch texture, soft rough edges, plain dark empty background, no text."),
                _fake_asset("background", "snowy field", "A loose unfinished painted snowy field, white ground and faint horizon, soft blur, no animals, no text."),
                _fake_asset("symbol", "small fire", "A small orange fire flame, rough painterly ember texture, isolated on dark empty background, no text."),
            ],
        ),
        "door-garden-key": StoryFragment(
            id=1,
            mood="DISSONANT",
            text="A blue door appears in an overgrown garden, and a brass key hangs where no hand can reach.",
            start_s=0.0,
            end_s=10.0,
            image_prompt="A rough blue door, overgrown garden, and brass key in an unfinished surreal style.",
            visual_motif="blue door in garden with key",
            palette="moss green, oxidized blue, brass yellow",
            motion="uneven pulsing reveal",
            image_assets=[
                _fake_asset("subject", "blue door", "A simple recognizable blue wooden door, unfinished painterly texture, soft rough edges, plain dark empty background, no text."),
                _fake_asset("background", "overgrown garden", "A loose unfinished painted overgrown garden, tangled green plants, soft blur, no people, no text."),
                _fake_asset("symbol", "brass key", "A simple recognizable brass key, rough painterly gold texture, isolated on dark empty background, no text."),
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
