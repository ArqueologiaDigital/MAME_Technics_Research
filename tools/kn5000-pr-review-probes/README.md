# Probes from the pre-submission review of the KN5000 tone generator PR

Written 2026-08-20 during an adversarial review of the three candidate PR branches in
`~/compartilhado/mame-pr-tonegen`. They check claims about the device against the actual ROM
contents rather than against the code's own comments.

| script | question it answers |
|---|---|
| `pagedir.py` | Re-implements the device's `parse_page_directories()` read-only. Can a page that is NOT a directory pass the six structural checks? This is the safety question for the walk: three of the four waveform ROMs are `NO_DUMP` and therefore zero-filled. |
| `parse304.py` | The same, pointed specifically at IC304 -- the socket the demo selects 60% of the time and which has no dump. |
| `parse.py` | The same for IC307, the one genuine dump, as the positive control. |
| `peak_probe.py` | Peak absolute sample of every IC307 recording, to test whether PCM voices can reach full scale and clip when summed. |
| `rms_probe.py` | The loudness counterpart: each recording's RMS, to compare a PCM voice against the placeholder tone it replaces. |
| `ovf.py` | Overflow check on the sample arithmetic. |
| `pitch.py` | Independent re-derivation of the per-recording pitch constants from the `table_data` mask ROM. |

All are read-only and take no arguments: `python3 <script>`. Paths are hardcoded to
`~/compartilhado/kn5000_original_roms/kn5000/`.

⚠ These are PROBES, not tools -- terse, no argument parsing. The polished descendants live in
`tools/kn5000-pitch-probes/`, `tools/kn5000-rootpitch/` and `tools/kn5000-rom-structure/`.

## Why they exist

The review they belong to found defects that months of listening tests had not: `M_PI` used where
MSVC will not compile it, six per-voice members missing from the save-state registration, a banner
describing a device that had been rewritten under it, and a factual claim in a commit message that
the diff itself refutes. None of those change what the emulator sounds like, which is exactly why
capture-and-measure could not find them.
