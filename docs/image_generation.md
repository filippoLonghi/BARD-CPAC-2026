# Image Generation And Retrieval

This document explains the image-keyframe layer used by BARD.

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
BARD_REMOVE_IMAGE_BACKGROUND=true
BARD_BACKGROUND_REMOVAL_PROVIDER=rembg
```

Do not switch to a newer image model unless it is verified in your configured GCP location. If the
selected model/location is unavailable, BARD raises a clear error instead of silently changing
providers.

For Imagen, BARD sends each asset's full `prompt` field. Imagen 4 does not use the `negative_prompt`
field in this implementation.

`openverse` is the free smoke-test provider. It does not generate a new image; it searches Openverse,
downloads a PNG/JPEG result, and stores attribution metadata in compact `story.json` plus
`run_manifest.json`.
For Openverse, BARD derives a one- or two-word search query locally from `search_query` or the asset
label, for example `radio tower` or `wooden ferry`. It does not spend an LLM call writing Openverse
queries. The longer `prompt` is reserved for generation models such as Imagen.

Current image assets are exactly two roles in order: `background`, then `subject`.

Background assets request a widescreen environment. Subject assets request the immutable cast identity
from the story bible and a plain simple background for backend cutout. Generated subject images are
postprocessed in Python with `rembg` into transparent PNGs before Processing receives them. Processing
uses alpha pixels for cutouts; color flood-fill is only a fallback when an input image has no alpha
channel.

The story bible also carries the deterministic audio-selected world profile. Image prompts append the
selected setting, cast style, and palette so the background and subject stay in the same world.

References:

- [Google Imagen prompt guide](https://cloud.google.com/vertex-ai/generative-ai/docs/image/img-gen-prompt-guide)
- [Openverse API reference](https://docs.openverse.org)

## Replay And Debug Records

Each normal run writes:

```text
runs/<run_id>/
  story.json
  run_manifest.json
  images/
```

`story.json` is the compact replay contract used by `send-osc`. It keeps the fields required for
replay/regeneration/licensing. `run_manifest.json` keeps technical metadata, model choices, timing
trace, and debug context. Add `--debug-artifacts` to write `debug/scene_cards.json`, which is the
verbose visual debugging view.

Each image asset has:

```json
{
  "role": "subject",
  "label": "brass clock helper",
  "prompt": "A simple recognizable brass clock helper...",
  "negative_prompt": "text, letters, watermark...",
  "provider": "imagen",
  "model": "imagen-4.0-fast-generate-001",
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

Set the private env path once:

```powershell
$WORKSPACE=(Resolve-Path ..).Path
$ENV_FILE=Join-Path $WORKSPACE "Project\secrets\bard-local.env"
```

Image-only generation from an existing `story.json`:

```powershell
python -m bard_core --env-file "$ENV_FILE" generate-images `
  --story-json runs\<run_id>\story.json `
  --image-provider openverse
```

Image-only output is intentionally small:

```text
runs/<image_test>/
  story.json              # replayable by the send-osc command
  run_manifest.json       # image metadata, errors, and timing trace
  images/                 # files that Processing can use
```

If fewer than two image files appear, open `run_manifest.json`; the missing layer should have
`status: "failed"` and an `error` in the debug context. Add `--debug-artifacts` for
`debug/scene_cards.json`.

Full pipeline Openverse smoke test:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\audio\dramatic_ending.ogg `
  --generate-images `
  --image-provider openverse `
  --out-dir runs\dramatic-ending-openverse
```

Imagen generation with GCP credits:

```powershell
python -m bard_core --env-file "$ENV_FILE" generate-images `
  --story-json runs\<run_id>\story.json `
  --image-provider imagen `
  --max-image-assets 1 `
  --out-dir runs\imagen-subject-test
```

Remove `--max-image-assets 1` when the first paid/GCP smoke test works.

Processing test with generated/retrieved images:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\audio\dramatic_ending.ogg `
  --generate-images `
  --image-provider openverse `
  --send-osc `
  --out-dir runs\dramatic-ending-processing-test
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

GCP billing/auth/model-region errors:

- Run `gcloud auth application-default login`.
- Confirm Vertex AI is enabled.
- Confirm the GCP project has billing or free credits.
- Confirm `BARD_IMAGE_MODEL` is available in `BARD_IMAGE_LOCATION`.
- For the current Europe setup, start with `imagen-4.0-fast-generate-001` in `europe-west1`.

Imagen safety block or no image bytes:

- Inspect the failed asset in `run_manifest.json`, or `debug/scene_cards.json` if you used `--debug-artifacts`.
- Simplify the prompt.
- Avoid people, violence, realistic body details, logos, and copyrighted characters.

Openverse no result or rate limit:

- Try fewer assets with `--max-image-assets 1`.
- Use a simpler visual label in the scene card.
- Run again later if the public API throttles requests.

Processing cannot load a path:

- Check that `local_path` exists in `story.json`.
- Use the same machine for Python and Processing.
- Prefer paths printed with forward slashes, like `C:/Users/...`, which the OSC sender now uses.

Background removal errors:

- Docker installs `rembg`, `onnxruntime`, and `Pillow` for the standard workflow.
- If `BARD_REMOVE_IMAGE_BACKGROUND=true` and `BARD_BACKGROUND_REMOVAL_PROVIDER=rembg`, missing
  `rembg` is a hard error. Use Docker or install the declared Python dependencies.
- Background/environment images normally remain full-frame and are not cut out.
