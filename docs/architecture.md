# BARD Architecture

BARD is an after-score system: it gives a visible narrative trace to a unique human performance.

## Current Vertical Slice

```text
audio file
-> audio/emotion segmentation
-> coherent abstract story fragments
-> optional OSC messages to Processing
```

The Python package lives in `src/bard_core`.

- `contracts.py`: shared JSON/data contracts.
- `audio/gemini_provider.py`: Vertex/Gemini audio analysis for a cloud-light path.
- `audio/chunks.py`: saves independently analyzable WAV windows for sequential execution.
- `story/music_translation.py`: musical observations to music-free dramatic directions.
- `story/gemini_story.py`: persistent symbolic-adventure bible, deterministic audio-selected world profile, continuity state, and two visual assets per beat.
- `pipeline_sequential.py`: uploaded-file stream simulation and planned-duration live foundation.
- `images/`: optional image-keyframe providers for Vertex Imagen and Openverse retrieval.
- `transport/osc_sender.py`: sends `/config/duration`, `/segment`, optional `/image`, and `/start` to Processing.
- Before cloud work, Python sends `/prepare`; Processing replies `/ready` on port 5007.
- Before playback, Python sends `/prime`; Processing loads scene 1 and replies `/primed`.

The active pipeline is `bard run-fragments` with Gemini/Vertex story generation.

## Active Mode

```text
audio analysis: Gemini / Vertex AI
story generation: Gemini / Vertex AI
image assets: Openverse or Imagen when enabled
```

The active mode avoids hosting CLAP or Mistral yourself. It calls Vertex AI managed models and is
the current path for local Docker/Processing runs.
The older local CLAP and local Mistral wrappers are kept under `src/bard_core/legacy/` for reference;
they are not imported by `run-fragments` or `run-live`.

## API Surface

`src/bard_core/api.py` contains a small FastAPI application with a health endpoint. It is not the
main way to run BARD at the moment: the synchronous `/runs/sync` endpoint is disabled and points back
to the supported CLI path, `bard run-fragments`.

This means the API code is best read as a starting point for a future deployed service. A Cloud Run
deployment would make sense later because the project already uses Docker, GCP credentials, Vertex AI,
and optional Cloud Storage upload. The missing work is orchestration: accepting an audio upload,
starting a run, storing artifacts, reporting run status, and delivering image/audio paths back to a
local Processing bridge.

## Persistence On GCP

In the current sequential runner, `BARD_STORAGE_BUCKET` enables a final recursive upload of the run
directory to `gs://<bucket>/runs/<run-id>/`. This includes JSON contracts, story text, audio chunks,
images, and the Docker/Processing playback WAV when present. A mounted Docker workspace still keeps
the same files locally. Vertex AI model execution itself does not create application files in the BARD
bucket.

## Processing Contract

Use the sketch in `apps/processing/bard_story_visuals` for now. It listens on port `5005`.

Python sends:

```text
/reset
/config/duration <float seconds>
/config/streaming <int 0|1>
/segment <int segment_id> <string mood> <string full_text> <float start_s> <float end_s>
/keywords <int segment_id> <string...>
/image <int segment_id> <int layer_index> <string role> <string local_path>
/start
/finish
```

Allowed moods:

```text
DARK, CALM, ANXIOUS, DENSE, RISING TENSION, RELEASE, BRIGHT, SPARSE
```

The same list must appear in `src/bard_core/contracts.py::MOOD_LABELS` and Processing
`MoodManager.pde` with no aliases.

See [pipeline_data.md](pipeline_data.md) for concrete JSON examples and field ownership.

Image generation is an optional provider stage:

```text
StoryFragment.image_assets
-> imagen | openverse
-> Python subject cutout to transparent PNG when generated
-> runs/<run_id>/images/
-> /image OSC paths
-> Processing live composition
```

Current image roles are only `background` and `subject`; symbol images are intentionally disabled.
The Processing visual layout, timing, and stale-image persistence are intentionally unchanged.
For the final performance, keep a procedural fallback live locally while generated assets arrive with a deliberate delay.

Normal story runs keep `image_provider=none`. Pass `--generate-images --image-provider openverse|imagen`
to create image assets. Normal runs write compact `story.json` plus `run_manifest.json`; add
`--debug-artifacts` for verbose `debug/scene_cards.json`.
