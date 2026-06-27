# Image Generation And Retrieval

This document explains the optional image-keyframe stage for BARD.

For complete end-to-end commands, use [running_the_pipeline.md](running_the_pipeline.md).

The image stage runs after story generation:

```text
audio -> music segments -> story fragments -> image assets -> transparent PNGs -> Processing
```

It is optional. A normal story run does not generate images or spend money unless you pass
`--generate-images` or use the `generate-images` command.

## Providers

`imagen` is kept as the provider name for backwards compatibility with existing commands. Internally,
it now uses Gemini image models through the current Google Gen AI SDK / Vertex AI Agent Platform path.

Preferred env vars:

```env
BARD_IMAGE_PROVIDER=imagen
BARD_IMAGE_MODEL=gemini-2.5-flash-image
BARD_IMAGE_LOCATION=global
BARD_IMAGE_ASPECT_RATIO=1:1
BARD_IMAGE_TIMEOUT_S=120
```

Legacy names are still accepted:

```env
BARD_IMAGEN_MODEL=gemini-2.5-flash-image
BARD_IMAGEN_LOCATION=global
```

`gemini-2.5-flash-image` is the tested default for this project. You can set a newer Gemini image model
with `BARD_IMAGE_MODEL` after confirming it is available in your Google Cloud project and location.

`openverse` is the free smoke-test provider. It searches Openverse, downloads a PNG/JPEG result, and
stores attribution metadata in `scene_cards.json`. Openverse is best for testing the pipeline and OSC
image paths; it is not expected to match the generated story as tightly as Gemini images.

`replicate` runs FLUX.1 Schnell through Replicate. Set one of:

```env
BARD_REPLICATE_API_TOKEN=...
REPLICATE_API_TOKEN=...
```

## Background Removal

Generated subject and symbol assets are post-processed in Python before Processing receives them:

```env
BARD_REMOVE_IMAGE_BACKGROUND=true
BARD_BACKGROUND_REMOVAL_PROVIDER=rembg
```

The backend saves PNGs with RGBA alpha. Subject and symbol roles get background removal. Background
roles are converted to RGBA PNGs but kept visually intact, because they are meant to fill the scene.
Processing still has a fallback for old non-alpha images, but it now uses alpha when present and only
uses connected edge-color flood fill when no alpha exists.

`rembg` may download its ONNX model on first use. In Docker, `U2NET_HOME=/workspace/.cache/rembg` keeps
that model cache in the mounted workspace so later runs can reuse it.

## Audio-Driven Story Worlds

The story bible receives a deterministic world profile selected from extracted music descriptors:
valence, arousal, tension, music prompt, texture, dynamics, rhythmic character, instruments, and genre
candidates. Profiles include worlds such as cyberpunk rooftops, clockwork city, radio tower,
underwater ruins, moon archive, desert caravan, storm airship, volcanic workshop, polar observatory,
festival harbor, sky market, and medieval citadel.

To add a profile, edit `WORLD_PROFILES` and the candidate rules in
`src/bard_core/story/gemini_story.py::choose_world_profile`. Selection is deterministic: the audio
descriptors build a candidate set, and a SHA-256 hash picks a stable profile for repeated runs of the
same music.

## Mood Synchronization

Python mood labels live in `src/bard_core/contracts.py::MOOD_LABELS`:

```text
ENERGETIC, SOLO, CALM, DEEP, DISSONANT, ANXIOUS
```

Processing `MoodManager.pde` must define these exact labels. Old Processing labels remain aliases:
`DARK -> DEEP`, `DENSE -> DISSONANT`, `RISING TENSION` and `RISING_TENSION -> ANXIOUS`,
`RELEASE -> CALM`, `BRIGHT -> ENERGETIC`, and `SPARSE -> SOLO`.

## Scene Cards

Each run writes:

```text
runs/<run_id>/
  result.json
  music_segments.json
  story.json
  scene_cards.json
  full_story.txt
  images/
```

`scene_cards.json` is the best file to inspect when debugging images. Each card contains segment
timing, mood, story text, visual motif, palette, motion, and `image_assets`.

Each image asset keeps the existing fields:

```json
{
  "role": "subject",
  "label": "signal mask",
  "prompt": "A small brass signal mask...",
  "negative_prompt": "text, letters, watermark...",
  "provider": "imagen",
  "model": "gemini-2.5-flash-image",
  "status": "generated",
  "local_path": "C:/.../runs/<run_id>/images/segment_001_00_subject_signal_mask.png",
  "remote_url": null,
  "source_url": null,
  "license": null,
  "creator": null,
  "error": null
}
```

Possible statuses are `planned`, `generated`, `retrieved`, and `failed`.

## Commands

Fastest image-only fake-card test:

```powershell
$WORKSPACE=(Resolve-Path ..).Path
$ENV_FILE=Join-Path $WORKSPACE "Project\secrets\bard-local.env"

python -m bard_core --env-file "$ENV_FILE" generate-images --fake-card --image-provider openverse --out-dir runs\fake-image-test
```

Write and inspect only the fake input scene card before generating images:

```powershell
python -m bard_core generate-images --fake-card --fake-card-name cat-wood-sun --image-provider openverse --write-input-only --out-dir runs\fake-card-preview
notepad runs\fake-card-preview\scene_cards.json
```

Gemini image smoke test:

```powershell
python -m bard_core --env-file "$ENV_FILE" generate-images `
  --fake-card `
  --fake-card-name boat-fog-lantern `
  --image-provider imagen `
  --max-image-assets 1 `
  --out-dir runs\gemini-image-test
```

Full pipeline with generated images:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --generate-images `
  --image-provider imagen `
  --out-dir runs\arabesque-gemini-images
```

Processing test with generated/retrieved images:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --generate-images `
  --image-provider openverse `
  --send-osc `
  --out-dir runs\arabesque-processing-test
```

Send an existing generated `story.json` to Processing:

```powershell
python -m bard_core --env-file "$ENV_FILE" send-osc `
  --story-json runs\<run_id>\story.json `
  --audio path\to\the-original-audio.mp3 `
  --include-images `
  --delay 0
```

## GCP Checklist

1. Select or create a Google Cloud project and enable billing.
2. Enable the Vertex AI / Generative AI APIs required by the current SDK path.
3. In Google Cloud Console, open Vertex AI, Agent Studio, or Model Garden and verify the selected image
   model is available.
4. Test `gemini-2.5-flash-image` in the console with image output enabled.
5. Authenticate locally with Application Default Credentials or mount a service account JSON only for
   local development when appropriate.

Required local/Docker env:

```env
BARD_GCP_PROJECT_ID=your-project-id
GOOGLE_CLOUD_PROJECT=your-project-id
BARD_GCP_LOCATION=global
GOOGLE_CLOUD_LOCATION=global
BARD_IMAGE_PROVIDER=imagen
BARD_IMAGE_MODEL=gemini-2.5-flash-image
BARD_IMAGE_LOCATION=global
BARD_REMOVE_IMAGE_BACKGROUND=true
BARD_BACKGROUND_REMOVAL_PROVIDER=rembg
```

## Debugging

Missing GCP auth or project:

```text
Set BARD_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT before using the imagen image provider.
```

Fix: set the project env vars and run `gcloud auth application-default login`, or mount
`GOOGLE_APPLICATION_CREDENTIALS` into Docker.

Model unavailable:

- Confirm billing is enabled.
- Confirm the required APIs are enabled.
- Confirm `gemini-2.5-flash-image` is available in your project and location.
- If you choose a newer model, confirm that exact model is enabled in Model Garden first.

No image bytes or safety block:

- Inspect the failed asset in `scene_cards.json`.
- Simplify the prompt.
- Avoid people, violence, logos, copyrighted characters, and horror details.

Openverse no result or rate limit:

- Try fewer assets with `--max-image-assets 1`.
- Use a simpler visual label in the scene card.
- Run again later if the public API throttles requests.

Processing cannot load a path:

- Check that `local_path` exists in `scene_cards.json`.
- Use the same machine for Python/Docker and Processing.
- In Docker mode, set `BARD_HOST_WORKSPACE` so OSC paths map from `/workspace` to the Windows repo path.

## Tests

Unit tests mock the Gemini image response and do not call live GCP:

```powershell
python -m pytest -q
```

Docker validation:

```powershell
docker compose build bard
docker compose run --rm --entrypoint python bard -m pytest -q
```

Live GCP image tests are optional paid smoke tests and should be run separately after the unit suite passes.
