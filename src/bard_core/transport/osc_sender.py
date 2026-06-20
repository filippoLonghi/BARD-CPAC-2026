from __future__ import annotations

import os
from pathlib import Path
import threading
import time
import urllib.parse

from typing import Callable

from ..contracts import StoryFragment


class ProcessingOscStream:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        slide_duration_s: float,
        include_images: bool,
        ready_port: int = 5007,
        ready_bind_host: str = "127.0.0.1",
        path_mapper: Callable[[Path], str] | None = None,
    ) -> None:
        try:
            from pythonosc import udp_client
        except ImportError as exc:
            raise RuntimeError("OSC output requires `pip install python-osc`.") from exc
        self.client = udp_client.SimpleUDPClient(host, port)
        self.slide_duration_s = slide_duration_s
        self.include_images = include_images
        self.ready_port = ready_port
        self.ready_bind_host = ready_bind_host
        self.path_mapper = path_mapper
        self.started = False

    def start(self) -> None:
        self.client.send_message("/reset", [])
        self.client.send_message("/config/duration", float(self.slide_duration_s))
        self.client.send_message("/config/streaming", 1)

    def send(self, fragment: StoryFragment, *, final: bool = False) -> None:
        self.client.send_message("/segment", _segment_payload(fragment, self.slide_duration_s))
        time.sleep(0.03)
        self.client.send_message("/keywords", [int(fragment.id), *fragment.keywords])
        if self.include_images:
            _send_fragment_images(self.client, fragment, self.path_mapper)
        if final:
            self.client.send_message("/finish", [])

    def play(self) -> None:
        if not self.started:
            self.client.send_message("/start", [])
            self.started = True

    def settle(self, delay_s: float) -> None:
        time.sleep(max(0.0, delay_s))

    def set_processing_audio(self, audio_path: str) -> None:
        self.client.send_message("/audio", [audio_path])

    def await_ready(self, timeout_s: float) -> None:
        self._await_response("/prepare", "/ready", timeout_s)

    def prime(self, timeout_s: float) -> None:
        self._await_response("/prime", "/primed", timeout_s)

    def _await_response(self, request_address: str, response_address: str, timeout_s: float) -> None:
        try:
            from pythonosc import dispatcher, osc_server
        except ImportError as exc:
            raise RuntimeError("OSC readiness checks require `pip install python-osc`.") from exc

        ready = threading.Event()
        receiver = dispatcher.Dispatcher()
        receiver.map(response_address, lambda *_: ready.set())
        try:
            server = osc_server.ThreadingOSCUDPServer((self.ready_bind_host, self.ready_port), receiver)
        except OSError as exc:
            raise RuntimeError(f"Cannot open Processing readiness port {self.ready_port}: {exc}") from exc
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.client.send_message(request_address, [int(self.ready_port)])
            if not ready.wait(max(0.5, timeout_s)):
                raise RuntimeError(
                    f"Processing did not answer {request_address}. Open the BARD sketch, press Run, "
                    "and check OSC ports or the Processing console."
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1.0)


def send_fragments_to_processing(
    fragments: list[StoryFragment],
    host: str,
    port: int,
    slide_duration_s: float,
    start_delay_s: float = 2.0,
    include_images: bool = False,
    audio_path: Path | None = None,
    wait_for_audio: bool = True,
    ready_port: int = 5007,
    ready_timeout_s: float = 8.0,
) -> None:
    if start_delay_s > 0:
        time.sleep(start_delay_s)

    stream = ProcessingOscStream(
        host,
        port,
        slide_duration_s=slide_duration_s,
        include_images=include_images,
        ready_port=ready_port,
    )
    stream.start()
    stream.await_ready(ready_timeout_s)
    for index, fragment in enumerate(fragments):
        stream.send(fragment, final=index == len(fragments) - 1)
        time.sleep(0.05)
    playback = prepare_audio_playback(audio_path) if audio_path else None
    stream.prime(ready_timeout_s)
    stream.play()
    if playback:
        playback.play()
    if playback and wait_for_audio:
        playback.wait()


def _send_fragment_images(
    client,
    fragment: StoryFragment,
    path_mapper: Callable[[Path], str] | None = None,
) -> None:
    for layer_index, asset in enumerate(fragment.image_assets):
        if not asset.local_path:
            continue
        local_path = Path(asset.local_path).expanduser().resolve()
        if not local_path.exists():
            continue
        client.send_message(
            "/image",
            [
                int(fragment.id),
                int(layer_index),
                asset.role or "background",
                path_mapper(local_path) if path_mapper else local_path.as_posix(),
            ],
        )
        time.sleep(0.03)


def _segment_payload(fragment: StoryFragment, fallback_duration_s: float) -> list[object]:
    start_s = float(fragment.start_s or 0.0)
    end_s = float(fragment.end_s) if fragment.end_s is not None else start_s + fallback_duration_s
    # testo_sicuro è il testo del frammento codificato in modo da avere le lettere accentate in OSC
    testo_sicuro = urllib.parse.quote(fragment.text)
    return [
        int(fragment.id),
        fragment.normalized_mood(),
        testo_sicuro,
        start_s,
        max(start_s + 0.1, end_s),
    ]


def prepare_audio_playback(audio_path: Path):
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    try:
        import pygame
    except ImportError as exc:
        raise RuntimeError("Synchronized audio playback requires `pip install pygame`.") from exc

    resolved = audio_path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Audio playback file not found: {resolved}")
    pygame.mixer.init()
    pygame.mixer.music.load(str(resolved))

    class Playback:
        def play(self) -> None:
            pygame.mixer.music.play()

        def wait(self) -> None:
            clock = pygame.time.Clock()
            while pygame.mixer.music.get_busy():
                clock.tick(30)

    return Playback()
