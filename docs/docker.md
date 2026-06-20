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

## Complete Imagen Test

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
  --out-dir /workspace/runs/dark-suspense-docker-imagen
```

This is a paid test. `dark_suspense.ogg` is about 140 seconds, so the defaults produce three scenes
and nine images. The Imagen portion is approximately `$0.18`:

```text
number of scenes * 3 * $0.02
```

The command prints the planned call count before cloud work begins.

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
- `runs/` as a bind-mounted local output directory.

Only one BARD container using `--service-ports` can own UDP port 5007 at a time.

## Credentials

The command mounts the JSON key read-only and overrides any Windows credential path stored in
`bard-local.env`. The project ID, regions, models, bucket, and story defaults still come from that env
file. Never copy credentials into the Docker image or repository.

For a keyless team setup, each member can instead mount their Application Default Credentials file
to `/secrets/application_default_credentials.json` and set `GOOGLE_APPLICATION_CREDENTIALS` to that
container path.

## Outputs

Results remain visible on Windows under the selected `runs/<name>/` directory because the repository
is bind-mounted. Docker additionally creates `processing_audio.wav` for host Processing playback.

If `BARD_STORAGE_BUCKET` is set, the current sequential runner also uploads the completed run
directory to `gs://<bucket>/runs/<run-id>/`. Remove or leave that setting empty when you want a
strictly local-output test.
