# Timing And Synchronization

## Master Clock

The original audio file is the master performance clock. Story scenes contain absolute `start_s`
and `end_s` timestamps measured from the beginning of that file. Processing records its own start
time when `/start` arrives and selects scenes using those timestamps, rather than adding a fixed
delay after each scene.

Before playback:

1. Python verifies that Processing answers `/prepare`.
2. Python sends every saved scene, sentence, keyword, and image path.
3. Processing preloads scene one's images and answers `/primed`.
4. Python sends `/start` and starts the source audio immediately afterward.

This keeps audio startup and Processing's visual clock close together without regenerating data.

## Story Length And Reading Speed

The backend calculates the requested word count for each story scene as:

```text
target words = scene seconds * reading words per minute / 60 * text coverage
```

The defaults are:

```text
reading speed = 120 words per minute
text coverage = 0.72
story scene = approximately 60 seconds
```

A complete 60-second scene therefore targets about 86 words. A shorter final scene receives fewer
words automatically. This is why the last sentence should end near the source audio's final time.

If Gemini exceeds the requested budget by more than roughly 12% (with a small eight-word tolerance),
BARD makes one low-temperature repair call. It compresses the same events into complete sentences
instead of truncating the final sentences. Runs that already respect the budget do not pay for this
extra call.

`text coverage` reserves time for words flying into place, sentence comprehension, and transitions.
It is not an extra audio delay.

## Processing Text Timing

When a scene begins, Processing knows:

- the exact remaining scene duration;
- the number of words;
- the number of sentences.

Each sentence receives a deadline-based slot proportional to its word count. Within that slot:

- words enter progressively during the assembly portion;
- any word still flying is snapped into its exact position at the assembly deadline;
- the complete sentence remains stable for approximately 1.2-2.4 seconds, using up to the final 22%
  of longer sentence slots.

The next sentence starts from its scheduled scene time. It never waits for the previous sentence's
particle physics to finish.

Text is paced against the scene's remaining time. If a cloud-generated scene arrives late during a
live run, Processing shortens its available display duration rather than moving the music clock.

This distinction fixes an important failure mode: previously, every sentence waited an extra 3-5
seconds for its last word to arrive. Across seven or more sentences, those unbudgeted delays could
consume 20-35 seconds and the final sentences were removed when the next scene began. The deadline
scheduler guarantees that every saved sentence is presented before its scene ends.

## Image Timing

All image files are loaded before a scene starts, avoiding disk stalls during playback. They are not
revealed together:

- first layer: randomly around 2-10% of the scene;
- second layer: randomly around 24-44%;
- third layer: randomly around 55-78%.

Subject and symbol positions are randomized for every scene. Background layers remain full-screen
because their role is environmental. These timings are visual only and do not expose the internal
15-second music-analysis windows.

## Small End Difference

The audio and visual clocks begin only milliseconds apart, but a small difference can remain because
audio playback, the Processing draw loop, particle movement, and font rendering use separate system
threads. The final words may also need a short settling or fade period after their scheduled entry.

At present, the audio clock remains authoritative: the story is not allowed to shift later scenes or
extend the source recording merely to finish an animation. The reading parameters remain available
through `BARD_READING_WPM`, `BARD_TEXT_COVERAGE`, `--reading-wpm`, and `--text-coverage`.

## Replay Without Cloud Calls

Open the Processing sketch and press Run, then execute:

```powershell
python -m bard_core --env-file "$ENV_FILE" send-osc `
  --story-json runs\arabesque-hybrid-test\story.json `
  --audio data\test_audio\arabesque.mp3 `
  --include-images `
  --delay 0
```

This reads the existing JSON and image files, sends OSC locally, and plays the existing audio. It
does not call Gemini, Imagen, Openverse, or any other cloud service.
