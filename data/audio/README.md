# Mood And Genre Test Audio

The local names describe sources or broad test contrasts, not ground-truth model labels. Normal runs
store audio-analysis details in `run_manifest.json`; add `--debug-artifacts --keep-audio-chunks` when
you want `debug/music_segments.json` alongside saved WAV chunks.

| Local file | Useful test | Duration | Creator | License | Source |
|---|---|---:|---|---|---|
| `sad_walk_komiku.ogg` | restrained/sad source title; verify instruments rather than trusting title | 191.29 s | Komiku | CC0 reported by Commons | [Commons](https://commons.wikimedia.org/wiki/File:Komiku_-_32_-_Sad_walk_with_sad_piano.ogg) |
| `upbeat_pop.ogg` | brighter pop/rock contrast | 197.88 s | Silent Partner | CC BY 3.0 | [Commons](https://commons.wikimedia.org/wiki/File:Silent_Partner_-_Bet_On_It.ogg) |
| `robot_gypsy_jazz.ogg` | short energetic contrast | 66.14 s | John Bartmann | license conflict; embedded tag says CC BY-NC-ND 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:John_Bartmann_-_13_-_Robot_Gypsy_Jazz.ogg) |
| `dark_suspense.ogg` | dark ambient/suspense contrast | 140.02 s | Rafael Krux | CC0 reported by Commons | [Commons](https://commons.wikimedia.org/wiki/File:Rafael_Krux_-_Horror_Suspense.ogg) |
| `dramatic_ending.ogg` | long dramatic build and ending | 229.92 s | Soft and Furious | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Soft_and_Furious_-_10_-_Dramatic_Ending.ogg) |
| `schubert_adagio_allegro.ogg` | one long recording with a slow-to-fast internal change | 648.10 s | Franz Schubert recording on Commons | CC BY-SA 2.0 | [Commons](https://commons.wikimedia.org/wiki/File:Franz_Schubert_-_Octet_-_1._Adagio_-_Allegro.ogg) |

`sad_walk_komiku.ogg` used to be called `melancholic_piano.ogg` locally. That was misleading: “piano”
came from the source title, not from BARD analysis, and the embedded genre tag says Rock. The neutral
filename avoids treating source metadata as acoustic truth.

Do not use `robot_gypsy_jazz.ogg` in redistributed demo media until its license conflict is resolved.
CC BY and CC BY-SA material requires attribution; keep this file with the test audio.
