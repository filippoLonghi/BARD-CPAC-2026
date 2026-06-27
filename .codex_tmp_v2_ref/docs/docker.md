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
```

Rebuild after Python dependency or Dockerfile changes. Ordinary runs reuse `bard-cpac:local`.

## Complete Gemini Image Test

Open Processing and press **Run** first. This example uses `dark_suspense.ogg`, not Arabesque:

```powershell
docker compose run --rm --service-ports `
  -v "${ENV_FILE}:/secrets/bard-local.env:ro" `
  -v "${GCP_KEY}:/secrets/gcp.json:ro" `
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp.json `
  bard --env-file /secrets/bard-local.env run-fragments `
  --audio /workspace/data/test_audio/dark_suspense.ogg `
  --story-language Italian `
  --story-level early-reader `
  --generate-images `
  --image-provider imagen `
  --max-image-assets 3 `
  --playback processing `
  --send-osc `
  --out-dir /workspace/runs/dark-suspense-docker-gemini-image
```

This is a paid test. `dark_suspense.ogg` is about 140 seconds, so the defaults produce three scenes
and nine images. The `imagen` provider name is kept for backwards-compatible commands, but it now
uses the configured Gemini image model:

```env
BARD_IMAGE_MODEL=gemini-2.5-flash-image
BARD_IMAGE_LOCATION=global
BARD_REMOVE_IMAGE_BACKGROUND=true
BARD_BACKGROUND_REMOVAL_PROVIDER=rembg
```

The command prints the planned call count before cloud work begins. Check current Google pricing for
the selected Gemini image model before a paid run.

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
- `U2NET_HOME=/workspace/.cache/rembg` for the background-removal model cache;
- `runs/` as a bind-mounted local output directory.

Only one BARD container using `--service-ports` can own UDP port 5007 at a time.

## Credentials

The command mounts the JSON key read-only and overrides any Windows credential path stored in
`bard-local.env`. The project ID, regions, models, bucket, and story defaults still come from that env
file. Never copy credentials into the Docker image or repository.

For a keyless team setup, each member can instead mount their Application Default Credentials file
to `/secrets/application_default_credentials.json` and set `GOOGLE_APPLICATION_CREDENTIALS` to that
container path.

`rembg` may download its background-removal ONNX model on first use. Because `.cache/rembg` lives in
the mounted workspace and is ignored by git, the model can be reused by later Docker runs without
committing it.

## Outputs

Results remain visible on Windows under the selected `runs/<name>/` directory because the repository
is bind-mounted. Docker additionally creates `processing_audio.wav` for host Processing playback.

If `BARD_STORAGE_BUCKET` is set, the current sequential runner also uploads the completed run
directory to `gs://<bucket>/runs/<run-id>/`. Remove or leave that setting empty when you want a
strictly local-output test.

## Tests In Docker

After dependency or Dockerfile changes:

```powershell
docker compose build bard
docker compose run --rm --entrypoint python bard -m pytest -q
```

The unit tests mock Gemini image responses and do not require live GCP calls.
