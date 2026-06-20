# Project Structure

```text
apps/
  processing/
    bard_story_visuals/      Processing sketch for live story display.

configs/
  local.example.env          Template for local environment variables.

data/
  audio/                     Input recordings and performance audio.
  labelbanks/                CLAP labelbank files used by local analysis.

deploy/
  cloud-run.env.example      Cloud Run environment template.

docs/
  docker.md                  Docker Desktop workflow and networking.
  running_the_pipeline.md    Canonical commands and parameter effects.
  timing_and_sync.md         Audio, text, sentence, and image timing model.
  architecture.md            System shape and future async design.
  future_development.md      Roadmap, live-video direction, model options, team roles.
  gcp_setup.md               Exact GCP setup commands.
  project_structure.md       This file.

examples/
  prototype_outputs/         Saved hackathon JSON/audio outputs.
  story_inputs/              Small sample segment inputs.

legacy/
  prototype_scripts/         Historical one-file prototype scripts.

scripts/
  send_demo_story.py         Sends a tiny hardcoded story to Processing.
  voice_server_edge.py       Optional local narrator voice server.

src/
  bard_core/                 Active Python package.
```

The active pipeline is `src/bard_core`. The old hackathon code is only kept where it is still wrapped by the package or useful as historical reference.
