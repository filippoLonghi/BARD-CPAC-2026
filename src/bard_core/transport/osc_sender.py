from __future__ import annotations

from pathlib import Path
import time

from ..contracts import StoryFragment


def send_fragments_to_processing(
    fragments: list[StoryFragment],
    host: str,
    port: int,
    slide_duration_s: float,
    start_delay_s: float = 2.0,
    include_images: bool = False,
) -> None:
    try:
        from pythonosc import udp_client
    except ImportError as exc:
        raise RuntimeError("OSC output requires `pip install python-osc`.") from exc

    client = udp_client.SimpleUDPClient(host, port)
    if start_delay_s > 0:
        time.sleep(start_delay_s)

    client.send_message("/config/duration", float(slide_duration_s))
    for fragment in fragments:
        client.send_message("/segment", [fragment.normalized_mood(), fragment.text])
        if include_images:
            _send_fragment_images(client, fragment)
        time.sleep(0.05)
    client.send_message("/start", [])


def _send_fragment_images(client, fragment: StoryFragment) -> None:
    for layer_index, asset in enumerate(fragment.image_assets):
        if not asset.local_path:
            continue
        local_path = Path(asset.local_path).expanduser().resolve()
        if not local_path.exists():
            continue
        client.send_message(
            "/image",
            [int(fragment.id), int(layer_index), asset.role or "background", local_path.as_posix()],
        )
