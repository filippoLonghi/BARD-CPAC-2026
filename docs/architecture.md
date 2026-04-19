# BARD Architecture

BARD is an after-score system: it gives a visible narrative trace to a unique human performance.

## Current Vertical Slice

```text
audio file
-> audio/emotion segmentation
-> coherent abstract story fragments
-> optional OSC messages to Processing
```

The new code lives in `src/bard_core`.

- `contracts.py`: shared JSON/data contracts.
- `audio/clap_provider.py`: reuses the wrapped hackathon CLAP implementation.
- `audio/gemini_provider.py`: Vertex/Gemini audio analysis for a cloud-light path.
- `story/local_mistral.py`: reuses the wrapped hackathon local Mistral story generator.
- `story/gemini_story.py`: Vertex/Gemini story generation with future visual fields.
- `transport/osc_sender.py`: sends `/config/duration`, `/segment`, and `/start` to Processing.
- `api.py`: small FastAPI service for Cloud Run experiments.

## Local Modes

Prototype-compatible mode:

```text
BARD_AUDIO_PROVIDER=clap
BARD_STORY_PROVIDER=local
```

Cloud-oriented mode:

```text
BARD_AUDIO_PROVIDER=gemini
BARD_STORY_PROVIDER=vertex
```

The cloud-oriented mode avoids hosting CLAP or Mistral yourself. It calls Vertex AI managed models and is the cheapest path to a deployable Cloud Run service.

## Processing Contract

Use the sketch in `apps/processing/bard_story_visuals` for now. It listens on port `5005`.

Python sends:

```text
/config/duration <float seconds>
/segment <string mood> <string text>
/start
```

Allowed moods:

```text
ENERGETIC, SOLO, CALM, DEEP, DISSONANT, ANXIOUS
```

## Target GCP Shape

```text
local performance machine
-> Cloud Run API
-> Vertex AI Gemini for audio/story
-> Cloud Storage for audio + generated artifacts
-> Cloud Tasks or Pub/Sub for async workers
-> local OSC/WebSocket bridge for Processing or TouchDesigner
```

The current `api.py` is synchronous on purpose. It is the smallest deployable step. Small local audio files are sent to Gemini inline; larger files can be uploaded to Cloud Storage when `BARD_STORAGE_BUCKET` is set. Each run can also upload JSON outputs to Cloud Storage. Once this works, split it into:

- request API
- audio/story worker
- image worker
- video/composition worker
- local bridge

## Next Architecture Step

Add image generation as another provider:

```text
StoryFragment.image_prompt
-> Gemini image or Imagen
-> keyframe assets
-> procedural animation/video compositor
```

For the final performance, keep a procedural fallback live locally while cloud-generated assets arrive with a deliberate delay.
