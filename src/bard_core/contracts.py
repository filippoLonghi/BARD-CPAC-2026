from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json

MOOD_LABELS: list[str] = [
    "DARK",
    "CALM",
    "ANXIOUS",
    "DENSE",
    "RISING TENSION",
    "RELEASE",
    "BRIGHT",
    "SPARSE",
]

IMAGE_ASSET_ROLES: list[str] = ["background", "subject"]


def normalize_mood_label(value: object) -> str:
    mood = str(value or "").upper().strip()
    return mood if mood in MOOD_LABELS else "CALM"


def normalize_image_role(value: object) -> str | None:
    role = str(value or "").strip().lower()
    return role if role in IMAGE_ASSET_ROLES else None


def order_image_assets(assets: list["ImageAsset"]) -> list["ImageAsset"]:
    by_role: dict[str, ImageAsset] = {}
    for asset in assets:
        role = normalize_image_role(asset.role)
        if role is None or role in by_role:
            continue
        asset.role = role
        by_role[role] = asset
    return [by_role[role] for role in IMAGE_ASSET_ROLES if role in by_role]

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

    def normalized_mood(self) -> str:
        return normalize_mood_label(self.mood)


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

    def replay_story_json(self, *, processing_audio_path: str | None = None) -> dict[str, Any]:
        return to_replay_story_json(
            run_id=self.run_id,
            audio_path=self.audio_path,
            audio_duration_s=self.metadata.get("duration_s"),
            processing_audio_path=processing_audio_path or self.metadata.get("processing_audio_path"),
            fragments=self.fragments,
            full_story=self.full_story,
        )

    def run_manifest_json(
        self,
        *,
        trace_events: list[dict[str, Any]] | None = None,
        artifact_paths: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return to_run_manifest_json(
            run_id=self.run_id,
            audio_path=self.audio_path,
            metadata=self.metadata,
            music_segments=self.music_segments,
            story_bible=self.story_bible,
            story_state=self.story_state,
            trace_events=trace_events or [],
            artifact_paths=artifact_paths or {},
        )

    def write(
        self,
        output_dir: Path,
        *,
        debug_artifacts: bool = False,
        trace_events: list[dict[str, Any]] | None = None,
        processing_audio_path: str | None = None,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        story_path = output_dir / "story.json"
        manifest_path = output_dir / "run_manifest.json"
        artifact_paths = {
            "story": story_path.name,
            "run_manifest": manifest_path.name,
        }
        write_json(story_path, self.replay_story_json(processing_audio_path=processing_audio_path))
        write_json(
            manifest_path,
            self.run_manifest_json(trace_events=trace_events, artifact_paths=artifact_paths),
        )
        if debug_artifacts:
            debug_dir = output_dir / "debug"
            write_json(debug_dir / "result.json", self.to_dict())
            write_json(debug_dir / "music_segments.json", [asdict(seg) for seg in self.music_segments])
            write_json(debug_dir / "scene_cards.json", self.scene_cards())
            (debug_dir / "full_story.txt").write_text(self.full_story, encoding="utf-8")
        else:
            _remove_legacy_artifacts(output_dir)


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
                mood=normalize_mood_label(item.get("mood", "CALM")),
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


def to_replay_story_json(
    *,
    run_id: str,
    audio_path: str | None,
    audio_duration_s: object | None,
    processing_audio_path: str | None,
    fragments: list[StoryFragment],
    full_story: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "bard.replay_story",
        "version": 1,
        "run_id": run_id,
        "audio": _compact_dict(
            {
                "source_path": audio_path,
                "duration_s": audio_duration_s,
                "processing_audio_path": processing_audio_path,
            }
        ),
        "fragments": [_fragment_replay_json(fragment) for fragment in fragments],
        "full_story": full_story,
    }
    return _compact_dict(payload)


def to_run_manifest_json(
    *,
    run_id: str,
    audio_path: str,
    metadata: dict[str, Any],
    music_segments: list[MusicSegment],
    story_bible: dict[str, Any],
    story_state: dict[str, Any],
    trace_events: list[dict[str, Any]],
    artifact_paths: dict[str, str],
) -> dict[str, Any]:
    return _compact_dict(
        {
            "schema": "bard.run_manifest",
            "version": 1,
            "run_id": run_id,
            "audio_path": audio_path,
            "metadata": _compact_dict(metadata),
            "artifacts": artifact_paths,
            "trace": trace_events,
            "debug_context": _compact_dict(
                {
                    "music_segments": [_compact_dict(asdict(segment)) for segment in music_segments],
                    "story_bible": story_bible,
                    "story_state": story_state,
                }
            ),
        }
    )


def _fragment_replay_json(fragment: StoryFragment) -> dict[str, Any]:
    return _compact_dict(
        {
            "id": fragment.id,
            "start_s": fragment.start_s,
            "end_s": fragment.end_s,
            "mood": fragment.normalized_mood(),
            "text": fragment.text,
            "keywords": fragment.keywords,
            "image_assets": [_image_asset_replay_json(asset) for asset in order_image_assets(fragment.image_assets)],
        }
    )


def _image_asset_replay_json(asset: ImageAsset) -> dict[str, Any]:
    return _compact_dict(
        {
            "role": normalize_image_role(asset.role) or asset.role,
            "label": asset.label,
            "prompt": asset.prompt,
            "negative_prompt": asset.negative_prompt,
            "provider": asset.provider,
            "model": asset.model,
            "status": asset.status,
            "local_path": asset.local_path,
            "remote_url": asset.remote_url,
            "source_url": asset.source_url,
            "license": asset.license,
            "creator": asset.creator,
            "error": asset.error,
        }
    )


def _compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            nested = _compact_dict(value)
            if nested:
                compact[key] = nested
        elif isinstance(value, list):
            compact[key] = value
        elif value != "":
            compact[key] = value
    return compact


def _remove_legacy_artifacts(output_dir: Path) -> None:
    for name in ("result.json", "music_segments.json", "scene_cards.json", "full_story.txt"):
        path = output_dir / name
        if path.exists() and path.is_file():
            path.unlink()


def image_assets_from_json(raw_assets: Any) -> list[ImageAsset]:
    if not isinstance(raw_assets, list):
        return []

    assets: list[ImageAsset] = []
    for raw in raw_assets:
        if not isinstance(raw, dict):
            continue
        role = normalize_image_role(raw.get("role") or "background")
        if role is None:
            continue
        prompt = str(raw.get("prompt", "")).strip()
        if not prompt:
            continue
        assets.append(
            ImageAsset(
                role=role,
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
    return order_image_assets(assets)
