# Pipeline Data Contracts

BARD keeps the raw musical evidence separate from the symbolic adventure prose. This makes each boundary
inspectable and prevents uncertain instrument or genre guesses from appearing in the story.

## 1. Audio File To Saved Chunks

`run-fragments` writes independently analyzable PCM WAV files:

```text
runs/<run>/audio_chunks/segment_001.wav
runs/<run>/audio_chunks/segment_002.wav
...
```

Each chunk has an `id`, local path, `start_s`, and `end_s`. With `--fragments 3`, the uploaded file is
divided into three equal windows. With `--chunk-seconds 20`, the final window may be shorter.

## 2. Chunk To Musical Observations

Gemini analyzes one chunk per request. `music_segments.json` is the debugging file to keep open while
listening to the files in `audio_chunks/`.

```json
{
  "id": 1,
  "start_s": 0.0,
  "end_s": 20.0,
  "mood_hint": "ANXIOUS",
  "music_prompt": "A restrained opening grows more urgent.",
  "valence": -0.45,
  "arousal": 0.68,
  "tension": 0.74,
  "tempo_bpm": 112,
  "tempo_description": "moderately fast and accelerating",
  "meter": "4/4",
  "mode": "minor or modal",
  "harmony": "unstable with unresolved movement",
  "dynamics": "soft to strong crescendo",
  "texture": "sparse becoming layered",
  "rhythmic_character": "steady with sharper attacks",
  "instruments": ["strings", "uncertain low percussion"],
  "genre_candidates": ["cinematic", "classical"],
  "notable_events": ["density increases near the end"],
  "source": "gemini-audio-chunk"
}
```

Instrument and genre values are hypotheses, not ground truth. The prompt tells Gemini to return
`uncertain` or an empty list rather than inventing details.

Google documents that Gemini can detect emotion in music and analyze timestamped audio segments:
[Gemini audio understanding](https://ai.google.dev/gemini-api/docs/audio).

## 3. Musical Observations To Dramatic Canvas

Python locally translates measured valence, arousal, and tension into story-safe directions. This
stage does not make another LLM call:

```json
{
  "story_energy": "cautious movement becoming urgent",
  "story_tension": "danger is approaching",
  "story_direction": "the safe path closes and the hero must choose",
  "suggested_event": "a shadow blocks the bridge",
  "visual_motion": "slow drift becoming sharp diagonal motion",
  "color_direction": "cool blue darkening toward violet"
}
```

The story-generation prompt receives only these dramatic directions. Instrument, genre, tempo,
rhythm, harmony, and recording vocabulary do not enter the audience-facing story.

## 4. Story Bible And Continuity State

Before the first fragment, Gemini creates `story_bible` in `story.json`:

```text
title
protagonist + trait + flaw + goal
antagonist + motive
helper
setting
magical rule
central problem + stakes
moral
ending target
one planned beat per expected fragment
```

The design follows a child-friendly story map: characters, setting, plot, problem, and solution, with
a beginning, middle, and end. A deterministic audio-driven world profile is attached to the bible so
the story setting and cast can change with the music instead of defaulting to woodland imagery.

Sources:

- [Reading Rockets story maps](https://www.readingrockets.org/classroom/classroom-strategies/story-maps)
- [University of Michigan summary of Propp's functions](https://websites.umich.edu/~esrabkin/Propp.htm)

After each fragment, `story_state` records location, character status, magical-object status, the last
event, unresolved threads, and facts that must remain true. The next call receives the immutable bible
and this compact state, rather than relying only on a growing prose transcript.

## 5. Story Fragment To Three Visual Assets

Each fragment contains full prose for narration plus shorter material for projection:

```json
{
  "id": 1,
  "narrative_phase": "opening and problem",
  "story_event": "Nilo discovers the stolen dawn key.",
  "text": "Full child-friendly story paragraph...",
  "display_text": "The dawn key had vanished.",
  "keywords": ["dawn", "key", "forest", "shadow"],
  "image_assets": [
    {"role": "background", "label": "moonlit forest", "prompt": "..."},
    {"role": "subject", "label": "Nilo the fox", "prompt": "..."},
    {"role": "symbol", "label": "dawn key", "prompt": "..."}
  ]
}
```

The three assets are generated or retrieved independently. `scene_cards.json` is the best visual
debugging view; it includes prompts, provider, model, local path, source/license, status, and errors.

## 6. Python To Processing

For uploaded-audio demonstrations, BARD first verifies Processing with `/prepare` and `/ready`.
After scene 1 text and images are ready, Processing preloads them through `/prime` and `/primed`.
Only then do the Processing clock and source audio start. Later scenes generate during playback:

```text
/reset
/prepare -> /ready
/config/duration <float seconds>
/config/streaming <0 batch | 1 sequential>
/segment <id> <mood> <full_story_text> <start_s> <end_s>
/keywords <id> <keyword...>
/image <id> <layer_index> <role> <local_path>
/prime -> /primed
/start
/finish
```

Processing uses `start_s/end_s` as the internal music clock. Each sentence receives a deadline
proportional to its word count. Words assemble progressively, then snap into place if necessary so
the complete sentence remains readable before the next sentence slot. Every saved sentence is shown
before its scene boundary.

Python sends `/start` and starts local playback with `pygame` immediately afterward. Processing
follows the audio clock, not accumulated slide delays. If a cloud scene arrives late, Processing shows it at the
correct current time instead of shifting every later fragment; until it arrives, the previous visual
state remains visible. True microphone mode will replace the local player with the live input stream.

## Timing And Story Length

Unless `--words-per-fragment` is supplied:

```text
target words = segment seconds * reading WPM / 60 * text coverage
```

Defaults are `120 WPM` and `0.72` coverage. This is deliberately slower than fluent adult fiction
reading because viewers also follow moving words, images, and music.

When neither `--chunk-seconds` nor `--fragments` is provided, BARD uses longer
`BARD_STORY_SCENE_S` windows, normally 60 seconds. Inside each scene, one Gemini audio request
returns several timestamped observations using `BARD_MUSIC_WINDOW_S`, normally 15 seconds.
One story request receives that complete ordered list, so the prose follows small musical changes
while the scene shares one coherent passage and one set of images.

Text length is calculated from the exact scene duration, audience reading speed, and coverage. The
final short scene therefore receives fewer words and finishes with the music. `--chunk-seconds` and
`--fragments` remain debugging overrides for story-scene boundaries.

These controls are configurable:

```text
--music-window-seconds 15
--chunk-seconds 60
--reading-wpm 105
--text-coverage 0.70
--story-language Italian
--story-level early-reader|children|general|literary
```

Only audience-facing story prose changes language. Music analysis and image prompts remain English.
Narrative tone is not a user parameter: it comes from each fragment's music-derived energy, tension,
direction, and event cues.

## Run Artifacts

```text
result.json          everything together
music_segments.json raw music facts + dramatic canvas
story.json           story bible, state, fragments, image records
scene_cards.json     visual integration view
full_story.txt       prose only
audio_chunks/        exact WAV chunks used for analysis
images/              generated or retrieved assets
```
