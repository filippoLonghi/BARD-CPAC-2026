# Project Structure

```text
apps/
  processing/
    bard_story_visuals/      Processing sketch for live story display.

configs/
  local.example.env          Template for local environment variables.

data/
  audio/                     Single active location for input recordings and sample audio.
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

legacy/
  hackathon_2025/            Historical standalone prototype and demo scripts.

src/
  bard_core/                 Active Python package.
```

The active pipeline is `src/bard_core`. Code under `legacy/hackathon_2025/` is historical reference
only and is not imported by the current package.
