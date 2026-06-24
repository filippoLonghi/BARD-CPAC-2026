import sys
import os
from pathlib import Path

# Il nostro solito trucco per la cartella src
cartella_src = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if cartella_src not in sys.path:
    sys.path.insert(0, cartella_src)

from bard_core.audio.gemini_provider import analyze_with_gemini

# =====================================================================
# IL TRUCCO: Creiamo un finto "Settings" che ha solo quello che serve a Gemini!
# =====================================================================
class FintiSettings:
    def __init__(self):
        # Sostituisci "il-tuo-id-gcp" con l'ID vero del progetto Google Cloud del tuo amico
        self.gcp_project_id = "bard-anna" 
        self.gcp_location = "europe-west1" # Di solito è us-central1, se ne usa un'altra cambiala
        self.vertex_audio_model = "gemini-2.5-flash" # O il modello esatto che usate
        self.storage_bucket = None # Lasciamo None così non cerca di caricare nulla sul cloud

def test_analisi_audio():
    # 1. Il percorso dinamico antiproiettile per trovare l'mp3
    cartella_script = Path(__file__).parent 
    audio_path = cartella_script / ".." / ".." / "data" / "test_audio" / "marco-test.wav"
    audio_path = audio_path.resolve()

    if not audio_path.exists():
        print(f"ERRORE: Il file {audio_path} non esiste.")
        return

    # 2. Usiamo il nostro "finto" settings invece di quello originale
    settings = FintiSettings()

    print(f"Sto inviando {audio_path.name} a Gemini per l'analisi. Attendi...")

    try:
        segments = analyze_with_gemini(
            audio_path=audio_path,
            settings=settings,
            target_segments=8 
        )

        print("\n=== RISULTATI DELL'ANALISI ===")
        for seg in segments:
            print(f"\n▶ Segmento {seg.id} (da {seg.start_s}s a {seg.end_s}s)")
            print(f"  MOOD:       {seg.mood_hint}")
            print(f"  Prompt:     {seg.music_prompt}")
            print(f"  Emozioni:   Valence={seg.valence} | Arousal={seg.arousal} | Tension={seg.tension}")
            print(f"  Ritmo:      {seg.tempo_description} ({seg.tempo_bpm} BPM), Meter: {seg.meter}")
            print(f"  Strumenti:  {', '.join(seg.instruments) if seg.instruments else 'Nessuno'}")
            print(f"  Generi:     {', '.join(seg.genre_candidates) if seg.genre_candidates else 'Sconosciuti'}")
            print(f"  Eventi:     {', '.join(seg.notable_events) if seg.notable_events else 'Nessuno'}")
            print("-" * 50)

    except Exception as e:
        print(f"\nErrore durante l'esecuzione: {e}")

if __name__ == "__main__":
    test_analisi_audio()