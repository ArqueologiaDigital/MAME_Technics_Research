# NEC uPD6383GF — the data-pointer ORIGIN, by CONTINUOUS whole-frame execution

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-23.
Tool: `tools/kn5000_dsp_origin.py`. Follows `kn5000-dsp-trace.md` (traced each body from
each header register, reported the origin **NOT PINNED**), `kn5000-dsp-pointer.md` (found the
header loads), `kn5000-dsp-headerdecode.md` (the frame dispatch), `kn5000-dsp-addressing.md`
(the proven pointer-delta rule). Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_origin.py
```

Claims are tagged **MEASURED**, **INFERRED**, **PROVEN BY CONSTRUCTION**, **SPECULATIVE**.
**No audio path was added; the core is still instantiated DISABLED; the KN5000 driver was not
touched; the disassembler was not edited.**

---

## Headline

1. **★★ THE ORIGIN VALUE IS PINNED FOR THE EQ (0x19) AND NOW SHARED WITH THE REVERB — the
   trace note's "no common constant" is SUPERSEDED.** The trace note (`-trace.md` Q1) reported
   *EQ wants 0x19, reverb wants ~0xA6, not a common constant → needs hardware*. That used an
   **incomplete reverb host map** (only the high block `{86,97,9E,A6,…}`). The COMPLETE map,
   read straight from the sub-CPU ROM's T1 records, gives the reverb a **LOW state block
   `{19,1A,1B,1C,1D,1E}`** as well. The pointer walk lands that low block at origin **~0x15–0x19**
   (6/6 at 0x16, 5/6 at 0x19) — i.e. the reverb's **low pointer coincides with the EQ's exact
   0x19**, *across the unit-0 / unit-1 boundary*. `0xA6` is a **second, separate reverb pointer**
   for the high delay bank. **MEASURED.**
2. **★★ THE ORIGIN'S SOURCE IS STILL NOT A DECODED WORD, AND CONTINUOUS EXECUTION PROVES IT
   CLEANLY.** Running the whole frame continuously (header 0..48 → call unit-0 body → header
   50..58 → call unit-1 body → epilogue) and reading the data pointer at each body's first
   instruction: model A (body reads register `0x821`, which the header absolutely loads) leaves
   **0x70**; model B (body reads a free accumulator the loads never touch) leaves **0x06** from a
   zero base. **Neither is 0x19.** And no register-load immediate *anywhere* in the header or
   epilogue is 0x19 (the full set is `{12,25,26,50,57,64,6C,70,86,90,92,B1,C0}`). **MEASURED.**
3. **★★ (a) vs (b), DECIDED BY A STRUCTURAL FACT: THE HEADER IS EFFECT-INDEPENDENT.** The
   header + epilogue are uploaded once and are byte-identical for every effect (only the body
   images differ, `-headerdecode.md` §0). Yet three unit-0 effects need three different origins
   (EQ 0x19; gated reverb ~0x07; compressor's cells are scalar, 0x02/0x03). **A single common-
   header value cannot supply a per-effect origin.** Therefore:
   * **Hypothesis (a) "a header load we mis-scoped carries the origin" — FALSIFIED** twice over:
     no header word loads 0x19, and even if one did it could not be *per-effect*.
   * **Hypothesis (b) "the body's pre-motif walk moves the header base 0x70 to 0x19" —
     FALSIFIED** (trace note: 0x70 walks to 0xBB, and making the pre-motif inert breaks the +4
     stride the EQ lock depends on).
   * **What SURVIVES: a per-effect DESCRIPTOR-relative base the HOST pokes** before the frame
     (`-parameters.md` §7). **INFERRED (strong, by elimination).**
4. **★ A CONCRETE, HARDWARE-FREE NEXT EXPERIMENT — NOT "needs a hardware address-bus read".**
   The cold-boot capture loaded CHORUS + reverb, **not** the EQ, so the EQ's own origin-poke is
   absent from it. Selecting **PARAMETRIC EQ** in MAME and capturing the uC-IF host stream should
   show the pointer-init poke `= 0x19` (predict `801.0.19.821` or a `0x825`-route load). That is a
   MAME-driving capture, no physical KN5000 required.
5. **★ NEW EVIDENCE THAT THE `0x820`/`0x822` ESCAPE-LOADS ARE THE STATE POINTERS.** The epilogue
   word `859.0.86.822` loads register `0x822 <- #$86` — and `0x86` is exactly the **base of the
   reverb's HIGH state block** `{86,97,9E,A6,…}`. The five header `0x820` escape-loads
   (`92/12/57/B1/C0`) and this `0x822` load are the undecoded register-selection words the trace
   note (§Q1 reading 1) predicted as the "fourth pointer". Decoding the escape-format load word
   is the concrete static target. **INFERRED.**
6. **COVERAGE UNCHANGED AT 18.3 % (545/2974).** This pass decoded no new body word; it bought a
   host-coincidence upgrade, a falsification of both origin hypotheses, and a per-effect-poke
   reading. Counting any of those as vocabulary would be the over-claim this series refuses.

---

## Positive controls (validated BEFORE any origin claim)

`tools/kn5000_dsp_origin.py` §0:

* **body pointer-loads = 0** over 87 valid images — reproduces `-pointer.md` §1 (the header holds
  every load; no body loads the pointer).
* **EQ +4 biquad walk locks UNIQUELY at 0x19** — the five band-motif starts land on the host state
  cells `{64,68,6C,70,74}` *in order* at exactly one origin, `0x19`, and nowhere else in 256.
* **biquad transfer-function impulse err = 0.000e+00** on 9 ROM banks
  (`kn5000_dsp_semantics.py verify`) — the addressing rule this interpreter reuses is the one
  already proven exact.

## The measurement (§3 of the tool)

```
    origin  EQ_state  REV_low  REV_high
     0x14    0/5      5/6     0/9
     0x16    0/5      6/6     0/9      <- reverb low-block peak
     0x19    5/5      5/6     0/9      <- EQ geometric lock
    reverb HIGH-block overlap peaks at 0xA6 (6/9)  -- a SECOND pointer
```

The EQ lock is a **clean geometric** result (unique origin, in-order stride-4 match). The reverb
low-block match is a **set-intersection** (5/6 at 0x19, 6/6 at 0x16), not a clean geometric lock,
**because the reverb's pointer-delta rule is known-broken** (`-pointer.md` §6: the reverb fails
the D-RAM extent test under every one of the 512 class subsets; the phaser's `0x76` vs `0x7B`
writer/reader mismatch is the same defect). So the honest reading is: the reverb's low state bank
sits at the **same ~0x19 origin** as the EQ, to within the delta rule's known ±few-cell error.

## Why continuous execution cannot emit 0x19 (§1, §4)

The per-frame program IS one continuous pass (`-headerdecode.md` §3): HW restarts the PC at the
header, the header sets up and CALLs unit 0's body, it returns, the header sets up and CALLs
unit 1's body, it returns, the epilogue runs, the chip waits for Fs. This interpreter runs that
path and tracks the data pointer across the call boundaries. The result:

* the header's `801.0.70.821` is an **absolute** load — it destroys whatever the preamble's
  class-2/A words accumulated, so model A pins body-entry at **0x70** regardless of the preamble;
* a free-accumulator pointer (model B) nets **+6** over header words 0..48, i.e. **0x06** from a
  zero base — it would need a persistent base of `0x13` to reach `0x19`, and nothing sets `0x13`;
* **the header is identical for all effects**, so it *structurally cannot* be the source of a
  value that differs per effect (EQ 0x19 ≠ gated-reverb 0x07). This is the decisive point and it
  needs no measurement.

The per-effect origin therefore lives in **host-poked per-effect state**, not in the resident
program. That is `-trace.md` Q1's surviving reading (2) — the descriptor-relative base — now
selected over reading (1) by the effect-independence of the header.

## Misses, limits, what this instrument is blind to

1. **The origin's SOURCE is not observed, only bounded.** We prove it is not in the resident
   program and infer it is a host poke; we do not see the poke, because the one capture we have
   does not load the EQ. §4's experiment closes this.
2. **The reverb low-block match rides the broken delta rule.** 6/6 at 0x16 vs the EQ's exact 0x19
   is *consistent* with a shared origin but is not independent confirmation of `0x19` to the cell.
3. **The compressor is NOT a valid origin control.** Its parameters (THRESHOLD 0x04, RATIO 0x0D,
   attack/release) are **scalars**, not a pointer-walked array (`-paramsemantics.md` §5: the
   host-coincidence lever works on arrays, not scalars). Its cells are reached by direct/cursor
   addressing, so it contributes no pointer-origin evidence — reported here so it is not mistaken
   for a third coincidence.
4. **One capture, one boot, one effect pair.** Everything about the host map is static (from the
   ROM's T1 records, which are solid); everything about which register the *body* reads is still
   the decoded-subset inference, unchanged from `-trace.md`.

## Coverage

Recomputed the same scoped way (`tools/kn5000_dsp_hi12.py coverage`): **18.3 % (545/2974),
UNCHANGED**. No body word was decoded. What this pass bought: the EQ↔reverb origin coincidence
(host-map upgrade), the clean falsification of both origin-source hypotheses via header
effect-independence, and the `0x822<-#$86` lead that the escape-loads are the state pointers.
