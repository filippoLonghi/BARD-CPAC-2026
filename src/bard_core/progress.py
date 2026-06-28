from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import perf_counter
from typing import Any


@dataclass
class TraceEvent:
    elapsed_s: float
    label: str
    fields: dict[str, Any] = field(default_factory=dict)


class PipelineTracer:
    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self._start = perf_counter()
        self.events: list[TraceEvent] = []
        self._lock = Lock()

    def log(self, label: str, **fields: Any) -> None:
        elapsed_s = perf_counter() - self._start
        clean_fields = {key: _jsonable(value) for key, value in fields.items() if value is not None}
        with self._lock:
            self.events.append(TraceEvent(elapsed_s=elapsed_s, label=label, fields=clean_fields))
            if self.enabled:
                suffix = " ".join(f"{key}={_format_value(value)}" for key, value in clean_fields.items())
                print(f"[{elapsed_s:07.3f}] {label}{(' ' + suffix) if suffix else ''}", flush=True)

    def to_json(self) -> list[dict[str, Any]]:
        return [
            {"elapsed_s": round(event.elapsed_s, 3), "label": event.label, **event.fields}
            for event in self.events
        ]


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_format_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(f"{key}:{_format_value(item)}" for key, item in value.items()) + "}"
    text = str(value)
    return text if " " not in text else repr(text)
