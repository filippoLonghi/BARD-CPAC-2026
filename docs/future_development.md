# Future Development

This document tracks possible next steps for BARD.

This is a roadmap, not the current run guide. Use
[running_the_pipeline.md](running_the_pipeline.md) for executable commands and current parameters.
For practical limits and production notes, see
[limitations_and_development.md](limitations_and_development.md).

BARD is not meant to generate a finished video after the performance. The goal is a live or near-live system: the music starts, the system listens, a story begins to appear after a delay, images arrive after another delay, and text, colors, effects, and generated images are composed in real time into an abstract visual narration.

## Core Idea

BARD is an after-score: a visible narrative trace of a unique human performance.

The system should highlight what makes each performance specific:

- musician interpretation
- interaction between performer and audience
- execution choices
- small mistakes
- dynamics, tension, silence, density, and energy

The output should not be a literal music description. It should feel like a story that the performance is secretly telling.

## Target Live Pipeline

The target pipeline is:

```text
live or recorded audio
-> audio segmentation
-> mood / energy / tension extraction
-> story fragment generation
-> visual prompt generation
-> image generation with delay
-> Processing receives text, moods, colors, effects, images
-> abstract real-time story-video
```

The important point is that the system can work with delay, but it should still feel alive.

Example timing:

```text
00s   Music starts.
10s   First audio segment is analyzed.
20s   First story fragment arrives.
30s   First abstract image/keyframe arrives.
30s+  Processing combines text, mood colors, particles/effects, and images.
```

The final output should be more like a live visual organism than a pre-rendered movie.

## Processing Role

Processing is the live visual layer.

The active OSC contract already sends timing, story text, keywords, image paths, and start/finish
signals:

```text
/reset
/prepare -> /ready
/config/duration <float seconds>
/config/streaming <int 0|1>
/segment <int segment_id> <string mood> <string full_text> <float start_s> <float end_s>
/keywords <int segment_id> <string...>
/image <int segment_id> <int layer_index> <string role> <string local_path>
/prime -> /primed
/start
/finish
```

The next useful contract extension is richer visual control: palette, motion quality, density,
transition style, and effect intensity.

Processing should not wait passively for images. It should always have procedural visuals available:

- text animation
- color transitions
- particles
- noise / fog / abstract fields
- mood-based motion

Generated images should enter the scene when ready, while procedural visuals keep the performance
alive.

## Video Strategy

For now, we should not generate one complete video file.

Instead, the video-story should be composed live from:

- story text
- mood labels
- color palettes
- procedural Processing effects
- generated images/keyframes
- transitions and motion

This is better for a live performance because:

- it tolerates model latency
- it can react while generation is still happening
- it avoids waiting for a full video render
- it keeps the performance feeling alive

Later, we can record the Processing output and export the final performance as a video artifact.

## Model Freedom

The current code uses providers. That means the architecture is not locked to one model or one cloud platform.

Possible provider types:

```text
audio_provider = gemini | clap | custom_features | essentia | librosa
story_provider = vertex | openai | anthropic | mistral | local
image_provider = imagen | openai | stable_diffusion | fal | comfyui
video_provider = processing | touchdesigner | ffmpeg | veo | runway
```

Vertex AI is useful because it is already connected to GCP, but it does not need to do everything.

## Hybrid Direction

Gemini is convenient for audio, but it may not understand musical performance deeply enough by itself.

A better direction is hybrid analysis:

```text
technical audio features
+
audio/music embeddings
+
LLM interpretation
```

Technical audio features can include:

- RMS / loudness
- spectral centroid / brightness
- onset density
- tempo or pulse
- silence
- dynamic range
- spectral roughness
- density
- sudden changes

CLAP or another audio embedding model can add semantic labels:

- calm
- anxious
- dense
- sparse
- bright
- dark
- rising tension
- release

Then an LLM can convert these into a narrative timeline:

```json
{
  "segment": 3,
  "energy": "high",
  "brightness": "low",
  "tension": "rising",
  "texture": "dense",
  "change": "sudden attack after quiet section",
  "mood": "ANXIOUS",
  "story_role": "the hidden force becomes visible"
}
```

This should be more controllable than asking one multimodal model to understand the audio directly.

## Near-Term Technical Objectives

1. Tighten the live pipeline:

```text
audio or microphone input
-> Gemini / Vertex audio interpretation
-> story fragments
-> image assets
-> Processing via OSC
```

2. Keep the structured intermediate format useful:

```text
story.json
run_manifest.json
debug/scene_cards.json
```

Scene data should stay easy to inspect:

- segment id
- start/end time
- mood
- story text
- visual motif
- palette
- motion
- image prompt
- image status
- generated image path/url

3. Improve audio analysis:

Start with simple local features using `librosa`, then combine with CLAP or another audio embedding model.

4. Improve image generation:

- keep backgrounds and subjects visually coherent across fragments
- reduce literal story illustration
- improve cutout quality for subject assets
- keep Openverse useful for free rehearsal runs

5. Improve image delivery:

Processing currently receives local file paths. For remote or multi-machine runs, decide between:

- local file paths
- URLs from Cloud Storage
- pre-downloaded image assets from a local bridge script

6. Build delay-aware live behavior:

Processing should show procedural visuals immediately and blend in story/images when they arrive.

## Image Direction

Images should be abstract, not literal illustrations of the story.

Good image prompts should describe:

- texture
- atmosphere
- color palette
- symbolic motif
- motion feeling
- composition
- continuity with previous images

Bad prompts:

- literal scene illustration
- too many characters
- cinematic realism by default
- direct description of instruments

Example visual prompt:

```text
Abstract luminous fragments drifting through a dark suspended space, cold blue and pale silver palette, dense mist, soft granular texture, a fragile vertical shape almost forming and dissolving, no text, no instruments.
```

## Team Roles

The team has four people. A good division is not just "two story, two image"; the project also needs integration.

### 1. Pipeline / Cloud Lead

Owns the technical backbone.

Tasks:

- maintain project structure
- maintain Docker and GCP setup
- manage GCP project configuration
- manage environment variables and secrets
- define JSON schemas between stages
- implement job orchestration
- keep local and remote-model runs reproducible
- monitor cost and latency

Deliverables:

- working local pipeline
- reproducible local and Docker runs
- clear setup documentation
- stable `runs/` outputs

### 2. Audio / Performance Analysis Lead

Owns the transformation from audio to emotional timeline.

Tasks:

- test Gemini audio interpretation
- test CLAP
- extract features with `librosa` or similar tools
- define mood mapping rules
- segment the audio in a musically meaningful way
- evaluate which features actually correspond to performance changes

Deliverables:

- `music_segments.json`
- feature extraction experiments
- mood/tension mapping
- comparison between Gemini-only, CLAP, and hybrid analysis

### 3. Story / Narrative Lead

Owns coherence and the narrative system.

Tasks:

- design prompts for story generation
- avoid literal music descriptions
- keep story fragments coherent
- define story arc rules
- create story bible / continuity memory
- convert audio timeline into abstract narrative progression

Deliverables:

- prompt templates
- story schema
- `story.json`
- examples of good and bad outputs
- evaluation notes on coherence and style

### 4. Visual / Live Composition Lead

Owns Processing and the visual language.

Tasks:

- improve Processing sketch
- define mood-to-color/effect mappings
- design how text appears live
- design how images enter the composition
- define OSC contract for images and visual parameters
- test generated images as live assets
- keep procedural fallback visuals always active

Deliverables:

- Processing live sketch
- OSC image integration prototype
- visual style guide
- live demo with text, mood, and generated image assets

## Shared Tasks

Some tasks should involve the whole team:

- decide the artistic language
- choose the final performance scenario
- test the system with different audio recordings
- define acceptable latency
- rehearse the live demo
- document failures and surprising outputs

## Immediate Next Milestones

### Milestone 1: Stable Cloud Story Prototype

Goal:

```text
audio -> story fragments -> image assets -> Processing
```

Success criteria:

- one command runs the pipeline
- story appears in Processing
- mood changes affect visual atmosphere
- `background` and `subject` images are available for each scene when image generation is enabled
- output files are saved in `runs/`

### Milestone 2: Hybrid Audio Analysis

Goal:

```text
audio -> technical features + CLAP/Gemini -> better scene cards
```

Success criteria:

- compare Gemini-only vs hybrid output
- define a stable mood mapping
- generate more convincing emotional arcs

### Milestone 3: Image Keyframes

Goal:

```text
scene cards -> abstract images -> Processing
```

Success criteria:

- image prompts are generated automatically
- images are generated with delay
- Processing can display image assets when ready
- procedural visuals continue while waiting

### Milestone 4: Live Abstract Video-Story

Goal:

```text
music + delayed story + delayed images + Processing effects
```

Success criteria:

- system feels live
- delay is artistically acceptable
- output is coherent but not literal
- performance can be recorded as final documentation

## Design Principle

The system should not hide latency completely. It can use delay as part of the aesthetic.

The performance starts as pure music. Then the story slowly appears, then images emerge, then everything becomes a visible after-score.
