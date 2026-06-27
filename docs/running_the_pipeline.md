# Running The Complete Pipeline

This is the canonical command guide for the current hybrid pipeline.

For the no-venv Docker Desktop workflow, see [docker.md](docker.md).

## Terminal Setup

Open PowerShell in the repository:

```powershell
.\.venv\Scripts\Activate.ps1
$WORKSPACE=(Resolve-Path ..).Path
$ENV_FILE=Join-Path $WORKSPACE "Project\secrets\bard-local.env"
```

Before a command containing `--send-osc`, open
`apps/processing/bard_story_visuals/bard_story_visuals.pde` and press **Run**.

## Complete Pipeline With Free Images

This runs audio analysis, local music-to-story mapping, story generation, Openverse retrieval,
synchronized audio playback, and Processing:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --story-language Italian `
  --story-level early-reader `
  --generate-images `
  --image-provider openverse `
  --max-image-assets 2 `
  --send-osc `
  --out-dir runs\arabesque-complete
```

Openverse has no image API charge. Gemini audio and story calls still use GCP.

## Complete Pipeline With Imagen

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --story-language Italian `
  --story-level early-reader `
  --generate-images `
  --image-provider imagen `
  --max-image-assets 2 `
  --send-osc `
  --out-dir runs\arabesque-imagen
```

With default 60-second scenes, Arabesque produces about five scenes and ten images. At
`$0.02` per Imagen 4 Fast image, the image portion is approximately `$0.20`.

## Replay Existing Results Without APIs

```powershell
python -m bard_core --env-file "$ENV_FILE" send-osc `
  --story-json runs\arabesque-hybrid-test\story.json `
  --audio data\test_audio\arabesque.mp3 `
  --include-images `
  --delay 0
```

This makes no Gemini, Imagen, Openverse, or GCP calls. Use it for Processing tests.

## Analysis Without Processing Or Images

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --out-dir runs\arabesque-analysis
```

Inspect `music_segments.json`, `story.json`, and `audio_chunks/` in that output directory.

## Parameters

| Parameter | Effect |
|---|---|
| `--audio PATH` | Required source music file. |
| `--story-language Italian` | Audience-facing story language. Analysis and image prompts remain English. |
| `--story-level early-reader` | Vocabulary and sentence complexity: `early-reader`, `children`, `general`, or `literary`. |
| `--story-wpm 70` | Target displayed story words per minute. Higher values permit more words. |
| `--fragment-target-seconds 60` | Automatic balanced-splitting target duration. Usually omit and use the default. |
| `--music-windows-per-fragment 4` | Fine observations per story fragment when fixed music windows are not set. |
| `--music-window-seconds 15` | Optional fixed fine-observation size. Overrides derived windows-per-fragment timing. |
| `--chunk-seconds 60` | Debug override that preserves old fixed-size story-scene chunks. |
| `--fragments 3` | Debug alternative that divides the file into exactly N balanced story scenes. |
| `--planned-duration 600` | Live-performance simulation: plans the story arc for this duration, while an uploaded file still ends at its real end. |
| `--words-per-fragment 80` | Manual word target. Normally omit it so fragment duration and `--story-wpm` calculate the target. |
| `--generate-images` | Enables image retrieval/generation. Without it, no image provider runs. |
| `--image-provider openverse` | Free retrieval for tests. |
| `--image-provider imagen` | Paid Vertex AI image generation. |
| `--image-provider replicate` | Optional paid Replicate/FLUX experiment requiring its API token. |
| `--max-image-assets 2` | Maximum images per scene. Current roles are `background` and `subject`; Imagen cost scales directly with this value. |
| `--startup-delay 1.5` | Extra delay before Processing primes scene one. |
| `--playback python` | Local default. Use `processing` when Python runs inside Docker Desktop. |
| `--send-osc` | Sends data to Processing and plays the source audio. |
| `--out-dir PATH` | Output directory. Use a new directory for each cloud run. |

Replay-only `send-osc` parameters:

| Parameter | Effect |
|---|---|
| `--story-json PATH` | Saved story and image records to replay. |
| `--audio PATH` | Existing source audio to play with the saved timestamps. |
| `--include-images` | Sends saved local image paths to Processing. |
| `--delay 0` | Delay before the replay handshake. Usually keep `0` because readiness is checked explicitly. |
| `--duration 10` | Fallback scene duration only when saved fragments have no `start_s/end_s`. |
| `--host` / `--port` | Override the Processing OSC destination. |

Creative timing defaults live in code and the non-secret examples under `configs/timing.*.env`.
Do not put them in the private secrets env by default. A command-line option overrides the
corresponding setting for one run.

## Recommended Adjustments

- More coherence and lower cost: raise `--fragment-target-seconds`, or use explicit `--fragments`.
- More frequent story/image changes: lower `--fragment-target-seconds`, with higher API/image cost.
- Finer mood tracking without more images: increase `--music-windows-per-fragment`.
- Less text and longer reading pauses: reduce `--story-wpm`.
- Free visual testing: use `openverse`.
- Final generated visuals: use `imagen`.

Do not set both `--chunk-seconds` and `--fragments`; they are mutually exclusive.
