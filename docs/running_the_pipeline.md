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
  --max-image-assets 3 `
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
  --max-image-assets 3 `
  --send-osc `
  --out-dir runs\arabesque-imagen
```

With default 60-second scenes, Arabesque produces about five scenes and fifteen images. At
`$0.02` per Imagen 4 Fast image, the image portion is approximately `$0.30`.

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
| `--reading-wpm 120` | Assumed reading speed. Higher values permit more words. |
| `--text-coverage 0.72` | Fraction of scene time budgeted for text. Lower values create shorter text and more breathing room. |
| `--music-window-seconds 15` | Fine observation size inside a story scene. Smaller values capture more musical changes. |
| `--chunk-seconds 60` | Debug override for story-scene duration. Longer scenes mean fewer story/image calls. |
| `--fragments 3` | Debug alternative that divides the file into exactly N story scenes. |
| `--planned-duration 600` | Live-performance simulation: plans the story arc for this duration, while an uploaded file still ends at its real end. |
| `--words-per-fragment 80` | Manual word target. Normally omit it so duration and reading settings calculate the target. |
| `--target-words-per-fragment 72` | Preferred minimum used when deriving automatic scene duration. |
| `--generate-images` | Enables image retrieval/generation. Without it, no image provider runs. |
| `--image-provider openverse` | Free retrieval for tests. |
| `--image-provider imagen` | Paid Vertex AI image generation. |
| `--image-provider replicate` | Optional paid Replicate/FLUX experiment requiring its API token. |
| `--max-image-assets 3` | Maximum images per scene. Imagen cost scales directly with this value. |
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

The equivalent persistent defaults live in `bard-local.env` as `BARD_READING_WPM`,
`BARD_TEXT_COVERAGE`, `BARD_MUSIC_WINDOW_S`, `BARD_STORY_SCENE_S`,
`BARD_PROCESSING_STARTUP_DELAY_S`, and the image/OSC settings shown in
`configs/local.example.env`. A command-line option overrides the corresponding setting for one run.

## Recommended Adjustments

- More coherence and lower cost: increase `--chunk-seconds`, for example `75`.
- More frequent story/image changes: decrease `--chunk-seconds`, with higher API cost.
- Finer mood tracking without more images: decrease `--music-window-seconds`.
- Less text and longer reading pauses: reduce `--text-coverage` or `--reading-wpm`.
- Free visual testing: use `openverse`.
- Final generated visuals: use `imagen`.

Do not set both `--chunk-seconds` and `--fragments`; they are mutually exclusive.
