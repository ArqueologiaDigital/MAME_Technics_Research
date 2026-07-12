# Per-part effect application — the structure behind the chorus-depth question

**Date:** 2026-07-12. Static RE (unidasm on kn7000_program_decompressed.bin) + live capture, resolving
*where* the per-part effect DEPTH comes from and why a cold CHORUS toggle leaves the send at 0.

## The question (from effect-return-routing.md)
A cold CHORUS button press turns the effect on (LED cpr_led29 toggles) but writes the sub-TG chorus
send (0x8198) with DEPTH = 0 (0x0B00) -> on-but-inaudible. A SOUND DSP (part-effect) toggle re-writes it
with the real depth 0x3C (0x0B3C) -> audible. The manual says CHORUS is a direct global toggle ("adds
breadth"). Is the emulator missing a depth-apply, or is this faithful lazy application?

## Findings (live + disasm)
1. **The chorus send is always written by the same emitter primitive** 0x4C036FBA (PC captured at the
   0x98050002 store): cold -> 0x0B00 (depth 0), sound-dsp -> 0x0B3C (depth 0x3C). So the difference is
   the DEPTH the CALLER passes, not two different writers.
2. **The depth 0x3C is STORED, not computed on the toggle**: watching the whole 0x500B0000-0x500BFFFF
   effect/part-state RAM during a sound-dsp toggle caught ZERO writes of a 0x3C byte -> the sound-dsp
   path READS a pre-existing 0x3C and applies it; it does not compute/populate it then.
3. **The effect ENABLE flags live in 0x500C0758** (halfword). Disasm of the enable setters:
   - REVERB enable = bit 0x0200 (bit9): setter 0x4C00908F (`or 0x0200` on / `and 0xFFFFFDFF` off).
   - next effect enable = bit 0x0400 (bit10): setter 0x4C0090C0. More setters follow (0x4C0090EC+).
   Each enable setter ONLY sets/clears its flag in 0x500C0758 -- it does NOT write any sub-TG send.
4. **An apparent per-part effect-apply loop at 0x4C009000** (found immediately after the enable-flag
   setters): it iterates a part index d2 from (start) up to 0x22 (`inc d2; cmp 0x22,d2; blt`), and per
   part calls attribute getters (0x4C0384C4/D9/EE) + the send-writer 0x4C03A660. Structurally this is a
   "walk every part and apply its effect sends" routine. INFERENCE (not yet confirmed): the SOUND DSP /
   part-effect path invokes this (or an equivalent) to apply the stored depths, while a cold global
   enable toggle only sets the 0x500C0758 flag. Confirm by tracing the callers (see NEXT STEP).
5. **The per-part send-writer 0x4C03A660** indexes a PART-DESCRIPTOR POINTER ARRAY at **0x500CE404**
   (`d2 = part*0x130; a1 = 0x500CE404 + d2; a0 = *(a1)`), then reads the part TYPE/MODE byte at
   descriptor **+0x10** (`movbu (0x10,a0); and 0xCF; cmp 0x80/0x81/0x82/0x83`) to branch on the part
   kind before writing its sends. So per-part effect routing is keyed off 0x500CE404[part]->(+0x10).

## Interpretation
The global effect enable (CHORUS/REVERB/etc. button) sets a flag bit in 0x500C0758 and the LED; the
actual per-part send application (which reads each part's stored effect DEPTH and writes the sub-TG send)
is a SEPARATE pass = the 0x4C009000 loop, driven by the part-effect path. REVERB happens to apply its
send on toggle too (its send changes immediately), so reverb's toggle handler DOES reach a send-apply;
CHORUS's cold toggle does not (writes depth 0), only the part-effect recompute applies the stored 0x3C.

WHETHER THIS IS FAITHFUL OR A GAP is still open and now precisely scoped: it hinges on whether the real
firmware's CHORUS-enable handler triggers the 0x4C009000 apply loop (or an equivalent per-part apply). If
it does on real HW but not in the emulator, a state/trigger the emulator doesn't satisfy is blocking it
(an emulation gap, like the old effect-select handshake); if the enable handler genuinely only sets the
flag and relies on a later recompute, the cold-toggle silence is faithful and you hear chorus after the
next part-effect recompute. NEXT STEP: find the callers of 0x4C009000 (scan the image for its address)
and disassemble the CHORUS-enable handler to see if it calls the apply loop. NOT changing anything (rule
g -- do not fake the depth-apply). This maps a big chunk of the per-part effect model (the deferred
enabler for chorus-depth, APC/SEQ volume, and faithful per-effect sends).

## 2026-07-12 (later): CORRECTION — 0x4C009000/0x500CE404 is REVERB's per-part apply, NOT chorus's
Empirical test (data-read tap on the descriptor pointer slot 0x500CE404, scratchpad/retcap/desc.lua):
- REVERB toggle -> 0x500CE404 read **once** (the 0x4C009000 loop runs; reverb IS applied per-part
  through this descriptor path).
- COLD CHORUS toggle -> **0** reads. SOUND DSP toggle -> **0** reads.
So the inference in finding #4 above (that 0x4C009000 is the chorus/sound-dsp apply) is FALSIFIED: that
loop is the REVERB per-part apply. The CHORUS/SOUND-DSP/MULTI sends are applied by a DIFFERENT path that
does NOT walk 0x500CE404 -- and the SOUND DSP toggle's chorus-depth application (0x0B3C) goes through
that other, still-untraced path. (Instruction-fetch read-taps do NOT fire on the MN10300 in MAME, so
loop-execution can only be detected via a DATA access the routine makes -- hence the 0x500CE404 read
probe; the emitter-PC and depth-source facts above stand.)
NET: reverb uses the 0x4C009000 per-part descriptor loop; the other effects use a separate apply path.
The chorus-depth faithful-vs-gap question is UNRESOLVED and now needs debugger-level tracing of the
sound-dsp handler's chorus-send path (the read-tap tooling has hit its limit). This deep thread has
reached diminishing returns for a minor user-facing issue (chorus is audible via its screen; only the
quick home-screen toggle leaves depth 0) -- deferring further trace.

## Addresses (durable)
- Effect enable flags: **0x500C0758** (bit9=reverb; bit10,11=other effects). Setters at 0x4C00908F+.
- **REVERB** per-part effect-apply loop: **0x4C009000** (parts 0..0x22) — confirmed by the 0x500CE404
  read on reverb toggle only. (NOT the chorus/sound-dsp apply — see correction above.)
- REVERB per-part send-writer: **0x4C03A660**; part-descriptor pointer array **0x500CE404** (stride
  0x130); part type/mode byte at descriptor **+0x10** (mask 0xCF; 0x80-0x83 kinds).
- Sub-TG bus emitter primitive (all effects): **0x4C036FBA**.
- CHORUS/SOUND-DSP/MULTI apply path: DIFFERENT, untraced (does not walk 0x500CE404).

## 2026-07-12 (later 2): call-chain traced -- the chorus DEPTH-read logic + a reusable capability
NEW CAPABILITY (unblocks caller-tracing without -debug): MAME has no Lua debug/bp interface without
-debug, BUT cpu.state exposes PC/SP/A0-A3/D0-D3/MDR. At a DATA-access write-tap, read SP and walk the
stack (prog:read_u32(SP+i*4)) collecting lib return addresses (0x4C0xxxxx) = the CALLER CHAIN. This
recovers who called a shared primitive. (scratchpad/retcap/callchain.lua)

CHORUS-SEND CALLER CHAINS (at the emitter store, latch 0x8198):
- COLD chorus toggle (send=0x0B00, depth 0): emitter <- wrapper 0x4C037DB9 <- func@0x4C0050A3(=0x4C005000)
  <- 0x4C01013A <- 0x4C02F077 <- 0x4C03DDF5.  A1=0x500BA862.
- SOUND DSP toggle  (send=0x0B3C, depth 0x3C): emitter <- wrapper 0x4C037DB9 <- 0x4C03B301 <- func@
  0x4C005043(=0x4C005000) <- 0x4C01013A <- 0x4C02F10F <- 0x4C03DDF5.  A1=0x500BA800.
Both go through the SAME send-writer func **0x4C005000** and the SAME emitter wrapper 0x4C037DB9; the
depth differs because of the structure it reads.

THE DEPTH-READ LOGIC (disasm of 0x4C005000):
  a0 = *(0x20,sp)                         ; a part/effect structure pointer
  d1 = movhu (a0)                         ; *(a0) halfword
  d2 = movbu (0x15,a0)                    ; depth byte at a0+0x15
  if (d1 & 0x04)==0  -> d2 = 0            ; bit2 of *(a0) = "apply this depth" gate
  ...emit send = base(0x0B00) | d2
So the CHORUS DEPTH = (bit2 of *(a0) set) ? *(a0+0x15) : 0. Cold path -> 0 (bit2 clear OR +0x15==0);
sound-dsp path -> 0x3C. The depth 0x3C IS stored (confirmed earlier); the gate bit2 of *(a0) decides
whether it is applied.

FAITHFUL-vs-GAP now narrowed to: in the cold chorus-toggle context, does *(a0)&0x04 come out clear
(depth forced 0) because the real firmware genuinely defers depth-apply to the part-effect recompute
(faithful), or because the emulator hasn't populated a state the real chorus-toggle path would have set
(gap)? NEXT = capture a0 (=*(0x20,sp)) + *(a0) + *(a0+0x15) in the COLD vs sound-dsp context (walk the
frame), and find where bit2 of *(a0) gets set (the "apply" trigger). The 0x4C03B301 layer (only in the
sound-dsp chain) is the part-effect recompute that satisfies the gate. Structure: a0->+0x00 halfword
(bit2=apply gate), +0x15 byte (chorus depth). Still not changing anything (rule g). The stack-walk
capability is REUSABLE for the deferred floppy FDC-base trace too.

## 2026-07-12 (later 3): DEFINITIVE + corrects two earlier errors -- depth addr 0x500CE342, computed on toggle
Register dumps at the emitter store + a write-tap on the effect-depth array pinned it:
- The per-effect DEPTH array is at **0x500CE340**: sound-dsp depth @+0 (0x500CE340), CHORUS depth @+2
  (0x500CE342), etc. (byte per effect). At the emitter store A0 points into this array.
- **CORRECTION to "depth 0x3C is STORED, not computed":** WRONG -- I had tapped 0x500B0000-0x500BFFFF
  and missed 0x500Cxxxx. The chorus depth at 0x500CE342 is WRITTEN on EVERY effect toggle by PC
  **0x4C037DA8** (a 16-bit store of 0x0Bxx to 0x500CE342): 0x0B00 (depth 0) in the cold-chorus context,
  0x0B3C (depth 0x3C) in the sound-dsp context. So the depth is COMPUTED per toggle, not pre-stored.
- The computed value differs because of the CONTEXT: A1 (a part-settings pointer) = 0x500BA862 in the
  cold path vs 0x500BA800 (part-16 base) in the sound-dsp path; and the depth-read is gated by bit2 of
  *(a0) (a0=*(0x20,sp) in func 0x4C005000, from the earlier trace). Cold context -> gated to 0;
  sound-dsp context -> reads the real 0x3C from the part settings.
So the model is: an effect toggle runs func 0x4C005000 which computes the per-part effect depth
(bit2-gated read of the part settings), stores it to 0x500CE340+effect, and emits the sub-TG send from
there. The chorus-toggle CONTEXT (which part / gate state it iterates) yields depth 0; the sound-dsp
(part-effect) context yields 0x3C.

## CONCLUSION (chorus-depth thread) -- thoroughly understood, DEFERRED as minor
The faithful-vs-gap question ultimately hinges on the per-part iteration CONTEXT of the chorus-enable
toggle (which part-settings pointer / gate bit it uses) vs the part-effect recompute -- deep per-part
logic. This is a MINOR user-facing issue: chorus/multi ARE audible through their normal screens (the
divergence sweep drove chorus across 8 types with real output); only the quick home-screen on/off toggle
leaves the depth at 0 until a part-effect interaction. Across several ticks this has been mapped
thoroughly (emitter 0x4C036FBA; send-writer 0x4C005000 with the bit2-gated depth read; depth store
0x4C037DA8 -> 0x500CE342; reverb's separate per-part loop 0x4C009000 -> 0x500CE404). DEFERRING further
resolution -- diminishing returns for a minor issue; the map here is enough for a future dedicated pass
(or Felipe) to finish. NOT changing anything (rule g). Durable byproduct: the reusable stack-walk +
register-read-at-tap tracing capability (callchain.lua / gate.lua patterns), reusable for the floppy work.

## Addresses (durable, updated)
- Effect ENABLE flags: 0x500C0758 (bit9=reverb, bit10/11=others). Setters 0x4C00908F+.
- **Per-effect DEPTH array: 0x500CE340** (sound-dsp @+0, CHORUS @+2, ...). Written by 0x4C037DA8.
- CHORUS send-writer (bit2-gated depth read): func 0x4C005000; emitter wrapper 0x4C037DB9;
  sub-TG emitter primitive 0x4C036FBA.
- REVERB per-part apply loop 0x4C009000 -> send-writer 0x4C03A660 -> descriptor array 0x500CE404.
