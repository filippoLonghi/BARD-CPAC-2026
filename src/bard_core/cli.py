from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

from .config import BardSettings, load_env_file
from .contracts import PipelineResult, StoryFragment, read_json, story_fragments_from_json, write_json
from .audio import convert_audio_to_wav
from .images import generate_images_for_fragments
from .pipeline_live import list_audio_input_devices, run_live_pipeline, test_audio_input_device
from .pipeline_sequential import run_sequential_pipeline
from .transport import send_fragments_to_processing
from .utils import make_run_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BARD pipeline tools.")
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
        "--startup-buffer-fragments",
        type=int,
        default=None,
        help="Complete story/image fragments to prepare before Processing starts.",
    )
    sequential.add_argument(
        "--playback",
        choices=["python", "processing"],
        default="python",
        help="Play audio with local Python or inside host Processing (required for Docker Desktop).",
    )
    _add_story_style_arguments(sequential)
    sequential.add_argument("--generate-images", action="store_true")
    sequential.add_argument("--image-provider", choices=["imagen", "openverse"], default=None)
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

    live = sub.add_parser(
        "run-live",
        help="Record microphone audio in live chunks and send delayed visuals to Processing.",
    )
    live.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Planned performance/story duration in seconds. BARD does not infer this automatically.",
    )
    live.add_argument(
        "--list-input-devices",
        action="store_true",
        help="List microphone/input devices visible to this Python environment and exit.",
    )
    live.add_argument(
        "--input-device",
        default=None,
        help="Sounddevice input device index or name visible to this Python environment.",
    )
    live.add_argument(
        "--test-input-seconds",
        type=float,
        default=None,
        help="Record a short microphone probe, print RMS/peak levels, and exit without OSC or API calls.",
    )
    live.add_argument(
        "--sample-rate",
        type=int,
        default=44100,
        help="Recording sample rate used for microphone chunks.",
    )
    live.add_argument(
        "--chunk-seconds",
        type=float,
        default=None,
        help="Live story-scene chunk length. Defaults to BARD_LIVE_STORY_SCENE_S.",
    )
    live.add_argument(
        "--words-per-fragment",
        type=int,
        default=None,
        help="Override automatic duration/readability word budgeting.",
    )
    live.add_argument(
        "--music-window-seconds",
        type=float,
        default=None,
        help="Length of fine musical observations inside each live story scene.",
    )
    live.add_argument(
        "--music-windows-per-fragment",
        type=int,
        default=None,
        help="Fine music observations per story fragment when --music-window-seconds is not set.",
    )
    live.add_argument(
        "--startup-delay",
        type=float,
        default=None,
        help="Seconds to let Processing ingest the first text scene before the visual clock starts.",
    )
    live.add_argument(
        "--startup-buffer-fragments",
        type=int,
        default=None,
        help="Complete story/image fragments to prepare before Processing starts.",
    )
    _add_story_style_arguments(live)
    live.add_argument("--generate-images", action="store_true")
    live.add_argument("--image-provider", choices=["imagen", "openverse"], default=None)
    live.add_argument("--max-image-assets", type=int, default=2)
    live.add_argument(
        "--debug-artifacts",
        action="store_true",
        help="Write verbose debug files under debug/ in addition to compact story.json and run_manifest.json.",
    )
    live.add_argument(
        "--keep-audio-chunks",
        action="store_true",
        help="Compatibility flag; live microphone chunks are always saved under recorded_audio_chunks/.",
    )
    live.add_argument("--out-dir", default=None)

    replay_live = sub.add_parser("replay-live", help="Replay a completed live run with its recorded_audio.wav.")
    replay_live.add_argument("--run-dir", required=True, help="Live run directory containing story.json and recorded_audio.wav.")
    replay_live.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Fallback slide duration. Defaults to the live run chunk length recorded in run_manifest.json.",
    )
    replay_live.add_argument("--host", default=None)
    replay_live.add_argument("--port", type=int, default=None)
    replay_live.add_argument("--delay", type=float, default=0.0)
    replay_live.add_argument(
        "--playback",
        choices=["python", "processing"],
        default="python",
        help="Play recorded audio with local Python or inside host Processing.",
    )
    replay_live.add_argument(
        "--include-images",
        action="store_true",
        default=True,
        help="Send saved local image paths to Processing. Enabled by default.",
    )
    replay_live.add_argument("--no-images", dest="include_images", action="store_false", help="Replay text only.")

    images = sub.add_parser("generate-images", help="Generate/retrieve image assets without running audio/story.")
    images.add_argument("--story-json", required=True, help="Existing story.json to use as input.")
    images.add_argument(
        "--write-input-only",
        action="store_true",
        help="Write debug/scene_cards.json and exit without images.",
    )
    images.add_argument("--image-provider", choices=["imagen", "openverse"], required=True)
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
    osc.add_argument(
        "--include-images",
        action="store_true",
        default=True,
        help="Send /image messages for local image assets. Enabled by default for replay.",
    )
    osc.add_argument("--no-images", dest="include_images", action="store_false", help="Replay text only.")
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
            startup_buffer_fragments=args.startup_buffer_fragments,
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

    if args.command == "run-live":
        if args.list_input_devices:
            devices = list_audio_input_devices()
            if devices:
                print("Input devices visible inside this environment:")
                for device in devices:
                    print(f"- {device}")
            else:
                print("No input devices are visible inside this environment.")
            return
        if args.test_input_seconds is not None:
            print(
                f"Recording {max(0.1, args.test_input_seconds):.1f}s from "
                f"{args.input_device or 'the default input device'}. Speak or clap now..."
            )
            levels = test_audio_input_device(
                input_device=args.input_device,
                sample_rate=args.sample_rate,
                seconds=args.test_input_seconds,
            )
            print(f"RMS={levels['rms']:.6f} PEAK={levels['peak']:.6f}")
            print("MIC_OK" if levels["peak"] > 0.01 else "MIC_SIGNAL_LOW")
            return
        if args.duration_seconds is None:
            parser.error("run-live requires --duration-seconds unless --list-input-devices or --test-input-seconds is used.")
        result = run_live_pipeline(
            settings=settings,
            duration_seconds=args.duration_seconds,
            input_device=args.input_device,
            sample_rate=args.sample_rate,
            chunk_s=args.chunk_seconds,
            words_per_fragment=args.words_per_fragment,
            music_window_s=args.music_window_seconds,
            story_wpm=args.story_wpm,
            music_windows_per_fragment=args.music_windows_per_fragment,
            startup_delay_s=args.startup_delay,
            startup_buffer_fragments=args.startup_buffer_fragments,
            generate_images=args.generate_images,
            image_provider=args.image_provider,
            max_image_assets=args.max_image_assets,
            output_dir=Path(args.out_dir).expanduser() if args.out_dir else None,
            debug_artifacts=args.debug_artifacts,
            keep_audio_chunks=args.keep_audio_chunks,
        )
        print(f"Live run complete: {result.run_id}")
        print(f"Fragments: {len(result.fragments)}")
        print(f"Output directory: {args.out_dir or settings.output_dir}")
        print("Playback: none during live run (Processing visuals only)")
        return

    if args.command == "replay-live":
        run_dir = Path(args.run_dir).expanduser()
        story_json_path = run_dir / "story.json"
        recorded_audio_path = run_dir / "recorded_audio.wav"
        manifest_path = run_dir / "run_manifest.json"
        if not story_json_path.exists():
            parser.error(f"replay-live could not find story.json in {run_dir}.")
        if not recorded_audio_path.exists():
            parser.error(f"replay-live could not find recorded_audio.wav in {run_dir}.")

        fragments = story_fragments_from_json(story_json_path)
        manifest = read_json(manifest_path) if manifest_path.exists() else {}
        metadata = manifest.get("metadata", {}) if isinstance(manifest, dict) else {}
        fallback_duration_s = float(args.duration or metadata.get("chunk_s") or settings.live_story_scene_s)
        send_fragments_to_processing(
            fragments=fragments,
            host=args.host or settings.osc_host,
            port=args.port or settings.osc_port,
            slide_duration_s=fallback_duration_s,
            start_delay_s=args.delay,
            include_images=args.include_images,
            audio_path=recorded_audio_path if args.playback == "python" else None,
            processing_audio_path=recorded_audio_path if args.playback == "processing" else None,
            ready_port=settings.osc_ready_port,
            ready_bind_host=settings.osc_ready_bind_host,
            ready_timeout_s=settings.processing_ready_timeout_s,
        )
        print(f"Replayed live run: {run_dir}")
        print(f"Fragments: {len(fragments)}")
        print(f"Playback: {args.playback}")
        return

    if args.command == "generate-images":
        fragments = story_fragments_from_json(Path(args.story_json).expanduser())
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
        sibling_processing_audio = story_json_path.parent / "processing_audio.wav"
        if not audio_path and sibling_processing_audio.exists():
            processing_audio_path = sibling_processing_audio.expanduser().resolve()
        if args.playback == "processing":
            if not audio_path and not processing_audio_path:
                parser.error("send-osc --playback processing requires --audio.")
            target_audio_path = story_json_path.parent / "processing_audio.wav"
            if audio_path:
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
    commands = {"run-fragments", "run-live", "replay-live", "generate-images", "send-osc"}
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


def scene_cards_from_fragments(fragments: list[StoryFragment]) -> list[dict[str, object]]:
    return PipelineResult(
        run_id="image-only-input",
        audio_path="image-only",
        music_segments=[],
        fragments=fragments,
        full_story="\n\n".join(fragment.text for fragment in fragments),
    ).scene_cards()
