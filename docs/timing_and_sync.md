# Timing And Synchronization

The source audio is the master clock. Python decides fragment boundaries, word budgets, fine music
analysis windows, and the absolute `start_s` / `end_s` timestamps sent over OSC. Processing receives
those timestamps, splits each fragment into sentences, and schedules word entrance, stable reading
time, and fade time inside the fragment. Processing does not move the global music clock.

Creative timing defaults should not live in `Project/secrets/bard-local.env`. Secrets files are for
credentials, project IDs, model names, and private paths. Use code defaults, `configs/timing.*.env`,
or CLI flags for timing experiments.

## Timing Parameters

| Parameter | Layer | Where defined | How to override | Requires regeneration? | Effect |
|---|---|---|---|---|---|
| `BARD_STORY_WPM` | Python story budget | `src/bard_core/config.py` default `70` | env/config file or `--story-wpm` | Regenerate story text | Sets `target_words = fragment_seconds * WPM / 60`. |
| `--story-wpm` | Python story budget | `src/bard_core/cli.py` | CLI | Regenerate story text | One-run override for `BARD_STORY_WPM`. |
| `BARD_FRAGMENT_TARGET_S` | Python splitting | `src/bard_core/config.py` default `60` | env/config file or `--fragment-target-seconds` | Regenerate story, analysis, images | Target automatic fragment duration. |
| `BARD_FRAGMENT_MIN_S` | Python splitting | `src/bard_core/config.py` default `50` | env/config file or `--fragment-min-seconds` | Regenerate story, analysis, images | Preferred minimum for longer-audio automatic fragments. |
| `BARD_FRAGMENT_MAX_S` | Python splitting | `src/bard_core/config.py` default `70` | env/config file or `--fragment-max-seconds` | Regenerate story, analysis, images | Preferred maximum for longer-audio automatic fragments. |
| `BARD_SHORT_AUDIO_THRESHOLD_S` | Python splitting | `src/bard_core/config.py` default `120` | env/config file or `--short-audio-threshold-seconds` | Regenerate story, analysis, images | Below this duration, automatic splitting chooses only one or two balanced fragments. |
| `--fragments N` | Python splitting | `src/bard_core/cli.py` | CLI only | Regenerate story, analysis, images | Forces exactly `N` balanced fragments. |
| `--chunk-seconds S` | Python splitting | `src/bard_core/cli.py` | CLI only | Regenerate story, analysis, images | Preserves old fixed-size chunking, including any short final remainder. |
| `BARD_MUSIC_WINDOWS_PER_FRAGMENT` | Python audio analysis | `src/bard_core/config.py` default `4` | env/config file or `--music-windows-per-fragment` | Rerun audio analysis and story generation | Number of fine observations inside each story fragment when fixed windows are not used. |
| `BARD_MUSIC_WINDOW_S` / `--music-window-seconds` | Python audio analysis | Optional env in `src/bard_core/config.py`; CLI in `src/bard_core/cli.py` | env/config file or CLI | Rerun audio analysis and story generation | Fixed observation length. If set, it overrides derived windows-per-fragment timing. |
| `SENTENCE_STABLE_FRACTION` | Processing text timing | `apps/processing/bard_story_visuals/WordsSystem.pde`, `0.22f` | Edit Processing source | Replay existing `story.json` | Maximum fraction of a sentence slot reserved for stable reading before fade. |
| `SENTENCE_MIN_STABLE_MS` | Processing text timing | `WordsSystem.pde`, `1200` | Edit Processing source | Replay existing `story.json` | Minimum stable reading time for a sentence. |
| `SENTENCE_MAX_STABLE_MS` | Processing text timing | `WordsSystem.pde`, `2400` | Edit Processing source | Replay existing `story.json` | Maximum stable reading time for a sentence. |
| `SENTENCE_FLIGHT_BUFFER_MS` | Processing word entrance | `WordsSystem.pde`, `2000` used by `SentenceDisplay.pde` | Edit Processing source | Replay existing `story.json` | Reserve before the assembly deadline so the last word has time to fly toward its target. |

`BARD_READING_WPM` is accepted as a legacy env/CLI compatibility input and maps to the story WPM
when no explicit `BARD_STORY_WPM` / `--story-wpm` is provided. `BARD_TEXT_COVERAGE` is deprecated
for the main `run-fragments` path.

## Automatic Fragment Splitting

When neither `--fragments` nor `--chunk-seconds` is provided, Python measures total audio duration
and chooses a balanced fragment count:

- short audio at or below `BARD_SHORT_AUDIO_THRESHOLD_S` uses one or two balanced fragments;
- longer audio chooses a count near `BARD_FRAGMENT_TARGET_S`, preferring the
  `BARD_FRAGMENT_MIN_S` to `BARD_FRAGMENT_MAX_S` range;
- final fragment end time is exactly the audio end time;
- tiny final remainders are avoided because splitting is by balanced fragment count, not fixed step.

Examples with defaults: 90s becomes two roughly 45s fragments, 115s becomes two roughly 57.5s
fragments, and 183.9s becomes three roughly 61.3s fragments. Explicit `--fragments N` still forces
exactly `N` balanced fragments. Explicit `--chunk-seconds S` keeps the old fixed-size behavior and
can intentionally produce a short final chunk.

## Music Windows

If `BARD_MUSIC_WINDOW_S` or `--music-window-seconds` is set, Python uses that fixed observation
duration. Otherwise it derives each fragment's fine-analysis window:

```text
music_window_seconds = fragment_duration / BARD_MUSIC_WINDOWS_PER_FRAGMENT
```

With `BARD_MUSIC_WINDOWS_PER_FRAGMENT=4`, a 45s fragment gets four 11.25s music observations.
Those observations inform one story fragment and one set of image prompts; they are not separate
Processing scenes.

## Processing Sentence Timing

Processing keeps the current visual animation model:

1. `WordsSystem.pde` splits the fragment text into sentences.
2. Each sentence receives a slot proportional to its word count.
3. Stable time is `slot * SENTENCE_STABLE_FRACTION`, constrained between
   `SENTENCE_MIN_STABLE_MS` and `SENTENCE_MAX_STABLE_MS`.
4. The remaining slot is assembly time. `SentenceDisplay.pde` uses
   `SENTENCE_FLIGHT_BUFFER_MS` so words start early enough to become readable.
5. The final sentence still ends at the fragment's scheduled audio timestamp.

Changing only Processing constants does not require Gemini, Imagen, audio analysis, or image
generation. Open Processing and replay an existing `story.json`.

## Regeneration Rules

- Changing `BARD_STORY_WPM` or `--story-wpm` changes the word budget sent to Gemini, so regenerate
  the story.
- Changing automatic fragment parameters changes fragment `start_s` / `end_s`, so regenerate audio
  analysis, story, and images.
- Changing `BARD_MUSIC_WINDOWS_PER_FRAGMENT` changes the audio observations, so rerun audio
  analysis and story generation.
- Changing `BARD_MUSIC_WINDOW_S` / `--music-window-seconds` also reruns audio analysis and story.
- Changing Processing-only constants can be tested by replaying an existing `story.json`.

## Starting Profiles

- Normal: `configs/timing.default.env`, `BARD_STORY_WPM=70`, 60s target fragments, 4 music windows.
- Readable: `configs/timing.readable.env`, `BARD_STORY_WPM=55`, slightly longer target fragments.
- Fast: `configs/timing.fast.env`, `BARD_STORY_WPM=85`, shorter target fragments.

For quick tests, prefer CLI flags:

```powershell
python -m bard_core run-fragments --audio data\test_audio\demo.wav --story-wpm 55
```

## Worked Example

For a 183.9s audio file with default timing:

1. Automatic splitting chooses three story fragments.
2. Fragment windows are approximately `0.0-61.3`, `61.3-122.6`, and `122.6-183.9`.
3. With `BARD_STORY_WPM=70`, each fragment targets about `61.3 * 70 / 60 = 71.5`, rounded to
   about 72 words.
4. With `BARD_MUSIC_WINDOWS_PER_FRAGMENT=4`, each fragment gets four music-analysis windows of
   about `61.3 / 4 = 15.3s`.
5. Processing receives each fragment with absolute `start_s` and `end_s`.
6. Processing splits the fragment text into sentences. A sentence with twice as many words as
   another sentence receives roughly twice the display slot.
7. The whole fragment still ends at its scheduled audio time.

## Replay Without Cloud Calls

Open the Processing sketch and press Run, then execute:

```powershell
python -m bard_core --env-file "$ENV_FILE" send-osc `
  --story-json runs\cpac-mixedgenres-docker\story.json `
  --include-images `
  --delay 0
```

This sends existing text and image paths. It does not call Gemini, Imagen, Openverse, or Replicate.
