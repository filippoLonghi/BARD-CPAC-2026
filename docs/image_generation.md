# Image Generation And Retrieval

This document explains the first image-keyframe implementation for BARD.

For complete end-to-end commands, use [running_the_pipeline.md](running_the_pipeline.md).

The image stage runs after story generation:

```text
audio -> music segments -> story fragments -> image assets -> Processing
```

It is optional. A normal story run does not generate images or spend money unless you pass `--generate-images`.

## Providers

`imagen` is the scalable GCP provider. It runs Imagen through Vertex AI using the existing Google Gen AI SDK and the same GCP auth as the Gemini story/audio path.
The default remains the Europe-compatible Imagen model used by the current setup:

```env
BARD_IMAGE_PROVIDER=imagen
BARD_IMAGE_MODEL=imagen-4.0-fast-generate-001
BARD_IMAGE_LOCATION=europe-west1
BARD_IMAGEN_MODEL=imagen-4.0-fast-generate-001
BARD_IMAGEN_LOCATION=europe-west1
BARD_REMOVE_IMAGE_BACKGROUND=true
BARD_BACKGROUND_REMOVAL_PROVIDER=rembg
```

`BARD_IMAGE_MODEL` and `BARD_IMAGE_LOCATION` are clearer aliases. The older `BARD_IMAGEN_MODEL`
and `BARD_IMAGEN_LOCATION` names still work. Do not switch to a newer image model unless it is
verified in your configured GCP location. If the selected model/location is unavailable, BARD raises
a clear error instead of silently changing providers.

For Imagen, BARD sends each asset's full `prompt` field. Imagen 4 does not use the `negative_prompt`
field in this implementation.

`openverse` is the free smoke-test provider. It does not generate a new image; it searches Openverse, downloads a PNG/JPEG result, and stores attribution metadata in `scene_cards.json`.
For Openverse, BARD derives a one- or two-word search query locally from `search_query` or the asset
label, for example `radio tower` or `wooden ferry`. It does not spend an LLM call writing Openverse
queries. The longer `prompt` is reserved for generation models such as Replicate and Imagen.

Current image assets are exactly two roles in order: `background`, then `subject`. Symbol images are
intentionally disabled for now; the story writer does not plan them, image generation does not create
them, and OSC does not send them.

Background assets request a widescreen environment. Subject assets request the immutable cast identity
from the story bible and a plain simple background for backend cutout. Generated subject images are
postprocessed in Python with `rembg` into transparent PNGs before Processing receives them. Processing
uses alpha pixels for cutouts; color flood-fill remains only as a fallback for non-alpha legacy images.

The story bible also carries the deterministic audio-selected world profile. Image prompts append the
selected setting, cast style, and palette so the background and subject stay in the same world.

References:

- [Google Imagen prompt guide](https://cloud.google.com/vertex-ai/generative-ai/docs/image/img-gen-prompt-guide)
- [Openverse API reference](https://docs.openverse.org/api/reference.html)

`replicate` runs FLUX.1 Schnell through Replicate. It is the cheap generated-image path. Set one of:

```env
BARD_REPLICATE_API_TOKEN=...
REPLICATE_API_TOKEN=...
```

## Scene Cards

Each run now writes:

```text
runs/<run_id>/
  result.json
  music_segments.json
  story.json
  scene_cards.json
  full_story.txt
  images/
```

`scene_cards.json` is the best file to inspect when debugging images. Each card contains the segment timing, mood, story text, visual motif, palette, motion, and `image_assets`.

Each image asset has:

```json
{
  "role": "subject",
  "label": "brass clock helper",
  "prompt": "A simple recognizable brass clock helper...",
  "negative_prompt": "text, letters, watermark...",
  "provider": "replicate",
  "model": "black-forest-labs/flux-schnell",
  "status": "generated",
  "local_path": "C:/.../runs/<run_id>/images/segment_001_00_subject_cat.png",
  "remote_url": "https://...",
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

The fake cards are generated from the Python code, so they do not appear in a folder until you run `--write-input-only` or generate images from them.

List the available fake cards:

```powershell
python -m bard_core generate-images --list-fake-cards --image-provider openverse
```

Choose a specific fake card:

```powershell
python -m bard_core generate-images --fake-card --fake-card-name boat-fog-lantern --image-provider openverse --out-dir runs\boat-image-test
```

Available fake cards:

```text
cat-wood-sun
girl-tower-moon
boat-fog-lantern
fox-snow-fire
door-garden-key
```

If you do not have an env file yet, omit the global option completely:

```powershell
python -m bard_core generate-images --fake-card --image-provider openverse --out-dir runs\fake-image-test
```

Do not run `--env-file "$ENV_FILE"` when `$ENV_FILE` is empty. In PowerShell that can make `--env-file`
consume the command name and produce an error like `invalid choice: 'data/audio/audio.mp3'`.

Image-only generation from an existing `story.json`:

```powershell
python -m bard_core --env-file "$ENV_FILE" generate-images --story-json runs\<run_id>\story.json --image-provider openverse
```

Image-only output is intentionally small:

```text
runs/<image_test>/
  story.json              # replayable by the send-osc command
  scene_cards.json        # input card, updated with statuses after generation
  image_manifest.json     # image-only output metadata and errors
  images/                 # files that Processing can use
```

If fewer than two image files appear, open `image_manifest.json`; the missing layer should have
`status: "failed"` and an `error`.

Full pipeline Openverse smoke test:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --generate-images `
  --image-provider openverse `
  --out-dir runs\arabesque-openverse
```

Cheap FLUX generation:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --generate-images `
  --image-provider replicate `
  --out-dir runs\arabesque-replicate
```

Imagen generation with GCP credits:

```powershell
python -m bard_core generate-images --fake-card --fake-card-name cat-wood-sun --image-provider imagen --max-image-assets 1 --out-dir runs\imagen-subject-test
```

Remove `--max-image-assets 1` when the first paid/GCP smoke test works.

If you have a private env file path in `$ENV_FILE`, this also works:

```powershell
python -m bard_core --env-file "$ENV_FILE" generate-images --fake-card --fake-card-name cat-wood-sun --image-provider imagen --max-image-assets 1 --out-dir runs\imagen-subject-test
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

## Debugging

Missing Replicate token:

```text
Set REPLICATE_API_TOKEN or BARD_REPLICATE_API_TOKEN before using the replicate image provider.
```

Fix: create a Replicate token, keep it outside the repo, and add it to your private env file.

GCP billing/auth/model-region errors:

- Run `gcloud auth application-default login`.
- Confirm Vertex AI is enabled.
- Confirm the GCP project has billing or free credits.
- Confirm `BARD_IMAGE_MODEL`/`BARD_IMAGEN_MODEL` is available in `BARD_IMAGE_LOCATION`/`BARD_IMAGEN_LOCATION`.
- For the current Europe setup, start with `imagen-4.0-fast-generate-001` in `europe-west1`.

Imagen safety block or no image bytes:

- Inspect the failed asset in `scene_cards.json`.
- Simplify the prompt.
- Avoid people, violence, realistic body details, logos, and copyrighted characters.

Openverse no result or rate limit:

- Try fewer assets with `--max-image-assets 1`.
- Use a simpler visual label in the scene card.
- Run again later if the public API throttles requests.

Processing cannot load a path:

- Check that `local_path` exists in `scene_cards.json`.
- Use the same machine for Python and Processing.
- Prefer paths printed with forward slashes, like `C:/Users/...`, which the OSC sender now uses.

Background removal errors:

- Docker installs `rembg`, `onnxruntime`, and `Pillow` for the standard workflow.
- If `BARD_REMOVE_IMAGE_BACKGROUND=true` and `BARD_BACKGROUND_REMOVAL_PROVIDER=rembg`, missing
  `rembg` is a hard error. Use Docker or install the declared Python dependencies.
- Background/environment images normally remain full-frame and are not cut out.
