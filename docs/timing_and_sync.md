# Timing And Synchronization

The source audio is the master clock. Python decides fragment boundaries, word budgets, fine music
analysis windows, and the absolute `start_s` / `end_s` timestamps sent over OSC. Processing receives
those timestamps, splits each fragment into sentences, and schedules word entrance, stable reading
time, and fade time inside the fragment. Processing does not move the global music clock.

Shared creative timing defaults live in `src/bard_core/config.py`. Secrets files are for
credentials, project IDs, bucket names, private paths, and API tokens. Use CLI flags for quick
one-run timing experiments.

## Timing Parameters

| Parameter | Layer | Where defined | How to override | Requires regeneration? | Effect |
|---|---|---|---|---|---|
| `BARD_STORY_WPM` | Python story budget | `src/bard_core/config.py` | env/config file or `--story-wpm` | Regenerate story text | Sets `target_words = fragment_seconds * WPM / 60`. |
| `--story-wpm` | Python story budget | `src/bard_core/cli.py` | CLI | Regenerate story text | One-run override for `BARD_STORY_WPM`. |
| `BARD_FRAGMENT_TARGET_S` | Python splitting | `src/bard_core/config.py` | env/config file or `--fragment-target-seconds` | Regenerate story, analysis, images | Target automatic fragment duration. |
| `BARD_FRAGMENT_MIN_S` | Python splitting | `src/bard_core/config.py` | env/config file or `--fragment-min-seconds` | Regenerate story, analysis, images | Preferred minimum for longer-audio automatic fragments. |
| `BARD_FRAGMENT_MAX_S` | Python splitting | `src/bard_core/config.py` | env/config file or `--fragment-max-seconds` | Regenerate story, analysis, images | Preferred maximum for longer-audio automatic fragments. |
| `BARD_SHORT_AUDIO_THRESHOLD_S` | Python splitting | `src/bard_core/config.py` | env/config file or `--short-audio-threshold-seconds` | Regenerate story, analysis, images | Below this duration, automatic splitting chooses only one or two balanced fragments. |
| `--fragments N` | Python splitting | `src/bard_core/cli.py` | CLI only | Regenerate story, analysis, images | Forces exactly `N` balanced fragments. |
| `--chunk-seconds S` | Python splitting | `src/bard_core/cli.py` | CLI only | Regenerate story, analysis, images | Preserves old fixed-size chunking, including any short final remainder. |
| `BARD_MUSIC_WINDOWS_PER_FRAGMENT` | Python audio analysis | `src/bard_core/config.py` | env/config file or `--music-windows-per-fragment` | Rerun audio analysis and story generation | Number of fine observations inside each story fragment when fixed windows are not used. |
| `BARD_LIVE_MUSIC_WINDOWS_PER_FRAGMENT` | Python live audio analysis | `src/bard_core/config.py` | env/config file or `--music-windows-per-fragment` | Rerun live command | Live-mode fine observations per story fragment. Default is `2`. |
| `BARD_MUSIC_WINDOW_S` / `--music-window-seconds` | Python audio analysis | Optional env in `src/bard_core/config.py`; CLI in `src/bard_core/cli.py` | env/config file or CLI | Rerun audio analysis and story generation | Fixed observation length. If set, it overrides derived windows-per-fragment timing. |
| `BARD_STARTUP_BUFFER_FRAGMENTS` / `--startup-buffer-fragments` | Python OSC start | `src/bard_core/config.py`; CLI in `src/bard_core/cli.py` | env/config file or CLI | Rerun OSC-producing command | Complete story/image fragments to prepare before Processing starts. Default is `2`. |
| `BARD_LIVE_STORY_SCENE_S` / `--chunk-seconds` | Python live splitting | `src/bard_core/config.py`; CLI in `src/bard_core/cli.py` | env/config file or CLI | Rerun live command | Live microphone story-scene chunk length. Default is `30`; use `--chunk-seconds 15` for the current short test run. |
| `BARD_LIVE_STARTUP_BUFFER_FRAGMENTS` / `--startup-buffer-fragments` | Python live OSC start | `src/bard_core/config.py`; CLI in `src/bard_core/cli.py` | env/config file or CLI | Rerun live command | Complete live fragments to prepare before Processing starts. Default is `2`. |
| `SENTENCE_STABLE_FRACTION` | Processing text timing | `apps/processing/bard_story_visuals/WordsSystem.pde` | Edit Processing source | Replay existing `story.json` | Maximum fraction of a sentence slot reserved for stable reading before fade. |
| `SENTENCE_MIN_STABLE_MS` | Processing text timing | `WordsSystem.pde` | Edit Processing source | Replay existing `story.json` | Minimum stable reading time for a sentence. |
| `SENTENCE_MAX_STABLE_MS` | Processing text timing | `WordsSystem.pde` | Edit Processing source | Replay existing `story.json` | Maximum stable reading time for a sentence. |
| `SENTENCE_FLIGHT_BUFFER_MS` | Processing word entrance | `WordsSystem.pde` used by `SentenceDisplay.pde` | Edit Processing source | Replay existing `story.json` | Maximum word flight duration for the time-based entrance schedule. |
| `WORD_MIN_FLIGHT_MS` | Processing word entrance | `WordsSystem.pde` used by `SentenceDisplay.pde` | Edit Processing source | Replay existing `story.json` | Minimum word flight duration unless the sentence assembly window is shorter. |
| `WORD_FLIGHT_PX_PER_SECOND` | Processing word entrance | `WordsSystem.pde` used by `SentenceDisplay.pde` | Edit Processing source | Replay existing `story.json` | Converts spawn-to-target distance into a natural linear flight duration. |
| `MIN_LATE_SCENE_DURATION_S` | Processing sync fallback | `StoryDirector.pde` | Edit Processing source | Replay existing `story.json` | Minimum display time when a scene arrives after its scheduled audio end. |

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

The exact count follows the committed defaults in `src/bard_core/config.py`. Explicit
`--fragments N` still forces exactly `N` balanced fragments. Explicit `--chunk-seconds S` keeps the
old fixed-size behavior and can intentionally produce a short final chunk.

## Music Windows

If `BARD_MUSIC_WINDOW_S` or `--music-window-seconds` is set, Python uses that fixed observation
duration. Otherwise it derives each fragment's fine-analysis window:

```text
music_window_seconds = fragment_duration / BARD_MUSIC_WINDOWS_PER_FRAGMENT
```

Those observations inform one story fragment and one set of image prompts; they are not separate
Processing scenes. With `BARD_MUSIC_WINDOWS_PER_FRAGMENT=N`, each story fragment is divided into `N`
fine music observations.

## Processing Sentence Timing

Processing keeps the current text layout and scene timing model:

1. `WordsSystem.pde` splits the fragment text into sentences.
2. Each sentence receives a slot proportional to its word count.
3. Stable time is `slot * SENTENCE_STABLE_FRACTION`, constrained between
   `SENTENCE_MIN_STABLE_MS` and `SENTENCE_MAX_STABLE_MS`.
4. The remaining slot is assembly time. `SentenceDisplay.pde` assigns every word a
   `flightStartMs` and `flightEndMs` derived from the actual scene duration.
5. `FlyingWord.pde` linearly interpolates from its random edge spawn to the final text position.
   It does not use steering acceleration for normal entrances and does not snap words at the scene
   deadline.
6. The final sentence still ends at the fragment's scheduled audio timestamp. If a scene arrives
   late, Processing uses the remaining audio time, with `MIN_LATE_SCENE_DURATION_S` as the fallback
   minimum instead of silently extending the scene by its original full duration.

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

## Shared Default Snapshot

`configs/timing.default.env` mirrors the committed defaults in `src/bard_core/config.py`. When you
change the committed defaults for an experiment, update that file too so teammates can see the active
timing profile.

For quick tests, prefer CLI flags:

```powershell
python -m bard_core run-fragments --audio data\audio\demo.wav --story-wpm 55
```

## Worked Example

For any generated run:

1. Automatic splitting chooses a balanced fragment count from the current config.
2. Processing receives each fragment with absolute `start_s` and `end_s`.
3. Processing splits the fragment text into sentences. A sentence with twice as many words as
   another sentence receives roughly twice the display slot.
4. Each word gets a deterministic flight window inside its sentence assembly interval.
5. The whole fragment still ends at its scheduled audio time, except for the explicit late-scene
   minimum fallback.

## Replay Without Cloud Calls

Open the Processing sketch and press Run, then execute:

```powershell
python -m bard_core --env-file "$ENV_FILE" send-osc `
  --story-json runs\cpac-mixedgenres-docker\story.json `
  --delay 0
```

This sends existing text and image paths by default, and it auto-loads `processing_audio.wav` if that
file is next to `story.json`. It does not call Gemini, Imagen, Openverse, or Replicate.
