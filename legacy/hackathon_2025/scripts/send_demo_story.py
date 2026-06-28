import time

from pythonosc import udp_client


ip = "127.0.0.1"
port = 5005
client = udp_client.SimpleUDPClient(ip, port)

timing = 15

data = {
    "fragments": [
        {
            "id": 1,
            "mood": "CALM",
            "text": (
                "The train from Cremona hissed into Milano Lambrate. Three students stepped onto the platform, "
                "marching solemnly toward the Politecnico's Campus Leonardo. Today was the final battle: the "
                "submission for Creative Programming and Computing."
            ),
        },
        {
            "id": 2,
            "mood": "CALM",
            "text": (
                "They seized a table in a chaotic study room and summoned their secret weapon: a fourth teammate "
                "connecting remotely from Calabria. 'I'm in', his voice crackled over the laptop speakers."
            ),
        },
        {
            "id": 3,
            "mood": "ANXIOUS",
            "text": (
                "Disaster struck immediately. The code refused to compile, sensors remained lifeless, and morale "
                "plummeted. 'Nothing works!' one cried out, burying his face in his hands. For hours, they fought "
                "against bugs and syntax errors, guided by the calm voice from the south."
            ),
        },
        {
            "id": 4,
            "mood": "ENERGETIC",
            "text": (
                "Suddenly, a breakthrough. A single line of code fixed the loop. The prototype finally blinked to "
                "life just minutes before the deadline. Breathless, they rushed to the presentation. As the device "
                "performed perfectly before the professors, they shared a tired, triumphant glance with the "
                "pixelated face on their screen. The war was over; they had won."
            ),
        },
    ],
    "full_story": "",
}

time.sleep(10)
print(f"Sending data to {ip}:{port}...")

client.send_message("/config/duration", timing)
print(f"Sent duration: {timing}s")

for item in data["fragments"]:
    client.send_message("/segment", [str(item["mood"]), str(item["text"])])
    print(f"Sent segment: {item['text']}")
    time.sleep(0.05)

client.send_message("/start", [])
print("Transmission complete.")
