# WSA1R work: what is UPSTREAMABLE and what is DSP-decoding scaffolding

**Felipe, 2026-09-14:** *"This fix to the MIDI implementation is generally good for the driver to be
later submitted upstream, while the custom rom is specific to the dsp decoding effort. Be sure to
keep track of which is which so that we can later separate them when preparing PRs."*

This file is that ledger. Standing rule it serves: a PR branch is an **extract** off
`upstream/master`, never a copy of the overlay — see `MAME-PR-*` and the project's PR-extraction
rule. Nothing in the right-hand column may ever reach a PR.

---

## A. UPSTREAMABLE — genuine driver/device work

| commit | what | PR-worthy? |
|---|---|---|
| `5b32b3a` | **`l7a1429` startup SEGFAULT fixed + ABI guard.** `wsa1r` crashed on every start in the device constructor (`rep stos` overrunning) because `WSA1R_ENABLE_ACOUSTIC_HLE` changes `sizeof` from 8952 to 2112880 and MAME's build system does not treat `-D` flags as a dependency, so two objects disagreed. The guard turns a silent crash into a `fatalerror` naming the cause. | ★★ **Yes** — a real crash fix. The guard is defensive and self-contained. ⚠ Its comment references research macros; reword for upstream. |
| `5d76514` | **`wsa1_midi_uart` RX/TX diagnostic**, `WSA1R_MIDI_LOG=1`, default off: logs assembled RX bytes, RXD transitions, and every byte handed to the TX FIFO. | ★ **Maybe** — a small, gated debug aid. Upstream may not want it; harmless if dropped. |

⚠ **There is NO MIDI driver bug to upstream.** An earlier reading of mine — "the MIDI receive path
is broken" — was **wrong**, and the correction is the useful part: MAME's own `midiin` deliberately
delays a *file's* playback, `m_sequence_start = std::max(machine().time(), attotime(10, 0))`,
commented *"at least 10 seconds after starting to allow the keyboards to initialize"*. Every test
shorter than that plays nothing. The WSA1R's UART bridge was correct throughout.

★ **MIDI emulation is now VALIDATED end-to-end** (see below), which is itself worth knowing before
any MIDI-touching PR.

## B. DSP-DECODING SCAFFOLDING — never upstream

| item | what |
|---|---|
| `e8832e6` | `tools/wsa1r-sysex-monitor/` — the SysEx debug monitor, its patcher, build script and Lua rigs |
| — | any patched `prom_a` image (`patched_ic12.bin`) |
| — | `notes/WSA1R-SYSEX-MONITOR-BUILD.md`, `HARDWARE-CUSTOM-DSP-PROGRAMS-WSA1R.md` |
| earlier | the `upd6383` census arms and diagnostics (`UPD6383_*` envs), which exist to decode the ISA |

These modify a **customer ROM image** and exist solely to interrogate the µPD6383. They are
research instruments, not emulation of the real machine, and a PR containing them would be wrong on
its face.

⚠ The dividing question is simple: **does it make MAME emulate the real hardware more faithfully
(A), or does it help us learn what the DSP's instructions mean (B)?** The monitor is B even though
it runs inside MAME, because no real WSA1R has it.

---

## The MIDI validation, for the record

End-to-end, 2026-09-14, on the patched ROM:

```
   wsa1_midi_uart: RX byte F0 (t=10.500319)     <- 320 us apart = 31250 baud, correct
   wsa1_midi_uart: RX byte 7E (t=10.500639)
   wsa1_midi_uart: RX byte 7D (t=10.500959)
   wsa1_midi_uart: RX byte 01 (t=10.501279)
   wsa1_midi_uart: RX byte F7 (t=10.501599)

   RXBYTE  124   SXSTART 1   STOCK 2   CLAIM 2   IDENT 2   SEND 2060 (baseline 2058, so +2)
   (0xA9) = 0x23   = bit 0 accepted | bit 1 in-message | bit 5 OUR CLAIM
   ✅ END-TO-END PASS
```

So: a MIDI file on `-midiin` → MAME's `midiin` → the bit-serial bridge → the CPU's SC0 → the
firmware's MIDI ISR → the SysEx parser → **our monitor**, which recognised its marker, claimed the
message, dispatched the command and handed a reply to the firmware's transmitter.

⚠ Two rig lessons worth keeping: MAME's Lua address-space taps must be **bus-width aligned** (an
odd start address is rejected outright), and TLCS-900 registers are exposed **bank-qualified**
(`XDE0`…`XDE3`, never plain `DE`).

★ **And now in the other direction too, with no Lua at all** (`tools/wsa1r-sysex-monitor/midi_roundtrip.sh`):

```
   ✅ ident  F0 7E 7D 7F 01 00 F7
   ✅ peek   F0 7E 7D 7E 0F 00 07 0E 07 0D 07 0F 00 01 00 00 0F 07 00 00 F7
   ✅ stock  (control: no SysEx, as required)
```

`-midiin <file>` → UART → firmware ISR → monitor → ring `0x601432` → INTTX0 → SC0BUF → `-midiout`
→ ALSA → `aseqdump`. **MAME's MIDI is validated in both directions, against an external program.**

The same run seen at the UART, with `WSA1R_MIDI_LOG=1 … -log` (`error.log`), five bytes in and
seven out, 320 µs apart in each direction — 31250 baud, as it should be:

```
   RX byte F0 (t=0011.000,319)   TX byte F0 (t=0011.0…)
   RX byte 7E                    TX byte 7E
   RX byte 7D                    TX byte 7D
   RX byte 01                    TX byte 7F
   RX byte F7                    TX byte 01 / 00 / F7
                                 TX byte FE …   <- Active Sensing resumes
```
That is column-A knowledge even though the monitor is column B: any future MIDI-touching PR can
cite it.

⚠ The bug that hid this for a round was **entirely in our ROM patch, not in MAME**: the monitor was
sending through `0xF40ED4`, which is the CPU1↔CPU2 link sender, not the MIDI transmitter. Nothing
about it implicates the driver.
