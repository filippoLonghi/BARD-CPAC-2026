from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json


MOOD_LABELS = ["DARK", "ANXIOUS", "CALM", "DENSE", "RISING TENSION", "RELEASE", "BRIGHT", "SPARSE"]


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

    def __post_init__(self):
        self.mood = self.normalized_mood()
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
            )
        )
    return fragments


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
