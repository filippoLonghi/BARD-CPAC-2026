# BARD-CPAC-2026

BARD is an after-score system: it listens to a unique human performance and turns it into a visible abstract narration.

BARD connects audio analysis, story generation, image assets, and a Processing sketch for live or near-live visuals:

```text
audio
-> performance / mood analysis
-> story fragments
-> visual prompts and image assets
-> Processing live composition
```

The goal is not to generate one finished video file. The goal is a live or near-live story-video: music starts, story fragments arrive after a delay, images arrive after another delay, and Processing combines text, colors, particles/effects, and generated image assets in real time.

## Start Here

For setup, follow:

[docs/gcp_setup.md](docs/gcp_setup.md)

That guide covers:

- installing Python, Docker, and Google Cloud CLI
- joining or creating the shared GCP project
- creating local private env files outside the repo
- running the local orchestrator with Vertex AI

Each teammate should keep secrets outside this repo, using this assumed layout:

```text
<workspace>/
  BARD-CPAC-2026/
  Project/
    secrets/
      bard-local.env
```

Use [configs/local.example.env](configs/local.example.env) as the template for `bard-local.env`.

## Complete Pipeline

The canonical commands and explanation of every parameter are in
[docs/running_the_pipeline.md](docs/running_the_pipeline.md).

Open Processing, press Run, then execute:

```powershell
$WORKSPACE=(Resolve-Path ..).Path
$ENV_FILE=Join-Path $WORKSPACE "Project\secrets\bard-local.env"

python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\audio\dramatic_ending.ogg `
  --story-language Italian `
  --story-level early-reader `
  --generate-images `
  --image-provider openverse `
  --max-image-assets 2 `
  --send-osc `
  --out-dir runs\dramatic-ending-complete
```

Expected output:

```text
runs/dramatic-ending-complete/
  story.json
  run_manifest.json
  images/
```

Normal runs write compact replay data in `story.json` and technical/debug metadata, including the
elapsed timing trace, in `run_manifest.json`. Add `--debug-artifacts` for verbose debug files under
`debug/`, and `--keep-audio-chunks` to preserve per-fragment WAV chunks.

## Processing Replay Without APIs

Open the Processing sketch:

```text
apps/processing/bard_story_visuals
```

Press Run in Processing first, then replay the saved result:

```powershell
python -m bard_core --env-file "$ENV_FILE" send-osc `
  --story-json runs\dramatic-ending-complete\story.json `
  --delay 0
```

Replay sends saved images by default. If the run folder contains `processing_audio.wav`, Processing
preloads it and starts music with `/start`.

Current OSC messages:

```text
/reset
/prepare -> /ready
/config/duration <float seconds>
/config/streaming <int 0|1>
/segment <int segment_id> <string mood> <string full_text> <float start_s> <float end_s>
/keywords <int segment_id> <string...>
/image <int segment_id> <int layer_index> <string role> <string local_path>
/prime -> /primed
/start
/finish
```

For an uploaded-audio demo, BARD plans fragment boundaries first, then prepares fragment 1 only:
temporary audio chunk, Gemini audio observation, story text, and the two required image assets
(`background` and `subject`). Processing is primed and `/start` is sent only after fragment 1 is
complete. Fragment 2 and later are prepared while playback is already running. If a later fragment is
late or incomplete, Python logs the delay and keeps the current Processing scene rather than sending a
placeholder or incomplete visual.

The hybrid plan keeps fine timestamped music observations inside larger story/image scenes. The
committed defaults live in `src/bard_core/config.py` and are mirrored in `configs/timing.default.env`.
This preserves small musical changes without paying for a story call and two image calls for every
observation.

The story bible selects one deterministic world profile from the first available music observations.
The same descriptor chooses the same world, while different descriptors can move the story into places
such as a clockwork city, radio tower, moon archive, storm airship, festival harbor, or medieval citadel.
The Processing layout, story timing, WPM, scene duration, and stale-image persistence are intentionally unchanged.

Allowed moods:

```text
DARK, CALM, ANXIOUS, DENSE, RISING TENSION, RELEASE, BRIGHT, SPARSE
```

This list is shared exactly between `src/bard_core/contracts.py` and Processing `MoodManager.pde`.
Invalid Python moods normalize to `CALM` before OSC.

## Optional Image Keyframes

Image assets are opt-in so normal runs do not spend money. Start with the free Openverse retrieval path:

```powershell
python -m bard_core --env-file "$ENV_FILE" generate-images `
  --story-json runs\dramatic-ending-analysis\story.json `
  --image-provider openverse `
  --out-dir runs\dramatic-ending-images-openverse
```

Then try generated images with Imagen:

```powershell
python -m bard_core --env-file "$ENV_FILE" generate-images `
  --story-json runs\dramatic-ending-analysis\story.json `
  --image-provider imagen `
  --max-image-assets 1 `
  --out-dir runs\dramatic-ending-images-imagen
```

See [docs/image_generation.md](docs/image_generation.md) for image providers, costs, compact output files, and debugging.

Current generated image assets are only `background` and `subject`. Generated subject assets are cut out in Python into transparent PNGs before Processing
receives them; Processing uses alpha pixels for cutouts and only falls back to color flood-fill when
an input image has no alpha channel.

## Docker Quick Check

```powershell
docker compose build
docker compose run --rm bard --help
```

## Documents

- [docs/gcp_setup.md](docs/gcp_setup.md): team setup, GCP, and local env.
- [docs/running_the_pipeline.md](docs/running_the_pipeline.md): canonical terminal commands and parameter effects.
- [docs/docker.md](docs/docker.md): no-venv Docker Desktop build and complete pipeline commands.
- [docs/future_development.md](docs/future_development.md): roadmap, live pipeline, model freedom, team roles.
- [docs/limitations_and_development.md](docs/limitations_and_development.md): known limits, latency, costs, and next steps.
- [docs/image_generation.md](docs/image_generation.md): Imagen, Openverse, scene cards, and Processing image OSC.
- [docs/architecture.md](docs/architecture.md): current technical architecture and provider structure.
- [docs/pipeline_data.md](docs/pipeline_data.md): exact JSON and OSC data passed between every stage.
- [docs/testing_and_costs.md](docs/testing_and_costs.md): test tracks, Processing order, commands, and per-run cost.
- [docs/timing_and_sync.md](docs/timing_and_sync.md): audio master clock, reading speed, image reveals, and free replay.
- [docs/project_structure.md](docs/project_structure.md): where files live in the repo.
- [docs/public_release_checklist.md](docs/public_release_checklist.md): quick checks before publishing the repo.
- [configs/local.example.env](configs/local.example.env): local private env template.
- [configs/timing.default.env](configs/timing.default.env): non-secret snapshot of shared timing defaults.

## License

Code and documentation are released under the [MIT License](LICENSE). Third-party media keep their
own licenses; see [NOTICE.md](NOTICE.md) and [data/audio/README.md](data/audio/README.md).

