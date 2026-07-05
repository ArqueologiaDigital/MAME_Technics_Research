# MIDI input (RX) — verified working at the byte/ISR level

The KN7000 has two MIDI ports on the MN10300's on-chip serial channels SC1/SC2
(0x34000810 / 0x34000820), 8N1 at 31250 baud (see boot-performance-and-clock.md
for the baud/clock derivation). The driver already models the full RX path; this
note records a direct verification that MIDI bytes reach and are processed by the
firmware.

## The path (all already in the driver)

MAME MIDI-in port `mdin1`/`mdin2` (a `midiin_slot`) -> bit-serial `rxd_handler`
-> `kn7000_sio_uart_device::rx_w` (deserializes at 31250/8N1) -> `rx_cb` ->
`kn7000_state::midi_rx<Ch>()` -> `sio_rx_push(ch, byte)`. `sio_rx_push` enqueues
the byte in the per-channel RX FIFO and asserts the channel's RX interrupt group
(MIDI1 -> group 0x12 via ICR 0x34000148; MIDI2 -> group 0x14 via 0x34000150).
The firmware's MIDI-1 RX ISR is 0x484B1E86 (MIDI-2: 0x484B2037); it reads the
data register at +0x09 and acks its GxICR.

## Verification (2026-07-05)

Injected a note-on `90 3C 64` then note-off `80 3C 40` into MIDI-1 after boot
(temporary `sys_tick` hook; removed afterward) and probed the firmware:

- **The MIDI RX ISR 0x484B1E86 ran exactly 6 times = once per injected byte**
  (3 note-on + 3 note-off). So every MIDI byte is delivered to and consumed by
  the firmware's interrupt handler. The RX interrupt (group 0x12), its ICR, and
  the ISR registration are all correctly set up by the firmware and delivered by
  the driver's INTC model. **MIDI input works end-to-end at the byte level.**

- **Note -> sound is NOT yet observable.** The dual tone generators
  (0x98040000 main / 0x98050000 sub) are written continuously with a cyclic
  `FC08..FC0B` command/refresh pattern (data 0000) both before and after the
  note; the note-on did not add a distinct voice write in the 0x98040000-
  0x98060000 range. So the firmware receives the note but does not turn it into
  an audible tone-generator voice in this test.

  Most likely cause: the note-to-voice path depends on the sound subsystem being
  up, which it is not -- the sound init "spins on the 0x9805000E readback latch"
  (io-map.md) and the tone generators / DSP are not emulated yet. The MIDI note
  handler probably gates voice allocation on tone-generator readiness. (Other
  possibilities: default MIDI receive-channel/part routing not enabling
  playback at the home screen.)

## Using real MIDI input

The ports are exposed as standard MAME MIDI slots, so a host MIDI source works:
`./kn7000 kn7000 -mdin1 midiin` (and `-mdout1 midiout` for MIDI out). Bytes will
flow into the firmware exactly as verified above.

## Next

To get audible/observable notes: bring up the tone-generator model (at least far
enough that the sound-init latch 0x9805000E and the readiness checks pass), then
re-test -- the note handler should then allocate a voice and the note write will
be distinguishable from the FC08..FC0B refresh. Also worth decoding: the
0x98040000/0x98050000 command format (the FC0x cycle) and the voice/pitch
register layout, so a note can be verified by its pitch value for note 60 (C4).
