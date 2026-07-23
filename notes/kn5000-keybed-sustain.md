# KN5000 keybed sustain — held notes no longer auto-release after ~45ms

## Symptom
On the real KN5000 a held key sustains. In the emulator a scripted/held key
played only ~45ms then went silent, even though the key was still down.

Before fix (scripted C4, press t=20.00, release t=22.00), WAV ch1 peak:
```
t=20.00 10262   t=20.02 10262   t=20.04 10262   t=20.06 0 ... 22.00 0
```
i.e. a ~45ms burst, then silence for the rest of the hold.

## Root cause — the task's initial localization was WRONG; corrected here
The task blamed `ToneGen_Poll_All` (0x03D217) reading held/voice state from the
keybed port 0x110000/0x110002 and our HLE returning empty. **Measured false:**
instrumenting the keybed reads shows `ToneGen_Poll_All` (PC ~03D230) is **never
called at runtime** — it runs once at boot from `Audio_System_Init`→`ToneGen_Init`
and never again. During play the *only* keybed reader is the event reader
`ToneGen_Read_Voice_Data` (PC 03D0D1/03D0DF), and it correctly delivers exactly
one note-on (t=20.004) and one note-off (t=22.009). The keybed HLE was fine.

The real 45ms key-off (0x7E00 to tonegen voices 0/1) comes from PC **02B4DB** =
`LABEL_02B4A1`, called by the sub-CPU's **software voice-manager**
(`LABEL_02219F`/`LABEL_02222A`, v142 asm L13273-13330):

```
CALR DAC_Write_Sample   ; writes bank idx (0..3) to 0x100000, reads HL back
LD DE,(2936h+bank*2)    ; prev-active bitmap
OR  DE,HL               ; prev | current
XOR (XSP+004),(292Eh..) ; M = firmware-commanded-ON bitmap
AND (XSP+004),(292Eh..) ;  -> ((prev|cur) XOR M) AND M  = "commanded ON but chip SILENT"
... per set bit: CALL LABEL_02B4A1  ; write 0x7E00 key-off, free the voice slot
```

`DAC_Write_Sample` (v142 asm L11479-11483) is mis-named: it writes a bank index
to **0x100000** and reads a **16-bit active-voice bitmap** back from **0x100000**.

## THE DISTINGUISHER (event vs. state on the tonegen)
It is **the port**, not a mode written before the read:
* **Keybed EVENTS** (note-on/off FIFO): read via **0x110000 / 0x110002**
  (`ToneGen_Read_Voice_Data`). Encoding: L=note, E=velocity, 0xFF=note-off.
* **Voice-active STATE poll**: read via **0x100000** (`DAC_Write_Sample`), after
  writing a bank index 0..3. Encoding: 16-bit bitmap, bit i = voice (bank*16+i)
  currently sounding.

Our HLE mapped 0x100000 **write-only** (address latch) — the read was unmapped
and returned 0, so every held voice looked SILENT ⇒ the voice-manager freed it
after one ~45ms poll cycle. This is the whole bug.

## Fix
1. `kn5000_tonegen_device::status_r()` (new): read handler for **0x100000**.
   Returns the active-voice bitmap for bank = `m_addr_latch & 3`; bit i set when
   voice (bank*16+i) is keyed on. Driver map for 0x100000 changed `.w(addr_w)` →
   `.rw(status_r, addr_w)`. Now held voices report active ⇒ no premature release.

2. Key RELEASE detection. The sub-CPU never writes 0x7E00 on real key-up; it
   re-programs the voice's hardware envelope with a *release* ramp — a burst of 6
   writes to groups 8/9/A (routine `LABEL_027FD6`, v142 asm L23045). Note-ON also
   programs those same EG registers, so a write alone is ambiguous. Discriminator:
   note-ON rewrites the group0/bank0 gate (0x8100), so its EG writes land ~12µs
   after `process_key_on`; the release burst carries no gate and arrives only once
   the key is released (≥45ms, usually seconds, later). We trigger on the
   **group9/bank0** EG write (0x0900+ch) when the voice is keyed on and it is
   **>1ms after the note-on gate** → `process_key_off(ch)`. Then `status_r` reports
   the voice inactive and the firmware completes its normal voice-free handshake.
   A per-voice `key_on_time` (set in `process_key_on`) carries the gate timestamp.

## Verification (all pass)
* Sustain: held C4 now holds ch1 peak 10148 from t=20.00 through 21.98 (was a
  ~45ms burst). Releases cleanly — silent from t=22.02 (not stuck-on).
* Note-on + velocity: unchanged event path; note sounds with correct amplitude.
* Note-off at real release: releases shortly after t=22.
* `-validate kn5000`: clean. Boots to the play screen (PMEM, RIGHT1=Piano).
* IC307 PCM (`has_pcm` @ 8ab1610): untouched.

## Files
* `src/mame/matsushita/kn5000_tonegen.cpp` / `.h` — `status_r()`, release detect,
  `key_on_time`.
* `src/mame/matsushita/kn5000.cpp` — 0x100000 map now read/write.

## Caveat
The release detector is a heuristic (group9/bank0 EG write >1ms after the gate).
Robust for held keys; a sound that legitimately re-programs group9/bank0 during
sustain (e.g. some LFO/modulation voices) could false-trigger a release. Not
observed for the tested Piano voice (no register writes at all during 20.006→
22.010). A fuller fix would model the tonegen hardware envelope generator.
