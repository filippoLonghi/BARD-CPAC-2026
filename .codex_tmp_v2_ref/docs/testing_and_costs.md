# End-To-End Testing And Cost

Prices below were checked on June 13, 2026. Verify them before a public performance because cloud
pricing and model availability can change.

For the canonical complete-pipeline commands and all current parameter effects, start with
[running_the_pipeline.md](running_the_pipeline.md). This document contains additional test scenarios
and cost examples.

## Setup

```powershell
$WORKSPACE=(Resolve-Path ..).Path
$ENV_FILE=Join-Path $WORKSPACE "Project\secrets\bard-local.env"

.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[api,cloud]"
gcloud auth application-default login
```

Install Processing 4 and `oscP5`, then open:

```text
apps/processing/bard_story_visuals/bard_story_visuals.pde
```

Press Run before starting a command containing `--send-osc`. Processing waits on its title screen
while scene 1 is prepared. Music starts only after scene 1 has non-empty story text, at least one
usable image, and the OSC messages have had the configured startup delay to settle. Later scenes
continue generating during playback.

## Hybrid Call Plan

The defaults are 15-second musical observations grouped into 60-second story scenes. For a
281-second recording such as `arabesque.mp3`, this is approximately:

| Stage | Old design | Hybrid design |
|---|---:|---:|
| Fine music observations | 19 | 19 |
| Gemini audio calls | 19 | 5 |
| Music-to-story LLM calls | 19 | 0 (local mapping) |
| Story calls, including bible | 20 | 6 |
| Images at three per story scene | 57 | 15 |

At the documented Imagen 4 Fast price of `$0.02/image`, the image portion falls from about `$1.14`
to `$0.30`. Openverse remains `$0` for image API usage. As of June 14, 2026, Gemini 2.5 Flash
standard pricing lists audio input at `$1/1M audio tokens`, ordinary text/image/video input at
`$0.30/1M tokens`, and text output at `$2.50/1M tokens`. Grouping does not remove the cost of
listening to the complete recording, but it removes repeated prompt/output overhead and 19 separate
music-to-story LLM calls. A practical Arabesque hybrid run should normally keep Gemini analysis and
story cost in the low cents; allow roughly `$0.02-$0.06`, then add `$0.30` for 15 Imagen Fast images.
Every run writes planned counts under `metadata.estimated_api_calls`.

Pricing source: [Google Cloud generative AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing).

Python also performs an OSC readiness handshake before the cloud pipeline begins. If Processing is
closed or has crashed, the command stops with a clear `/prepare` timeout rather than spending money
and starting audio into a blank screen. After scene 1 arrives, Processing preloads its images and
answers `/primed`; only then do the Processing clock and source audio start.

## Debug Per-Fragment Analysis

This command makes three exact chunks without creating images:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\sad_walk_komiku.ogg `
  --fragments 3 `
  --out-dir runs\debug-three-fragments
```

Listen to:

```text
runs/debug-three-fragments/audio_chunks/segment_001.wav
...
```

Compare each file with the matching object in:

```text
runs/debug-three-fragments/music_segments.json
```

The filename `sad_walk_komiku.ogg` is neutral on purpose. Its source title says “Sad walk with sad
piano”, but that title is not evidence that a piano is audible. BARD must infer instruments from each
chunk and may correctly return `uncertain`.

## Short Imagen Test: Three Scenes, Nine Images

Open Processing first, then run:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\dramatic_ending.ogg `
  --fragments 3 `
  --words-per-fragment 80 `
  --generate-images `
  --image-provider imagen `
  --max-image-assets 3 `
  --send-osc `
  --out-dir runs\imagen-three-fragments
```

This performs 3 grouped audio calls, no music-to-story LLM calls, 1 story-bible call, 3 story-scene
calls, and 9 Imagen calls. An extra repair call occurs only if a story scene materially exceeds its
word budget. The image portion is about `$0.18` at `$0.02/image`; allow roughly
`$0.19-$0.23` total depending on Gemini input/output size.

## Long Coherence Test With Openverse

The Schubert file is about 10 minutes 48 seconds and changes from Adagio to Allegro in the same
recording. Open Processing first:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\schubert_adagio_allegro.ogg `
  --chunk-seconds 60 `
  --story-language English `
  --story-level children `
  --generate-images `
  --image-provider openverse `
  --max-image-assets 3 `
  --send-osc `
  --out-dir runs\schubert-long-openverse
```

This produces 11 story fragments and plans 33 retrieved images. Openverse has no API charge, although
some searches may fail or be rate-limited. Gemini cost should usually remain in the low cents; budget
about `$0.03-$0.08` because sequential mode makes several structured calls per fragment.

For normal runs, omit both `--chunk-seconds` and `--fragments`. Use `--music-window-seconds` only
when testing how finely musical changes are detected. Story word count is derived from each longer
scene's exact duration, `--reading-wpm`, and `--text-coverage`.

Italian early-reader test using only Openverse for images:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\dramatic_ending.ogg `
  --fragments 3 `
  --story-language Italian `
  --story-level early-reader `
  --reading-wpm 105 `
  --text-coverage 0.70 `
  --generate-images `
  --image-provider openverse `
  --max-image-assets 3 `
  --send-osc `
  --out-dir runs\italian-openverse
```

The command stays active while the music plays so `pygame` remains alive. Replay the saved result
without new cloud or Openverse calls:

```powershell
python -m bard_core --env-file "$ENV_FILE" send-osc `
  --story-json runs\italian-openverse\story.json `
  --audio data\test_audio\dramatic_ending.ogg `
  --include-images `
  --delay 0
```

## Planned-Duration Live Simulation

This is not microphone capture yet. It uses an uploaded file fragment by fragment, but plans the story
against a known performance duration:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio path\to\recorded-performance.wav `
  --chunk-seconds 20 `
  --planned-duration 600 `
  --generate-images `
  --image-provider openverse `
  --send-osc
```

If the file ends before the planned duration, the final available fragment is explicitly told to
resolve the story. True microphone/live capture still needs a recorder that closes and queues each WAV
window while the performance continues; the sequential runner and streaming OSC class are the reusable
downstream foundation for that worker.

## Cost Formula

The dominant predictable cost is image generation:

```text
Imagen cost = fragments * images_per_fragment * $0.02
```

Examples:

| Run | Imagen only | Typical total |
|---|---:|---:|
| 3 fragments x 3 images | `$0.18` | `$0.19-$0.23` |
| 5 fragments x 3 images | `$0.30` | `$0.31-$0.36` |
| 11 fragments x 3 images | `$0.66` | `$0.69-$0.78` |
| 11 fragments with Openverse | `$0` | `$0.03-$0.08` |

Processing and local WAV splitting cost nothing. Storage is negligible for these tests. Official
pricing lists Imagen 4 Fast at `$0.02/image`:
[Vertex AI generative AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing).

## Changing GCP Project

Do not edit the `project_id` text inside an old key and expect it to become a credential for another
project. Use a service account/key that belongs to the new project, or use Application Default
Credentials with an account that has access.

Update `bard-local.env` so these values agree:

```env
BARD_GCP_PROJECT_ID=NEW_PROJECT_ID
GOOGLE_CLOUD_PROJECT=NEW_PROJECT_ID
BARD_STORAGE_BUCKET=NEW_PROJECT_ID-bard-artifacts
BARD_GCP_LOCATION=europe-west1
BARD_IMAGEN_LOCATION=europe-west1
GOOGLE_APPLICATION_CREDENTIALS=C:\...\new-project-key.json
```

If you overwrite the old `bard-gcp-key.json` at the same path, the credential path can remain, but the
project IDs and bucket in `bard-local.env` still need changing. With ADC, the JSON file is ignored
unless `GOOGLE_APPLICATION_CREDENTIALS` points to it:

```powershell
gcloud config set project NEW_PROJECT_ID
gcloud auth application-default login
gcloud auth application-default set-quota-project NEW_PROJECT_ID
```

The new project also needs billing, Vertex AI, Cloud Storage if used, the target bucket, and suitable
IAM permissions.

Reading-rate reference: Marc Brysbaert, “How many words do we read per minute? A review and
meta-analysis of reading rate,” *Journal of Memory and Language* 109 (2019),
[DOI 10.1016/j.jml.2019.104047](https://doi.org/10.1016/j.jml.2019.104047).
