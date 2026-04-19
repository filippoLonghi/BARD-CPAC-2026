from __future__ import annotations

import time

from ..contracts import StoryFragment


def send_fragments_to_processing(
    fragments: list[StoryFragment],
    host: str,
    port: int,
    slide_duration_s: float,
    start_delay_s: float = 2.0,
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
        time.sleep(0.05)
    client.send_message("/start", [])
