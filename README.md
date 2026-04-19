# BARD-CPAC-2026

BARD is an after-score system: it listens to a unique human performance and turns it into a visible abstract narration.

The current prototype is moving from a hackathon script toward a live architecture:

```text
audio
-> performance / mood analysis
-> story fragments
-> visual prompts and future image keyframes
-> Processing live composition
```

The goal is not to generate one finished video file. The goal is a live or near-live story-video: music starts, story fragments arrive after a delay, images arrive after another delay, and Processing combines text, colors, particles/effects, and generated image assets in real time.

## Start Here

For setup, follow:

[docs/gcp_setup.md](docs/gcp_setup.md)

That guide covers:

- installing Python, Docker, and Google Cloud CLI
- joining or creating the shared GCP project
- creating local private env files outside the repo
- running the local orchestrator with Vertex AI
- deploying and testing Cloud Run

Each teammate should keep secrets outside this repo, using this assumed layout:

```text
<workspace>/
  BARD-CPAC-2026/
  Project/
    secrets/
      bard-local.env
```

Use [configs/local.example.env](configs/local.example.env) as the template for `bard-local.env`.

## Recommended Smoke Test

After setup, run the cloud-oriented local pipeline:

```powershell
$WORKSPACE=(Resolve-Path ..).Path
$ENV_FILE=Join-Path $WORKSPACE "Project\secrets\bard-local.env"

python -m bard_core --env-file "$ENV_FILE" run-local --audio data/audio/audio.mp3 --audio-provider gemini --story-provider vertex
```

Expected output:

```text
runs/<timestamp>/
  result.json
  music_segments.json
  story.json
  full_story.txt
```

## Processing Test

Open the Processing sketch:

```text
apps/processing/bard_story_visuals
```

Then run:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-local --audio data/audio/audio.mp3 --audio-provider gemini --story-provider vertex --send-osc
```

Current OSC messages:

```text
/config/duration <float seconds>
/segment <string mood> <string text>
/start
```

Allowed moods:

```text
ENERGETIC, SOLO, CALM, DEEP, DISSONANT, ANXIOUS
```

## Optional Local Prototype Path

The old hackathon-like local mode is still available:

```powershell
python -m pip install -e ".[local-ai]"
python -m bard_core --env-file "$ENV_FILE" run-local --audio data/audio/audio.mp3 --audio-provider clap --story-provider local
```

This runs CLAP and Mistral locally. It can be slow on CPU and may require a CUDA-enabled PyTorch install plus a Hugging Face token. For the main project direction, prefer the Vertex/GCP path.

## Documents

- [docs/gcp_setup.md](docs/gcp_setup.md): team setup, GCP, local env, Cloud Run.
- [docs/future_development.md](docs/future_development.md): roadmap, live pipeline, model freedom, team roles.
- [docs/architecture.md](docs/architecture.md): current technical architecture and provider structure.
- [docs/project_structure.md](docs/project_structure.md): where files live in the repo.
- [configs/local.example.env](configs/local.example.env): local private env template.
- [deploy/cloud-run.env.example](deploy/cloud-run.env.example): Cloud Run env template.

## Current Direction

Short term:

```text
audio -> Gemini/Vertex story fragments -> Processing via OSC
```

Next development:

```text
audio features + CLAP/Gemini
-> scene cards
-> story fragments
-> image prompts
-> generated abstract image keyframes
-> Processing live composition
```

Longer term, BARD should be model-flexible:

```text
audio_provider = gemini | clap | librosa | essentia | custom
story_provider = vertex | openai | anthropic | mistral | local
image_provider = imagen | openai | stable_diffusion | replicate | fal | comfyui
video_layer = processing | touchdesigner | ffmpeg | cloud video model
```
