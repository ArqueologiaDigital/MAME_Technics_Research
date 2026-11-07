# Evidence: the listening recordings of 2026-10-21

**Claim:** the levels in `../README.md` (peak and RMS of each recording, the gain per comparison group) were measured
from the WAVs that `../mklisten.py` wrote. **Verdict:** the recordings were scratch (`~/compartilhado/tmp/listen-2026-10-21/`,
406 MB) and were retired on 2026-11-07. This folder keeps what backs the numbers, and the five MP3s (the owner
kept them).

| file                          | what it is                                                                               |
|-------------------------------|------------------------------------------------------------------------------------------|
| `stats.txt`                   | `mklisten.py`'s analysis table, as written, beside the recordings                        |
| `README-listening-folder.txt` | the listening folder's own README (per-file length, peak, RMS, what each group compares) |
| `recordings.sha256`           | sha256 of every WAV and MP3 there, and of the raw WAVs under `work/`                     |
| `recordings/`                 | the five MP3s, as listened to (sha256 in `recordings.sha256`)                            |

To make them again: `../run_midi.sh` and `../run_aw.sh`, then `../mklisten.py` (`../README.md`). The emulator they were
recorded with was the published `kn7000-emulator/kn7000` of 2026-10-21 (md5 `7336efbe`), so a rerun on a later build
measures that build.
