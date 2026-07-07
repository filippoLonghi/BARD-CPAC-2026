# Running The Complete Pipeline

This is the canonical command guide for the current live/sequential file pipeline.

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
  --audio data\audio\dramatic_ending.ogg `
  --story-language Italian `
  --story-level early-reader `
  --generate-images `
  --image-provider openverse `
  --max-image-assets 2 `
  --send-osc `
  --out-dir runs\dramatic-ending-complete
```

Openverse has no image API charge. Gemini audio and story calls still use GCP.

## Complete Pipeline With Imagen

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\audio\dramatic_ending.ogg `
  --story-language Italian `
  --story-level early-reader `
  --generate-images `
  --image-provider imagen `
  --max-image-assets 2 `
  --send-osc `
  --out-dir runs\dramatic-ending-imagen
```

The number of scenes depends on the committed timing defaults in `src/bard_core/config.py` or any CLI
overrides. At `$0.02` per Imagen 4 Fast image, the image portion is roughly
`scene_count * 2 * $0.02` when using two image assets per scene.

## Replay Existing Results Without APIs

```powershell
python -m bard_core --env-file "$ENV_FILE" send-osc `
  --story-json runs\dramatic-ending-complete\story.json `
  --delay 0
```

This makes no Gemini, Imagen, Openverse, or GCP calls. Saved images are replayed by default. If the
run folder contains `processing_audio.wav`, audio is also preloaded in Processing and starts on
`/start`; otherwise pass `--audio path\to\source.wav`.

## Analysis Without Processing Or Images

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\audio\dramatic_ending.ogg `
  --out-dir runs\dramatic-ending-analysis
```

Inspect `story.json` and `run_manifest.json` in that output directory. Add `--debug-artifacts` and
`--keep-audio-chunks` when you need verbose debug files or exact chunk WAVs.

## Live Visuals

Use `run-live` for performance-style microphone visuals. Processing shows only story, mood,
particles, and images; neither Python nor Processing plays music during the live run. File-based
testing stays in `run-fragments --audio`.

On Windows laptops, run microphone live mode locally from the project `.venv`. Docker Desktop often
does not expose the built-in microphone to Linux containers, so the container may have no input
device for BARD to select:

```powershell
.\.venv\Scripts\Activate.ps1
python -m bard_core run-live --list-input-devices
python -m bard_core run-live --input-device 5 --test-input-seconds 5
```

During the test, speak or clap. `MIC_OK` means BARD received a clear signal; `MIC_SIGNAL_LOW` means
the selected device is silent, muted, blocked by Windows privacy settings, or the wrong input.

Then open Processing, press **Run**, and start the local live pipeline:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-live `
  --duration-seconds 60 `
  --chunk-seconds 15 `
  --music-window-seconds 15 `
  --startup-buffer-fragments 2 `
  --input-device 5 `
  --story-language Italian `
  --story-level early-reader `
  --generate-images `
  --image-provider openverse `
  --out-dir runs\live-mic-openverse
```

When the live run ends, BARD saves the microphone chunks and attempts to write
`recorded_audio.wav`. To review the same live run later with recorded audio playback, keep
Processing open and run:

```powershell
python -m bard_core --env-file "$ENV_FILE" replay-live `
  --run-dir runs\live-mic-openverse `
  --playback python `
  --delay 0
```

## Live/Sequential Behavior

`run-fragments` plans the fragment boundaries from the full file, then works one fragment at a time.
It does not analyze the full audio, write every chunk, generate the full story, or generate all images
before playback. Fragment 1 is fully prepared first: temporary audio chunk, audio analysis, story
text, and both required image roles (`background` and `subject`). By default BARD prepares two
complete fragments before it primes Processing and sends `/start`; Processing still starts from
fragment 1, with fragment 2 already queued while Python works on fragment 3. Tune this with
`--startup-buffer-fragments`: `1` starts as soon as fragment 1 is ready, `2` starts fragment 1 with
one ready fragment in reserve.

While fragment 1 is playing, Python prepares fragment 2, then fragment 3, and so on. A later fragment
is sent to Processing only after its story and images are ready. If it is late or incomplete, the
console trace and `run_manifest.json` record the delay; Processing keeps the current scene rather
than receiving placeholders.

Normal run artifacts are compact:

```text
runs/<run>/
  story.json          replay contract for send-osc
  run_manifest.json   config, models, trace, debug metadata
  images/             generated or retrieved image assets
```

With `--debug-artifacts`, verbose files are written under `debug/`:

```text
debug/result.json
debug/music_segments.json
debug/scene_cards.json
debug/full_story.txt
```

## Parameters

| Parameter | Effect |
|---|---|
| `--audio PATH` | Required source music file. |
| `--story-language Italian` | Audience-facing story language. Analysis and image prompts remain English. |
| `--story-level early-reader` | Vocabulary and sentence complexity: `early-reader`, `children`, `general`, or `literary`. |
| `--story-wpm 70` | Target displayed story words per minute. Higher values permit more words. |
| `--fragment-target-seconds 60` | Automatic balanced-splitting target duration. Usually omit and use the default. |
| `--music-windows-per-fragment 2` | Fine observations per story fragment when fixed music windows are not set. |
| `--music-window-seconds 15` | Optional fixed fine-observation size. Overrides derived windows-per-fragment timing. |
| `--chunk-seconds 60` | Debug override that uses fixed-size story-scene chunks. |
| `--fragments 3` | Debug alternative that divides the file into exactly N balanced story scenes. |
| `--planned-duration 600` | Live-performance simulation: plans the story arc for this duration, while an uploaded file still ends at its real end. |
| `--words-per-fragment 80` | Manual word target. Normally omit it so fragment duration and `--story-wpm` calculate the target. |
| `--generate-images` | Enables image retrieval/generation. Without it, no image provider runs. |
| `--image-provider openverse` | Free retrieval for tests. |
| `--image-provider imagen` | Paid Vertex AI image generation. |
| `--max-image-assets 2` | Maximum images per scene. Current roles are `background` and `subject`; Imagen cost scales directly with this value. |
| `--startup-delay 1.5` | Extra delay before Processing primes scene one. |
| `--startup-buffer-fragments 2` | Complete story/image fragments to prepare before Processing starts. Use `1` for faster start, or higher values for more safety. |
| `--playback python` | Local default. Use `processing` when Python runs inside Docker Desktop. |
| `--send-osc` | Sends data to Processing and plays the source audio. Requires `--generate-images` so playback never starts story-only. |
| `--debug-artifacts` | Writes verbose JSON/text files under `debug/`. |
| `--keep-audio-chunks` | Preserves per-fragment WAV chunks under `audio_chunks/`; otherwise chunks are temporary and removed after analysis. |
| `--out-dir PATH` | Output directory. Use a new directory for each run. |

Replay-only `send-osc` parameters:

| Parameter | Effect |
|---|---|
| `--story-json PATH` | Saved story and image records to replay. |
| `--audio PATH` | Optional source audio to play with the saved timestamps if `processing_audio.wav` is not already in the run folder. |
| `--playback processing` | Optional explicit Docker Desktop mode: convert/preload audio in Processing and start it on `/start`. |
| `--include-images` | Sends saved local image paths to Processing. Enabled by default. |
| `--no-images` | Replay text without saved image paths. |
| `--delay 0` | Delay before the replay handshake. Usually keep `0` because readiness is checked explicitly. |
| `--duration 10` | Fallback scene duration only when saved fragments have no `start_s/end_s`. |
| `--host` / `--port` | Override the Processing OSC destination. |

Live-only `run-live` parameters:

| Parameter | Effect |
|---|---|
| `--duration-seconds S` | Required planned performance/story duration. BARD does not infer it. |
| `--list-input-devices` | List microphone/input devices visible to the current Python environment and exit. |
| `--input-device INDEX_OR_NAME` | Select a visible `sounddevice` input device. |
| `--test-input-seconds 5` | Record a short local/device probe and print RMS/peak levels without OSC or API calls. |
| `--sample-rate 44100` | Recording sample rate for microphone chunks. |
| `--chunk-seconds S` | Live story-scene length. Defaults to `BARD_LIVE_STORY_SCENE_S`, currently `30`. |
| `--music-window-seconds S` | Fixed live music-analysis window. Use `15` with `--chunk-seconds 15` for one music window per fragment. |
| `--startup-buffer-fragments N` | Complete live fragments to prepare before the Processing visual clock starts. Defaults to `BARD_LIVE_STARTUP_BUFFER_FRAGMENTS`, currently `2`. |
| `--generate-images` | Enables image retrieval/generation. In live mode, generated images are sent with their fragment before Processing starts displaying that buffered fragment. |
| `--image-provider openverse|imagen` | Image backend for delayed `/image` messages. |

Replay-only `replay-live` parameters:

| Parameter | Effect |
|---|---|
| `--run-dir PATH` | Completed live run directory containing `story.json` and `recorded_audio.wav`. |
| `--playback python` | Play the recorded microphone WAV from local Python while Processing replays visuals. |
| `--playback processing` | Ask Processing to play `recorded_audio.wav` on `/start`. Useful only when Processing can see that path. |
| `--no-images` | Replay saved live text without image paths. |
| `--duration S` | Fallback scene duration only if saved fragments have no `start_s/end_s`. Defaults to the run's live chunk length. |

Live recordings are saved inside the run folder as `recorded_audio_chunks/segment_*.wav`. BARD also
attempts to write a combined `recorded_audio.wav` at the end of the run; if that combine step fails,
the original chunks remain available.

## Recommended Adjustments

- More coherence and lower cost: raise `--fragment-target-seconds`, or use explicit `--fragments`.
- More frequent story/image changes: lower `--fragment-target-seconds`, with higher API/image cost.
- Finer mood tracking without more images: increase `--music-windows-per-fragment`.
- Less text and longer reading pauses: reduce `--story-wpm`.
- Free visual testing: use `openverse`.
- Final generated visuals: use `imagen`.

Do not set both `--chunk-seconds` and `--fragments`; they are mutually exclusive.
