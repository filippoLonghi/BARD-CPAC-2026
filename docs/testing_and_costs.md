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
$GCP_KEY=Join-Path $WORKSPACE "Project\secrets\bard-gcp-key.json"

.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[cloud,dev]"
gcloud auth application-default login
```

The reproducible Docker test command is:

```powershell
docker compose run --rm --entrypoint python bard -m pytest
```

Install Processing 4 and `oscP5`, then open:

```text
apps/processing/bard_story_visuals/bard_story_visuals.pde
```

Press Run before starting a command containing `--send-osc`. Processing waits on its title screen
while scene 1 is prepared. Music starts only after scene 1 has non-empty story text and both required
image roles (`background` and `subject`) ready. Later scenes continue generating during playback; if
one is late or incomplete, Python logs the delay and Processing holds the current scene.

## Hybrid Call Plan

The default call count depends on `BARD_FRAGMENT_TARGET_S` and
`BARD_MUSIC_WINDOWS_PER_FRAGMENT` in `src/bard_core/config.py`. For a medium-length recording,
estimate the hybrid design as one audio call per story fragment, with multiple fine music
observations inside that call:

| Stage | Per-window design | Hybrid design |
|---|---:|---:|
| Fine music observations | 19 | 18 |
| Gemini audio calls | 19 | 9 |
| Music-to-story LLM calls | 19 | 0 (local mapping) |
| Story calls, including bible | 20 | 10 |
| Images at two per story scene | 38 | 18 |

At the documented Imagen 4 Fast price of `$0.02/image`, the image portion falls from about `$1.14`
to `$0.36`. Openverse remains `$0` for image API usage. As of June 14, 2026, Gemini 2.5 Flash
standard pricing lists audio input at `$1/1M audio tokens`, ordinary text/image/video input at
`$0.30/1M tokens`, and text output at `$2.50/1M tokens`. Grouping does not remove the cost of
listening to the complete recording, but it removes repeated prompt/output overhead and 19 separate
music-to-story LLM calls. A practical medium-length run should normally keep Gemini analysis and
story cost in the low cents; allow roughly `$0.02-$0.06`, then add `$0.36` for 18 Imagen Fast images.
Every run writes planned counts under `run_manifest.json` at `metadata.estimated_api_calls`.

Pricing source: [Google Cloud generative AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing).

Python also performs an OSC readiness handshake before remote model calls begin. If Processing is
closed or has crashed, the command stops with a clear `/prepare` timeout rather than spending money
and starting audio into a blank screen. After scene 1 arrives, Processing preloads its images and
answers `/primed`; only then do the Processing clock and source audio start.

## Debug Per-Fragment Analysis

This command makes three exact chunks without creating images:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\audio\sad_walk_komiku.ogg `
  --fragments 3 `
  --debug-artifacts `
  --keep-audio-chunks `
  --out-dir runs\debug-three-fragments
```

Listen to:

```text
runs/debug-three-fragments/audio_chunks/segment_001.wav
...
```

Compare each file with the matching object in:

```text
runs/debug-three-fragments/debug/music_segments.json
```

## Short Imagen Test: Three Scenes, Six Images

Open Processing first, then run:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\audio\dramatic_ending.ogg `
  --fragments 3 `
  --words-per-fragment 80 `
  --generate-images `
  --image-provider imagen `
  --max-image-assets 2 `
  --send-osc `
  --out-dir runs\imagen-three-fragments
```

This performs 3 grouped audio calls, no music-to-story LLM calls, 1 story-bible call, 3 story-scene
calls, and 6 Imagen calls. An extra repair call occurs only if a story scene materially exceeds its
word budget. The image portion is about `$0.12` at `$0.02/image`; allow roughly
`$0.13-$0.17` total depending on Gemini input/output size.

## Long Coherence Test With Openverse

The Schubert file is about 10 minutes 48 seconds and changes from Adagio to Allegro in the same
recording. Open Processing first:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\audio\schubert_adagio_allegro.ogg `
  --chunk-seconds 60 `
  --story-language English `
  --story-level children `
  --generate-images `
  --image-provider openverse `
  --max-image-assets 2 `
  --send-osc `
  --out-dir runs\schubert-long-openverse
```

This produces 11 story fragments and plans 22 retrieved images. Openverse retrieval itself is free,
although some searches may fail or be rate-limited. Gemini cost should usually remain in the low
cents; budget about `$0.03-$0.08` because sequential mode makes several structured calls per fragment.

For normal runs, omit `--chunk-seconds`, `--fragments`, and `--music-window-seconds`. Automatic
balanced splitting chooses story fragments near the configured target, and story word count is
derived from each fragment's exact duration and `BARD_STORY_WPM` / `--story-wpm`.

Italian early-reader test using only Openverse for images:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\audio\dramatic_ending.ogg `
  --fragments 3 `
  --story-language Italian `
  --story-level early-reader `
  --story-wpm 70 `
  --generate-images `
  --image-provider openverse `
  --max-image-assets 2 `
  --send-osc `
  --out-dir runs\italian-openverse
```

The command stays active while the music plays so `pygame` remains alive. Replay the saved result
without new Gemini, Imagen, or Openverse calls:

```powershell
python -m bard_core --env-file "$ENV_FILE" send-osc `
  --story-json runs\italian-openverse\story.json `
  --audio data\audio\dramatic_ending.ogg `
  --include-images `
  --delay 0
```

## Live Test Path

`run-live` records microphone chunks only and should be run locally from the project `.venv`. Docker
Desktop often cannot see the built-in mic, so file-based Docker tests stay under `run-fragments --audio`.

```powershell
python -m bard_core --env-file "$ENV_FILE" run-live `
  --duration-seconds 60 `
  --chunk-seconds 15 `
  --music-window-seconds 15 `
  --startup-buffer-fragments 2 `
  --input-device 5 `
  --generate-images `
  --image-provider openverse `
  --out-dir runs\live-mic-openverse
```

If live recording ends before the planned duration, the final available fragment is explicitly told to
resolve the story. Use `run-live --list-input-devices` to see what BARD can actually access. With
`--generate-images`, BARD prepares the configured startup buffer as complete story/image fragments
before Processing starts.

Replay the saved live run later with the combined recording:

```powershell
python -m bard_core --env-file "$ENV_FILE" replay-live `
  --run-dir runs\live-mic-openverse `
  --playback python `
  --delay 0
```

## Cost Formula

The dominant predictable cost is image generation:

```text
Imagen cost = fragments * images_per_fragment * $0.02
```

Examples:

| Run | Imagen only | Typical total |
|---|---:|---:|
| 3 fragments x 2 images | `$0.12` | `$0.13-$0.17` |
| 5 fragments x 2 images | `$0.20` | `$0.21-$0.26` |
| 11 fragments x 2 images | `$0.44` | `$0.47-$0.56` |
| 11 fragments with Openverse | `$0` image API cost | `$0.03-$0.08` including Gemini calls |

Processing and local WAV splitting cost nothing. Storage is negligible for these tests. Official
pricing lists Imagen 4 Fast at `$0.02/image`:
[Vertex AI generative AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing).

## Changing GCP Project

Do not edit the `project_id` text inside an existing key and expect it to become a credential for another
project. Use a service account/key that belongs to the new project, or use Application Default
Credentials with an account that has access.

Update `bard-local.env` so these values agree:

```env
BARD_GCP_PROJECT_ID=NEW_PROJECT_ID
GOOGLE_CLOUD_PROJECT=NEW_PROJECT_ID
BARD_STORAGE_BUCKET=NEW_PROJECT_ID-bard-artifacts
BARD_GCP_LOCATION=europe-west1
BARD_IMAGE_LOCATION=europe-west1
GOOGLE_APPLICATION_CREDENTIALS=C:\...\new-project-key.json
```

If you overwrite `bard-gcp-key.json` at the same path, the credential path can remain, but the
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
