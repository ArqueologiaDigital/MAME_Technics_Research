# KN5000 MIDI → internal keybed bridge (velocity-sensitive)

Lets a host MIDI controller play the KN5000's OWN 61-key bed with velocity — a
separate input from the rear MIDI jacks (which go to the TLCS-900 serial /
firmware MIDI engine). Mirrors the KN7000 `m_kbd_midi_uart` / `kbd_midi_rx`
pattern (kn7000.cpp), re-encoded to the KN5000 keybed wire format.

## Data path
```
host MIDI controller ──► MIDI_PORT "kbdmidi" (slot: midiin)
   ──► kn5000_kbd_uart_device (31250 baud 8N1 deserializer, rx_cb per byte)
   ──► kn5000_state::kbd_midi_rx(byte)   [MIDI running-status parser]
   ──► m_tonegen->push_keybed_event(word) [same FIFO keybed_scan() feeds]
   ──► SubCPU reads 0x110000 ──► voice engine ──► sound
```

## Wire format (matches keybed_scan())
- note-on : `(velocity << 8) | (raw | 0x80)`  where raw = MIDI note − 36
- note-off: `0xFF00 | raw`  (velocity 0xFF = the SubCPU's note-off marker)
- 61-key bed spans MIDI 36..96 (C2..C7); notes outside are ignored.
- MIDI velocity is passed straight through (note-on velocity 0 ⇒ note-off).

## Files
- `kn5000.cpp`: `kn5000_kbd_uart_device` (byte↔bit MIDI UART, modelled on the
  KN7000 SIO UART / vocalizer.cpp); `kbd_midi_rx()` + running-status state;
  machine-config wiring (`KN5000_KBD_UART` + `MIDI_PORT "kbdmidi"`); `diserial.h`
  include. No changes to the tonegen or the existing rear MIDI (mdin/mdout).

## Verification (2026-07-23)
Host-MIDI delivery to headless MAME could NOT be exercised in this environment —
under PipeWire, MAME creates no ALSA-seq input client, so `aplaymidi` → "Midi
Through" never reaches MAME (an environment/routing limitation, not the bridge).
Instead the bridge was proven by injecting canned MIDI bytes straight through the
real `kbd_midi_rx()` parser (the byte-deserializer ahead of it is MAME-standard
and identical to the proven KN7000 UART). MEASURED, WAV ch1 RMS:
- note-on C4 (vel 110) sustains ~7400 until note-off, then clean release.
- **Velocity sensitive:** soft note (vel 30) = 2575 RMS, hard note (vel 120) =
  7405 RMS → **2.88× louder**; both sustain and release cleanly.
- `-validate kn5000` clean; boots to the play screen.

## How to use / test with real hardware
`kn7000 kn5000 -rompath ./roms -kbdmidi midiin` with a host MIDI controller
connected (MAME's midiin opens the host default MIDI input). Play the controller;
notes drive the internal key bed with velocity, sustaining while held.
