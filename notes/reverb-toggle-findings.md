# REVERB on/off toggle — complete inspection (2026-07-11, workflow wf_870ba134-582)

Felipe: "I cannot toggle reverb on/off in the emulator as I can on the real KN7000."
VERDICT: **the toggle already works end-to-end in firmware/UI/LED — what is missing is the
HARDWARE CONSEQUENCE MODEL: the TG's effect-send bus.** It is NOT a DSP host-port operation.

## The chain (verified live, link by link)
- SEG0F.0x04 press -> bank-A event 0x00702060 -> ring -> central processor 0x48414542 ->
  subscription queue 0x50033F64 -> panel function "REVERB" (descriptor 0x48603860, event 0xF0079).
- SHORT press: toggle handler runs in ~30-40 ms: **global reverb flag = RAM 0x500C0758 bit9**
  (lib setter 0x4C00908F; ON store PC 0x4C0090AA / OFF 0x4C0090B8); **button LED cpr_led27
  toggles** (shadows 0x50150A47/0x50150A67 bit3). VERIFIED WORKING in MAME today.
- PRESS-AND-HOLD 2s: **the REVERB setting screen opens** (Room1/2, Plate1/2, Concert1/2, Dark1/2,
  TOTAL DEPTH 80, Effect Memory) — VERIFIED WORKING in MAME today (snapshot).
- The toggle's ONLY hardware action = **7 immediate writes to the SUB TG's output-bus/effect-send
  registers (0x80xx-0x83xx family @0x98050000, emitted by lib 0x4C036FBA)** — a dry/wet crossfade:
    0x803A: 0x007F (ON) <-> 0x7F00 (OFF)   ; wet/dry level pair
    0x80B8: 0x0366 (ON) <-> 0x0300 (OFF)   ; reverb SEND level 0x66 <-> 0
    0x8338: 0x8550 (ON) <-> 0x8500 (OFF)
  Per-note voicing registers are IDENTICAL on vs off — routing is bus-level, applied instantly
  (matches the real machine cutting a reverb tail immediately).
- Our kn7000_tonegen drops the whole 0x8xxx register family (handles only 0x2400/0x0000/0x0001/
  0x2009/0x1C02/0x0004-0x000A), and the TG->DSP bridge carries a single dry mix with no send bus:
  **the toggle cannot affect audio in the current model.**

## Corrections to prior beliefs (IMPORTANT — several notes/memories were wrong)
1. ***(0x500A01E0) == 0xFFFFFFFF is the NORMAL IDLE state*** of a transaction scratch pointer
   (2-buffer pool 0x5009EB58/0x5009F69C; boot runs dozens of alloc->commit->reset cycles). It was
   NOT evidence of a dead effect-select subsystem. The "DspEffectSelect path is dead" conclusion
   (stuck-note era + reverb-divergence era) is WITHDRAWN for the current normal-boot state.
2. **The effect-select path WORKS today**: the control press (SOUND GUITAR) ran the full pipeline
   live: param block alloc (0x5009F69C) -> mailbox-6 -> task 7 -> 74 index-port writes
   (0x1D x1, 0x1C x25, 0x40/41/42/04 x12 each) -> 158 data words. (The driver DOES receive 0x1D --
   currently ignored; harmless so far.)
3. **Reverb ON/OFF != effect-type selection.** DspEffectSelect(9,type) picks WHICH reverb is loaded
   in the DSP; the on/off toggle is pure TG bus routing. Both are healthy firmware-side.
4. The reverb type/depth SETTINGS live in the settings database (trie 0x4858B424; block 0x4C:
   on/off bits keys 0x8020-family, type key 0xA100) — panel-memory backed, with boot defaults.

## What faithful audible reverb still needs (in dependency order)
1. **Model the TG effect-send bus** (registers now decoded to family level): tonegen honors
   0x80B8-family send levels + 0x803A wet/dry pair; output becomes TWO stereo buses (dry main +
   reverb send). The full per-slot register map needs one more capture pass (per-part sends read
   from 0x500B5340+part*0x54C when flag 0x500C0758 bit9 set — lib consumers 0x4C0053B3/0x4C005433/
   0x4C01349E/0x4C03089E/0x4C033C11).
2. **Wire the send bus into the DSP bridge** as the reverb input (real F.3 SPORT wiring: determine
   which RX slots carry the send vs the dry main).
3. **Fix the parked SHARC reverb divergence** (loop gain ~1.0, needs reference-diff) — without it
   the wet return rails regardless of routing.
4. DSPAUDIO default flips to "through DSP" once (3) lands.
Until (3), the faithful-behavior increment available: honor the toggle in the TG (send muted when
off), so ON/OFF audibly changes the send feed — but the wet path itself stays parked.
