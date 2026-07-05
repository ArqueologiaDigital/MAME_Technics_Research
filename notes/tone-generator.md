# KN7000 tone generators — register interface (decode in progress)

The KN7000 has two tone-generator LSIs on the MN10300 bus: the **main TG at
0x98040000** (IC203/204) and the **sub TG at 0x98050000** (IC207/208). This note
records the hardware register interface decoded from the firmware TG driver; it
is the groundwork for eventually modeling sound (the current driver just logs
these writes). Audible MIDI notes are blocked on this (see midi-rx.md).

## Hardware interface: a 32-bit register write, split into two 16-bit ports

The low-level TG write helper (0x487EFF70 sub / 0x487EFF92 main) takes a 32-bit
value and writes it as two halves:

```
487eff92: and  0x3f, d0          ; a 6-bit field
487eff98: asl  20, d0            ; -> bits 20..25 of the 32-bit word
487eff9b: or   d1, d0            ; d1, d2 = the rest (address/data), from caller
487eff9d: or   d2, d0
487effa0: lsr  16, d1            ; d1 = high 16 bits
487effa3: movhu d1, (0x98040000) ; HIGH 16 -> base+0   (main; sub uses 0x98050000)
487effa9: and  0xffff, d0
487effad: movhu d0, (0x98040002) ; LOW  16 -> base+2   (sub uses 0x98050002)
```

So one TG register access = **HIGH 16 bits -> 0x9804_0000, LOW 16 bits ->
0x9804_0002** (main; +0x10000 for the sub TG). This mirrors the KN5000's
register-indirect interface (address port + data port) but packs both into a
single 32-bit word written across the two adjacent 16-bit ports.

By analogy to the KN5000 (documented, shared codebase -- see below) and the
observed traffic, the **HIGH 16 bits are the register ADDRESS and the LOW 16
bits are the DATA**.

## Observed traffic: the FC0x refresh (not note data)

At the home screen the TG is written continuously with a cyclic pattern:
`(0x9804_0000)=0xFC08, (0x9804_0002)=0x0000` cycling the low nibble FC08 -> FC09
-> FC0A -> FC0B (both main and sub TG). Read as an address 0xFC0x, that is the
0xFC register group, channels 8-0xB, data 0 -- i.e. a periodic system/global
register refresh, NOT per-voice note data. This is consistent with the finding
in midi-rx.md that an injected MIDI note did not produce a distinct voice write.

## KN5000 voice-register map (the likely KN7000 template)

The KN5000 TG (also 64-voice wavetable, register-indirect) is documented in
kn5000-docs/tone-generator.md. Its register ADDRESS = `group<<8 | bank<<6 |
channel(0..63)`; offset = group*0x100 + bank*0x40 + channel. Key per-voice
registers (a MIDI note-on writes roughly these, then a key-on strobe):

| group.bank | purpose |
|---|---|
| 0.0 | Voice Control -- key on/off / mode state machine |
| 0.1 | Pitch increment (semitone table lookup) |
| 0.2 | Voice mode / velocity (bit15 = latch strobe) |
| 1.3 | Key-on flag (firmware writes 0x8100) |
| 4.0 | Note key info (note<<8, bit15 = active) |
| 5.0 | Modulation param (written just before KEY ON) |
| 8.0 | Main Volume (0xFF80 = mute) |

## Open / next

- Confirm the KN7000 address bit-layout. The helper ORs a 6-bit field (masked
  0x3f) at word bits 20..25 (= bits 4..9 of the high/address half) on top of the
  caller-supplied d1/d2. Whether that field is the channel, or the channel sits
  in d1 at bits 0..5 (KN5000-style) with this being a group/flag field, needs the
  caller (the note->voice path) traced -- the helper's callers build d1/d2 from a
  command stream interpreter at 0x487EFExx-0x487F00xx (bytes >=0x80 = commands).
- The note->voice path: trace from the MIDI note handler (fed by ISR 0x484B1E86,
  see midi-rx.md) to the first write of a voice's group-0.0 key-on for a real
  note, and capture the exact address/data for note 60 (C4) to pin the format.
- Then a minimal MAME `sound_stream` device on 0x98040000/0x98050000 can start:
  latch the address/data pairs into a 64-voice x N-register state, and (later)
  synthesize from the waveform ROMs. Even a silent state-capturing device would
  let a note write be verified by its pitch/note-info registers.

## Playback path is not driven in MAME (2026-07-05, tick ss+1)

Modeled the register-indirect latch (address -> base+0, data -> base+2) as a
temporary capture and logged every non-0xFC-group TG write, under two stimuli
after boot: (a) an injected MIDI note-on, and (b) a scripted START/STOP press.

- **Boot init DOES write voice-register groups**: at ~t=0.9 s the main TG gets
  groups **0x04 and 0x0C written across all 64 channels (both banks), data 0** --
  a clear/init pass. So the TG register-indirect path works and the firmware
  drives it during initialization.
- **No playback voice traffic**: neither the MIDI note nor the START/STOP press
  produced ANY non-0xFC TG write. The only ongoing traffic is the 0xFC0x
  system-refresh cycle. So the firmware's sound *playback* engine does not emit
  voice writes (pitch/note-on/velocity) in MAME.

Interpretation: sound playback is gated at the engine level. The most likely
cause is a tone-generator readiness/handshake that never completes because the
TG is unmodeled (the boot init runs, but the engine won't allocate/trigger
voices for notes or rhythm until the TG reports ready). Getting audible sound is
therefore a LARGE effort: (1) model the TG far enough that its readiness checks
pass and it accepts voice writes, (2) then the engine will drive voices, (3)
then synthesize from the waveform ROMs -- which may be undumped (the KN7000's
wave ROMs are separate from the program/table flash we have). This is not a
near-term win; parked with the register interface fully documented above.

### Update: DEMO press also produced no voice traffic (tick ww+1)

Tried triggering internal playback a third way: a scripted press of the button
labeled DEMO (SEG06 bit6). No non-0xFC TG write appeared, and a snapshot 6 s
later showed the home screen UNCHANGED -- so that press did nothing visible.
Likely the folklore label is wrong (the real DEMO button is elsewhere) or DEMO
needs a different interaction; either way it did not start playback. Combined
with the MIDI-note and START/STOP tests, three attempts now show no playback
voice traffic. The blocker stands: the sound engine needs either a modeled TG
that reports ready, or a reliably-triggerable playback action (which is limited
by the button-label uncertainty -- see gui-toolkit-event-system.md on why button
function names are widget-level, not a flat table). Sound remains parked.

## Driver now models the interface (tick yy+1)

The MAME driver now implements the register-indirect write interface (io_w):
address latch at base+0, data at base+2 -> a captured per-TG voice-register file
`m_tg_reg[2][0x1000]` (group<<8|bank<<6|channel < 0x1000); the 0xFC0x system
group and the 0x98040004/0x98040010 control writes are accepted without storing.
This is behavior-neutral (the TG is write-only -- verified: every firmware ref to
0x98040000/2/4/10 and 0x98050000/2 is a write; boot still reaches the home
screen) and replaces the log-everything fallback. It is the state-capture
foundation; a `sound_stream` synthesis stage (reading this register file + the
waveform ROMs, which may be undumped) is the remaining work, gated behind getting
the firmware's playback engine to actually emit voices (see the null-playback
tests above).

## Sound gap localized: playback is never triggered (tick zz+1)

Probed the two firmware entry points that would produce sound -- **MainSoundAdd
0x4848C043** (voice allocator) and **MainSeqRun 0x484948BC** (sequencer run) --
across boot, a raw injected MIDI note, and a START/STOP double-press. **Neither
ran even once.** So the tone-generator voice path is dormant not because of a
hardware gate but because the higher-level playback is never *triggered*:

- `MainDspCheck` (0x484A062A) is a stub that just returns 0 -- not a readiness
  gate.
- The TG is write-only (no status read to satisfy).
- The boot-time voice writes (groups 0x04/0x0C, all channels) come from init, not
  playback.

The remaining work for audible notes is therefore **triggering playback**, which
splits into: (a) routing an incoming MIDI note to a sounding part so the note
handler calls MainSoundAdd -- gated by the default MIDI-receive configuration
(the TMidiInput/MidiInputGrid widgets), and (b) starting the sequencer / a rhythm
via the correct panel operation -- gated by the button-identity uncertainty
(START/STOP navigates to the rhythm-select page here rather than starting play;
see gui-toolkit-event-system.md on why button function names are widget-level).
Only after playback is triggered and voices flow into the captured register file
does the actual synthesis stage (and the possibly-undumped waveform ROMs) become
the next problem. This redirects future sound work away from TG/DSP hardware
modeling and toward the playback-trigger path.
