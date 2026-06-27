from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json


MOOD_LABELS = ["ENERGETIC", "SOLO", "CALM", "DEEP", "DISSONANT", "ANXIOUS"]


@dataclass
class ImageAsset:
    role: str
    label: str
    prompt: str
    search_query: str | None = None
    negative_prompt: str | None = None
    provider: str | None = None
    model: str | None = None
    status: str = "planned"
    local_path: str | None = None
    remote_url: str | None = None
    source_url: str | None = None
    license: str | None = None
    creator: str | None = None
    error: str | None = None


@dataclass
class MusicSegment:
    id: int
    music_prompt: str
    start_s: float | None = None
    end_s: float | None = None
    mood_hint: str | None = None
    confidence: float | None = None
    source: str = "unknown"
    valence: float | None = None
    arousal: float | None = None
    tension: float | None = None
    tempo_bpm: float | None = None
    tempo_description: str | None = None
    meter: str | None = None
    mode: str | None = None
    harmony: str | None = None
    dynamics: str | None = None
    texture: str | None = None
    rhythmic_character: str | None = None
    instruments: list[str] = field(default_factory=list)
    genre_candidates: list[str] = field(default_factory=list)
    notable_events: list[str] = field(default_factory=list)
    story_energy: str | None = None
    story_tension: str | None = None
    story_direction: str | None = None
    suggested_event: str | None = None
    visual_motion: str | None = None
    color_direction: str | None = None


@dataclass
class StoryFragment:
    id: int
    mood: str
    text: str
    music_prompt: str | None = None
    start_s: float | None = None
    end_s: float | None = None
    image_prompt: str | None = None
    visual_motif: str | None = None
    palette: str | None = None
    motion: str | None = None
    narrative_phase: str | None = None
    story_event: str | None = None
    display_text: str | None = None
    keywords: list[str] = field(default_factory=list)
    image_assets: list[ImageAsset] = field(default_factory=list)
    mood_cues: list[dict[str, Any]] = field(default_factory=list)

    def normalized_mood(self) -> str:
        mood = (self.mood or "").upper().strip()
        return mood if mood in MOOD_LABELS else "CALM"


@dataclass
class PipelineResult:
    run_id: str
    audio_path: str
    music_segments: list[MusicSegment]
    fragments: list[StoryFragment]
    full_story: str
    story_bible: dict[str, Any] = field(default_factory=dict)
    story_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "audio_path": self.audio_path,
            "music_segments": [asdict(seg) for seg in self.music_segments],
            "fragments": [asdict(fragment) for fragment in self.fragments],
            "full_story": self.full_story,
            "story_bible": self.story_bible,
            "story_state": self.story_state,
            "metadata": self.metadata,
        }

    def scene_cards(self) -> list[dict[str, Any]]:
        return [
            {
                "segment_id": fragment.id,
                "start_s": fragment.start_s,
                "end_s": fragment.end_s,
                "mood": fragment.mood,
                "story_text": fragment.text,
                "music_prompt": fragment.music_prompt,
                "visual_motif": fragment.visual_motif,
                "palette": fragment.palette,
                "motion": fragment.motion,
                "narrative_phase": fragment.narrative_phase,
                "story_event": fragment.story_event,
                "display_text": fragment.display_text,
                "keywords": fragment.keywords,
                "image_prompt": fragment.image_prompt,
                "image_assets": [asdict(asset) for asset in fragment.image_assets],
            }
            for fragment in self.fragments
        ]

    def write(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_dir / "result.json", self.to_dict())
        write_json(output_dir / "music_segments.json", [asdict(seg) for seg in self.music_segments])
        write_json(
            output_dir / "story.json",
            {
                "fragments": [asdict(fragment) for fragment in self.fragments],
                "full_story": self.full_story,
                "story_bible": self.story_bible,
                "story_state": self.story_state,
            },
        )
        write_json(output_dir / "scene_cards.json", self.scene_cards())
        (output_dir / "full_story.txt").write_text(self.full_story, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def story_fragments_from_json(path: Path) -> list[StoryFragment]:
    data = read_json(path)
    raw_fragments = data.get("fragments", []) if isinstance(data, dict) else []
    fragments: list[StoryFragment] = []
    for idx, item in enumerate(raw_fragments):
        fragments.append(
            StoryFragment(
                id=int(item.get("id", idx + 1)),
                mood=str(item.get("mood", "CALM")).upper(),
                text=str(item.get("text", "")),
                music_prompt=item.get("music_prompt"),
                start_s=item.get("start_s"),
                end_s=item.get("end_s"),
                image_prompt=item.get("image_prompt"),
                visual_motif=item.get("visual_motif"),
                palette=item.get("palette"),
                motion=item.get("motion"),
                narrative_phase=item.get("narrative_phase"),
                story_event=item.get("story_event"),
                display_text=item.get("display_text"),
                keywords=[str(value) for value in (item.get("keywords") or [])],
                image_assets=image_assets_from_json(item.get("image_assets", [])),
                mood_cues=mood_cues_from_json(item.get("mood_cues", [])),
            )
        )
    return fragments


def music_segments_from_json(path: Path) -> list[MusicSegment]:
    raw_segments = read_json(path)
    if not isinstance(raw_segments, list):
        return []
    segments: list[MusicSegment] = []
    for idx, item in enumerate(raw_segments):
        if not isinstance(item, dict):
            continue
        segments.append(
            MusicSegment(
                id=int(item.get("id", idx + 1)),
                music_prompt=str(item.get("music_prompt") or ""),
                start_s=item.get("start_s"),
                end_s=item.get("end_s"),
                mood_hint=item.get("mood_hint"),
                confidence=item.get("confidence"),
                source=str(item.get("source") or "unknown"),
                valence=item.get("valence"),
                arousal=item.get("arousal"),
                tension=item.get("tension"),
                tempo_bpm=item.get("tempo_bpm"),
                tempo_description=item.get("tempo_description"),
                meter=item.get("meter"),
                mode=item.get("mode"),
                harmony=item.get("harmony"),
                dynamics=item.get("dynamics"),
                texture=item.get("texture"),
                rhythmic_character=item.get("rhythmic_character"),
                instruments=[str(value) for value in (item.get("instruments") or [])],
                genre_candidates=[str(value) for value in (item.get("genre_candidates") or [])],
                notable_events=[str(value) for value in (item.get("notable_events") or [])],
                story_energy=item.get("story_energy"),
                story_tension=item.get("story_tension"),
                story_direction=item.get("story_direction"),
                suggested_event=item.get("suggested_event"),
                visual_motion=item.get("visual_motion"),
                color_direction=item.get("color_direction"),
            )
        )
    return segments


def mood_cues_from_music_segments(
    segments: list[MusicSegment],
    *,
    start_s: float | None = None,
    end_s: float | None = None,
) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    for segment in segments:
        mood = str(segment.mood_hint or "").upper().strip()
        if mood not in MOOD_LABELS:
            continue
        cue_start = float(segment.start_s if segment.start_s is not None else start_s or 0.0)
        cue_end = float(segment.end_s if segment.end_s is not None else cue_start)
        if start_s is not None:
            cue_start = max(cue_start, float(start_s))
        if end_s is not None:
            cue_end = min(cue_end, float(end_s))
        if cue_end <= cue_start:
            continue
        if cues and cues[-1]["mood"] == mood and abs(float(cues[-1]["end_s"]) - cue_start) <= 0.05:
            cues[-1]["end_s"] = cue_end
        else:
            cues.append({"mood": mood, "start_s": cue_start, "end_s": cue_end})
    return cues


def mood_cues_from_json(raw_cues: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_cues, list):
        return []
    cues: list[dict[str, Any]] = []
    for raw in raw_cues:
        if not isinstance(raw, dict):
            continue
        mood = str(raw.get("mood") or "").upper().strip()
        if mood not in MOOD_LABELS:
            continue
        try:
            start = float(raw.get("start_s"))
            end = float(raw.get("end_s"))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        cues.append({"mood": mood, "start_s": start, "end_s": end})
    return cues


def image_assets_from_json(raw_assets: Any) -> list[ImageAsset]:
    if not isinstance(raw_assets, list):
        return []

    assets: list[ImageAsset] = []
    for raw in raw_assets:
        if not isinstance(raw, dict):
            continue
        prompt = str(raw.get("prompt", "")).strip()
        if not prompt:
            continue
        assets.append(
            ImageAsset(
                role=str(raw.get("role") or "background").strip().lower(),
                label=str(raw.get("label") or raw.get("role") or "visual asset").strip(),
                prompt=prompt,
                search_query=raw.get("search_query"),
                negative_prompt=raw.get("negative_prompt"),
                provider=raw.get("provider"),
                model=raw.get("model"),
                status=str(raw.get("status") or "planned"),
                local_path=raw.get("local_path"),
                remote_url=raw.get("remote_url"),
                source_url=raw.get("source_url"),
                license=raw.get("license"),
                creator=raw.get("creator"),
                error=raw.get("error"),
            )
        )
    return assets
