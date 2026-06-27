import asyncio
import os
from pathlib import Path

import edge_tts
import pygame
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer


VOICE = "en-US-ChristopherNeural"
OUTPUT_FILE = Path("outputs/voice/temp_voice.mp3")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

pygame.mixer.init()


async def generate_edge_audio(text: str, output_file: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)


def speak_handler(address, *args) -> None:
    text_to_read = args[0]
    print(f"[Christopher]: {text_to_read}")

    try:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        pygame.mixer.music.unload()

        if os.path.exists(OUTPUT_FILE):
            try:
                os.remove(OUTPUT_FILE)
            except PermissionError:
                print("Could not remove the previous voice file; it may still be in use.")

        asyncio.run(generate_edge_audio(text_to_read, str(OUTPUT_FILE)))
        pygame.mixer.music.load(str(OUTPUT_FILE))
        pygame.mixer.music.play()

    except Exception as e:
        print(f"Voice error: {e}")


dispatcher = Dispatcher()
dispatcher.map("/speak", speak_handler)

ip = "127.0.0.1"
port = 5006

print(f"EDGE voice server listening on {ip}:{port}")
print(f"Selected voice: {VOICE}")

server = BlockingOSCUDPServer((ip, port), dispatcher)
server.serve_forever()
