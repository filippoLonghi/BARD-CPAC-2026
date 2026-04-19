from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json


MOOD_LABELS = ["ENERGETIC", "SOLO", "CALM", "DEEP", "DISSONANT", "ANXIOUS"]


@dataclass
class MusicSegment:
    id: int
    music_prompt: str
    start_s: float | None = None
    end_s: float | None = None
    mood_hint: str | None = None
    confidence: float | None = None
    source: str = "unknown"


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
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "audio_path": self.audio_path,
            "music_segments": [asdict(seg) for seg in self.music_segments],
            "fragments": [asdict(fragment) for fragment in self.fragments],
            "full_story": self.full_story,
            "metadata": self.metadata,
        }

    def write(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_dir / "result.json", self.to_dict())
        write_json(output_dir / "music_segments.json", [asdict(seg) for seg in self.music_segments])
        write_json(
            output_dir / "story.json",
            {
                "fragments": [asdict(fragment) for fragment in self.fragments],
                "full_story": self.full_story,
            },
        )
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
            )
        )
    return fragments
