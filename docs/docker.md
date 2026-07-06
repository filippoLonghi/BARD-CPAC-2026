# Running BARD With Docker Desktop

Docker removes the Python virtual-environment setup for group members. Processing remains a host
application because it owns the full-screen window and speakers.

## Requirements

- Docker Desktop running with Linux containers.
- Processing 4 with `oscP5`, with `apps/processing/bard_story_visuals/bard_story_visuals.pde` open.
- The private `bard-local.env` and a valid GCP credential outside the repository.

## Build Once

Open PowerShell in the repository:

```powershell
$ENV_FILE=(Resolve-Path "..\Project\secrets\bard-local.env").Path
$GCP_KEY=(Resolve-Path "..\Project\secrets\bard-gcp-key.json").Path
$env:BARD_HOST_WORKSPACE=$PWD.Path

docker compose build bard
docker compose run --rm bard --help
```

Rebuild after Python dependency or Dockerfile changes. Ordinary runs reuse `bard-cpac:local`.
The Docker image installs the normal pipeline, OSC, Google providers, dev test runner, and
background-removal stack: `rembg`, `onnxruntime`, and `Pillow`.

Run tests in the same dependency environment with:

```powershell
docker compose run --rm --entrypoint python bard -m pytest
```

## Complete Imagen Test

Open Processing and press **Run** first. This example uses `dark_suspense.ogg`, not Arabesque:

```powershell
docker compose run --rm --service-ports `
  -v "${ENV_FILE}:/secrets/bard-local.env:ro" `
  -v "${GCP_KEY}:/secrets/gcp.json:ro" `
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp.json `
  bard --env-file /secrets/bard-local.env run-fragments `
  --audio /workspace/data/audio/dark_suspense.ogg `
  --story-language Italian `
  --story-level early-reader `
  --generate-images `
  --image-provider imagen `
  --max-image-assets 2 `
  --playback processing `
  --send-osc `
  --out-dir /workspace/runs/dark-suspense-docker-imagen
```

This is a paid test. `dark_suspense.ogg` is about 140 seconds, so the number of scenes follows the
timing defaults in `src/bard_core/config.py`. The Imagen portion is approximately:

```text
number of scenes * 2 * $0.02
```

The command prints elapsed trace lines for planning, first-fragment readiness, Processing priming,
`/start`, and later fragment preparation.

## Free Openverse Test

Use the same command but replace:

```text
--image-provider imagen
```

with:

```text
--image-provider openverse
```

and use a different output directory. Openverse retrieval has no image API charge.

## Live Microphone Recording

`run-live` is the performance-oriented path. It records microphone chunks and sends delayed visuals
to Processing. It never plays music from Python or Processing; the performer supplies the music live.
When image generation is enabled, BARD buffers complete story/image fragments before starting
Processing. Open Processing and press **Run** first.

On Windows laptops, run microphone live mode locally from the project `.venv`. Docker Desktop
commonly does not expose the laptop microphone to Linux containers; if the container cannot see the
mic, there is no `--input-device` value BARD can set to fix it.

Check local input devices:

```powershell
.\.venv\Scripts\Activate.ps1
python -m bard_core run-live --list-input-devices
python -m bard_core run-live --input-device 5 --test-input-seconds 5
```

Then run live recording, passing the device index printed by `--list-input-devices`:

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
  --max-image-assets 2 `
  --out-dir runs\live-mic-openverse
```

To review the completed live run later with the saved microphone recording:

```powershell
python -m bard_core --env-file "$ENV_FILE" replay-live `
  --run-dir runs\live-mic-openverse `
  --playback python `
  --delay 0
```

Docker is still useful for `run-fragments --audio` and other file-based tests. It can also replay a
completed live run if the run folder is mounted and you use `--playback processing`, but local Python
is usually simpler for laptop microphone capture and recorded-audio replay.

## Why `--playback processing` Is Required

Docker Desktop Linux containers do not receive the Windows speaker device reliably. In Docker mode,
BARD converts the source file to `processing_audio.wav` inside the mounted run directory. It sends
the corresponding Windows host path over OSC. Processing preloads that WAV, replies `/primed`, and
starts audio and visuals from the same `/start` event.

The same path translation is applied to generated/retrieved image files. The repository is mounted
at `/workspace`, while Processing receives paths under the real Windows repository directory.

## Docker Networking

`compose.yaml` configures:

- OSC output to `host.docker.internal:5005`;
- UDP readiness replies through published port `5007`;
- `BARD_OSC_READY_BIND_HOST=0.0.0.0` inside the container;
- `BARD_REMOVE_IMAGE_BACKGROUND=true`;
- `BARD_BACKGROUND_REMOVAL_PROVIDER=rembg`;
- `runs/` as a bind-mounted local output directory.

Only one BARD container using `--service-ports` can own UDP port 5007 at a time.

## Credentials

The command mounts the JSON key read-only and overrides any Windows credential path stored in
`bard-local.env`. The project ID, regions, models, bucket, and story defaults still come from that env
file. Never copy credentials into the Docker image or repository.

For the current Europe-compatible Google image setup, keep these in the env file unless you have
verified a different model/location:

```env
BARD_IMAGE_PROVIDER=imagen
BARD_IMAGE_MODEL=imagen-4.0-fast-generate-001
BARD_IMAGE_LOCATION=europe-west1
BARD_IMAGEN_MODEL=imagen-4.0-fast-generate-001
BARD_IMAGEN_LOCATION=europe-west1
```

For a keyless team setup, each member can instead mount their Application Default Credentials file
to `/secrets/application_default_credentials.json` and set `GOOGLE_APPLICATION_CREDENTIALS` to that
container path.

## Outputs

Results remain visible on Windows under the selected `runs/<name>/` directory because the repository
is bind-mounted. Normal output is compact: `story.json`, `run_manifest.json`, and `images/`. Docker
additionally creates `processing_audio.wav` for host Processing playback.

`run-live` does not create `processing_audio.wav` and does not send `/audio`; the run manifest records
`playback_mode: none`, `startup_buffer_fragments`, and the measured `visual_delay_s`. Live microphone
audio is preserved under `recorded_audio_chunks/` and BARD attempts to write a combined
`recorded_audio.wav` when the run ends.

Generated image assets contain only `background` and `subject`. Symbol images are intentionally
disabled for now. Python removes the background only from generated `subject` assets and writes
transparent PNGs before Processing receives them; `background` assets remain full-frame. The
Processing visual layout, timing, and stale-image persistence behavior are intentionally unchanged.

If `BARD_STORAGE_BUCKET` is set, the current sequential runner also uploads the completed run
directory to `gs://<bucket>/runs/<run-id>/`. Remove or leave that setting empty when you want a
strictly local-output test.
