# Key-bed FIFO make/break encoding — the "stuck notes" fix (2026-07-10)

## Symptom
Felipe: the key bed emitted key-on but never key-off (or key-off was read as another
key-on) — stuck notes. Reproduced on BOTH the USB-MIDI controller and the PC key
bindings, observed as the pressed-key rectangles in the CHORD FINDER staying drawn.

## Root cause (firmware RE — unambiguous)
The key-bed voice-event FIFO word (read at 0x98050004) is `low = key code, high = velocity`.
MAKE/BREAK is encoded in **bit 7 of the key byte**, NOT in the velocity:

- FIFO reader `0x484480e5`: `btst 0x80, d0` on the word's low byte routes the event —
  bit7 CLEAR -> note-on path (0x4844811a), bit7 SET -> note-off / hold path (0x484480ea).
- Decoder `0x4844812d` @ `0x48448151`: `btst 0x80, d2` again — bit7 CLEAR -> compute pitch
  (gate the voice ON); bit7 SET -> `jmp 0x484481f8` which clears the gate byte (key UP).

So a word with bit7=0 is a NOTE-ON **regardless of velocity** — velocity 0 is a note-on
with velocity 0, not a note-off. The driver used to send releases as `(key, velocity 0)`
(bit7=0), so the firmware read every release as another note-on -> notes stuck.

### The sustain/hold re-latch (why release velocity = 0xFF)
On the note-off path, after gating the voice off, `0x484480fa`: `cmp 0xff, d2` (d2 = velocity);
if velocity != 0xFF it STORES the key (bit7 masked off) into the held-key slot 0x501496a2 +
sets flag 0x50007768, and the next key-bed poll (0x4844807c) re-decodes that held key with
bit7=0 -> re-gates the note ON. A release with **velocity 0xFF** hits the `beq` and SKIPS the
re-latch — a clean key-up. So the correct release word is `key | 0x80` with velocity `0xFF`.

## Fix (kn7000.cpp)
- PC keys (`kbd_key`): press -> `kbd_push(idx, 0x64)`; release -> `kbd_push(idx | 0x80, 0xFF)`.
- MIDI bridge (`kbd_midi_rx`): note-on -> `kbd_push(idx, vel)`; note-off (MIDI 0x8n, or 0x9n
  vel 0) -> `kbd_push(idx | 0x80, 0xFF)`. (Key indices are 0x00..0x3C, so bit7 is free.)
- Corrected the FIFO header/read comments (they wrongly said "velocity 0 = note-off").

## Verification
1. FIFO read tap: press C4 -> firmware reads 0x6418 (key 0x18, bit7=0, vel 0x64 = note-on);
   release -> reads 0xFF98 (key 0x98, **bit7=1**, vel 0xFF = note-off). Exactly one of each.
2. Disassembly: bit7=1 -> gate off (0x48448151); vel 0xFF -> skip re-latch (0x484480fa).
3. Visual (CHORD FINDER mini-keyboard held-key dots): press F-major -> F-A-C dots; release,
   press G-major -> dots MOVE to G-B-D (do NOT accumulate to all six) -> releases work.
   (Side result: the STAGE-2 bank-A LCD soft-key binding SEG11 0x01 correctly toggled
   CHORD FINDER on the APC SELECT screen — a live confirmation of a context soft-key.)
