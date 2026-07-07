# Project Structure

```text
apps/
  processing/
    bard_story_visuals/      Processing sketch for live story display.

configs/
  local.example.env          Template for local environment variables.

data/
  audio/                     Single active location for input recordings and sample audio.

docs/
  docker.md                  Docker Desktop workflow and networking.
  running_the_pipeline.md    Canonical commands and parameter effects.
  timing_and_sync.md         Audio, text, sentence, and image timing model.
  architecture.md            System shape and future async design.
  future_development.md      Roadmap, live-video direction, model options, team roles.
  gcp_setup.md               Exact GCP setup commands.
  project_structure.md       This file.

legacy/
  labelbanks/                CLAP labelbank files used by optional local analysis.
  hackathon_2025/            Reference prototype and demo scripts.

src/
  bard_core/                 Active Python package.
    legacy/                  Previous package-level CLAP/Mistral batch code, kept for reference.
```

The active pipeline is `src/bard_core` without the package `legacy/` subfolder. Code under
`legacy/hackathon_2025/` is the original prototype material. Code under `src/bard_core/legacy/`
belongs to previous package-level experiments and compatibility wrappers, and is not used by
`run-fragments` or `run-live`.
