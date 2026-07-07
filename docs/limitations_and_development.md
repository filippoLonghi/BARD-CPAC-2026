# Limitations And Development Notes

This document collects the practical limits we saw while running BARD and the most useful directions
for continuing the work.

## Current Runtime Limits

The main limitation is startup latency. In both file-based sequential runs and microphone live runs,
there can be roughly 80-110 seconds between the first audio input and the first complete Processing
scene. The exact delay changes from run to run.

The delay comes from several steps that happen before Processing can safely start:

- preparing the first audio chunk;
- sending audio to Gemini/Vertex and waiting for the response;
- generating the first story fragment;
- planning image prompts and retrieving or generating the first `background` and `subject` assets;
- cutting out generated subject images when background removal is enabled;
- sending the first complete scene to Processing and waiting for the `/prime -> /primed` handshake.

This depends on API response time, internet connection, local machine speed, the selected image
provider, the number of image assets per fragment, and whether the run uses Docker playback or local
Python playback. The current design avoids starting Processing with an incomplete scene, so it accepts
this delay in exchange for a more stable first visual moment.

Later fragments are prepared while playback is already running. If a fragment is late, Python logs
the delay and Processing keeps the current scene rather than showing an empty placeholder.

## GCP, Docker, And Vertex AI

BARD currently leans on GCP because Vertex AI gives one managed place for Gemini audio/story calls and
Imagen image generation. That is useful for a group project because nobody has to host large models
locally, install GPU-heavy inference stacks, or keep different laptops in exactly the same AI setup.

Docker helps with reproducibility. It packages the Python dependencies, background-removal stack, OSC
sender, and GCP client libraries in one environment. It is especially useful for file-based
`run-fragments --audio` tests. Microphone live mode is different: on Windows laptops, Docker Desktop
often does not expose the built-in microphone to Linux containers, so `run-live` should be run from
the local `.venv`.

These choices also make a production direction more realistic. The code already has:

- a Docker image;
- GCP authentication and project configuration;
- Vertex AI providers;
- optional Cloud Storage upload of completed run folders;
- compact replay artifacts in `story.json` and metadata in `run_manifest.json`;
- a small FastAPI app that can become a deployed API surface.

The missing production pieces are not model access but orchestration and user experience.

## Cost And Quotas

Openverse retrieval has no image API cost. It can still fail or throttle because it is a public API,
and downloaded images carry their own attribution/licensing metadata.

Imagen and Gemini/Vertex calls do cost money. In our test scale the cost is small, especially when
using Openverse for rehearsals and Imagen only for selected runs. The main predictable cost is Imagen:

```text
image cost ~= fragments * images_per_fragment * price_per_image
```

Gemini cost depends on audio length, prompt size, output length, and the number of model calls. BARD
reduces this by grouping fine musical observations inside larger story/image fragments and doing the
music-to-story mapping locally.

GCP projects also have quotas and rate limits. In practice this means a run can fail or slow down if
too many requests are made, if the selected model is not available in the configured region, if billing
is not active, or if the project has not been granted enough quota for the chosen model. The exact
limits are project-, region-, and model-dependent, so they should be checked in the GCP console before
a public demo.

## Artistic And Technical Limits

The audio analysis is still partly interpretive. Gemini can return useful musical observations, but
it can also be uncertain about instruments, genre, or performance details. The story layer avoids
putting raw instrument guesses directly into audience-facing text, but the quality of the narrative
still depends on the quality of the analysis.

Image coherence is another limitation. The story bible and deterministic world profile help keep a
consistent setting, but generated or retrieved images can still vary in style. Openverse is useful for
free testing, but it retrieves existing images rather than creating exactly the intended visual world.
Imagen gives more control but adds cost and latency.

The Processing layer is intentionally procedural and resilient, but it still depends on receiving
scene data through OSC. If OSC ports are blocked, Processing is not running, or paths are not visible
from the host machine, the visual side can fail even when the Python run succeeds.

## Development Directions

The most useful next step is a small user interface. Right now the project is powerful but command
driven. A simple UI could let a user:

- choose an audio file or microphone device;
- select language, story level, image provider, and output folder;
- see estimated cost before starting;
- see pipeline progress and current stage;
- replay a saved `story.json`;
- open the output folder after a run.

Another important direction is a proper deployed orchestrator. The existing FastAPI file can become a
Cloud Run service later, but it needs a run model: upload audio, create a run id, process work in the
background, save artifacts to Cloud Storage, and expose status/results. For live performance, a local
bridge would still be needed because Processing runs on the performance machine.

Latency can also be improved:

- prepare a procedural Processing intro while the first AI scene is generated;
- start with text-only or Openverse-only previews, then replace assets when generated images arrive;
- lower the startup buffer for faster first display;
- reduce image count per scene;
- cache generated assets for repeated rehearsals;
- parallelize story/image work where the contracts allow it.

Audio analysis can become more controllable by combining Gemini with local features such as loudness,
onset density, spectral brightness, silence, and dynamic range. CLAP or another embedding model could
be used as a secondary signal, but it should remain optional because it adds local model dependencies.

Finally, the documentation and public repo should keep separating source code from run artifacts,
private audio, credentials, and generated outputs. That makes the project easier to share and safer to
extend.
