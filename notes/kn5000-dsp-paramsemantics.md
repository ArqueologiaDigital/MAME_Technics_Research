# NEC uPD6383GF — instruction semantics from the parameter → cell → reader chain

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-23.
Tool: `tools/kn5000_dsp_paramsemantics.py` (imports `kn5000_dsp_params` and
`kn5000_dsp_addressing`; **neither is edited, no audio, the core stays disabled**).

A NEW semantic pass using a lever the earlier passes did not have: the COMPLETE
per-effect NAMED parameter list (`-paramlist.md`, `tools/kn5000_dsp_paramlist_capture.json`)
propagated through the host-write cell (`-parameters.md`, T1/T2) into the instruction(s)
that read that cell (`-addressing.md`, the pointer rule). Chain:

```
   USER PARAMETER (known meaning/unit)
     -> HOST WRITE CELL   (T1[opcode][operand], MEASURED)
     -> BODY INSTRUCTION that reads it (pointer walk / coeff cursor / class presence)
```

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED** or **SPECULATIVE**.
Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_paramsemantics.py
```

---

## Headline

1. **The chain reproduces the known bindings (the positive controls PASS).** Validating
   before extending, per the rules of evidence:
   * **LFO control — PASS.** Over the 27 DSP-page effects in scope, the UI LFO controls
     (`LFO SPEED`/`SLOW LFO SPEED`/`LFO WAVEFORM`) are present in a body **iff** the body
     contains `hi12 = 0x082` (the LFO read): **12 true-positives, 12 true-negatives, 0
     false-negatives**. The three "false positives" (ENHANCER, ROTARY/ROCK ROTARY) are
     modulation effects whose LFO is not surfaced as an `LFO SPEED` slot — i.e. correct.
     So `082` **is** the reader of the UI LFO controls. **MEASURED (presence + absence).**
   * **Biquad control — PASS, structural, 5/5.** PARAMETRIC EQ's `op70` host-writes coeffs
     `{00,06,0C,12,18}` (stride 6) and state `{64,68,6C,70,74}` (stride 4); the body
     reproduces both — six coefficient-cursor fetches/band and a `+4` pointer walk/band —
     and origin `0x19` lands channel-0's five state cells on the host block **5 of 5**.
     This is the `-addressing.md` result, re-derived here from the parameter side.
   * **VOLUME / REV SEND tail.** The two universal output-mix cells are `0x90` (`op21`,
     the MEASURED 0..0.8 level) and `0x06` (`op63`), each in 33/92 streamed effects; the
     reverb family uses the `0x86` counterpart and has **no** `0x90` (a reverb is the send
     bus, so no REV SEND slot) — exactly as the paramlist predicts.
2. **A per-effect NAMED-parameter → host-cell binding table for the 38 DSP-page effects**
   (`sect_bind`). This is the new artifact: every effect's ordered parameters printed
   against the DSP cells its stream writes. E.g. SINGLE DELAY `DELAY L/R → 0x26/0x28`
   (`op67`, ms→samples), `FEEDBACK L/R → …`; MULTI TAP `DELAY 1‑4 → 0x26/28/29/2A`,
   `PAN 1‑4 → 0x03‑06`.
3. **NEW operand-meaning in the compressor.** The compressor front end is the **C40
   envelope detector**, present **twice** (two level detectors, L/R). A compressor's
   one-pole smoother coefficient **is** its attack/release time constant, so the UI
   `ATTACK SENS.`/`RELEASE SENS.` (cells `0x02/0x03`, `op6D`) are the coefficients those
   C40 words consume. **INFERRED** (from meaning + the C40 being the only smoother in the
   body); it gives the C40 family an operand *meaning* it did not have.
4. **The comparison machinery: a clean NEGATIVE result.** A present-AND-absence sweep over
   the whole corpus finds **no `hi12` opcode unique to the three threshold effects**
   (COMPRESSOR, SLOW ATTACKER, GATED REVERB). There is **no distinct compare-and-branch /
   conditional-select instruction class** — consistent with the hand-unrolled, branchless
   bodies (`-necfamily.md` §6). The threshold-dependent gain is computed **arithmetically**
   (the C40 smoother chain + multiplies), not by a comparator word. This *falsifies* the
   brief's expectation that a decodable comparator sits around THRESHOLD/RATIO, and it is
   reported as prominently as the hits (the rules ask for that).

---

## 1. The binding table (`sect_bind`) — MEASURED cells, INFERRED alignment

The name-index arrays give the ordered, named parameters; the T2 stream resolves to the
host WRITE cells. **They are not 1:1**: some parameters emit an endpoint/L‑R *pair* of
records, some emit *none* (the LFO rate is set through the phase path, not this
translator), and every effect carries hidden constant records (`op74→1D`, `op63→06`,
`op21→90`). So the tool prints the resolved cells *alongside* the names rather than
forcing a positional decode — the cells are MEASURED, the name↔cell pairing is INFERRED
except where a family argument pins it (below). The corpus-wide facts that fall out
cleanly are the two universal tail cells (§Headline 1) and the family pins of §2–§3.

## 2. Positive control — the LFO read is the LFO-control reader (MEASURED)

`hi12 = 0x082` was INFERRED as "LFO read" from co-occurrence (`-core-draft.md`). The
parameter side now *confirms it as the reader*: it is present in a body **iff** the UI
exposes an LFO-rate/waveform slot (0 false-negatives across the DSP page). This is the
positive control the method needed before trusting anything new — the chain reproduces a
known binding with both a presence and an absence prediction. (Note: `hi12 = 0x092`, a
different family, is **not** LFO-specific — it also appears in distortion/overdrive/EQ —
so the clean LFO marker is `082`, and any earlier conflation of `092`/`082` should read
`082` for the LFO read.)

## 3. The compressor, decoded as far as the chain allows

```
   UI parameter        cell (host)   role
   THRESHOLD           0x04 (op72)   gain-computer input threshold
   RATIO               0x0D (op72)   gain-computer slope
   ATTACK SENS.(s)     0x02/0x0B     one-pole smoother coeff -> C40 detector   (INFERRED)
   RELEASE SENS.(s)    0x03/0x0C     one-pole smoother coeff -> C40 detector   (INFERRED)
   VOLUME / REV SEND   0x90 / 0x06   universal output-mix levels
```

The body (40 words) contains the **C40 envelope detector twice** — the level-detection
front end a compressor must have, one per channel. The attack/release parameters are
**time constants in seconds**; the only mechanism in the body that turns a coefficient
into a time constant is the one-pole C40 smoother, so `ATTACK/RELEASE SENS.` are the
coefficients the C40 words read. **INFERRED** (the absolute origin is unpinned, so the
exact C40↔0x02/0x03 read cannot be *measured* — see §5), but it is the only reading
consistent with the parameter units and the single smoother present.

**The comparator.** No word class is unique to the threshold effects (`sect_comp`), so the
"compare level against THRESHOLD" step is **not** a distinct opcode. On this branchless,
hand-unrolled machine the gain reduction is a smooth arithmetic function of the detected
level, threshold and ratio — computed with the ordinary MAC/ALU words, not a compare.
The `(hi12,class,lo12)` families that *are* unique to the set all belong to the GATED
REVERB's all-pass/DRAM tail (`104.2.*.407`, `212.A.*.655`, `880.1.*.41A`, `C40.3.*.359`,
…), i.e. reverb plumbing, not a comparator. **The comparison machinery was NOT found as a
localisable instruction — and the corpus says it does not exist as one.**

## 4. What each frequent unknown word's operands MEAN (progress short of a full opcode)

Per the brief's item 3 — report operand meanings even where the operation stays uncertain:

* **`hi12 = 0xC40` (envelope detector, 46 occ.)** — in the compressor its coefficient
  operand is the **attack/release time constant** (§3); wherever it appears (chorus/reverb
  damping/LFO smoothing) it is a **one-pole smoother** and its coefficient is a *rate/time*
  quantity, never a mix gain. **INFERRED.**
* **`hi12 = 0x082` (LFO read, 64 occ.)** — its operand is the **LFO phase/output**; present
  exactly on the effects whose UI exposes `LFO SPEED`/`WAVEFORM`. **MEASURED (reader).**
* **`op21 → 0x90` / `op63 → 0x06` readers** — the **output-mix levels** (VOLUME + REV
  SEND); their readers are the last gain multiplies before the effect output, and `0x90`
  is a fixed 0..0.8-range level in every effect that has it. **MEASURED (cell) / INFERRED
  (reader position).**
* **PARAMETRIC EQ `op70` coeff `{00,06,0C,12,18}`** — read by the **6-word coefficient
  cursor**, one band each; state `{64,68,6C,70,74}` read by the **`+4` pointer walk**.
  **MEASURED, 5/5** (§Headline 1).

## 5. Honest limits — what the chain does NOT settle

* **Scalar parameters do not pin a reader by coincidence.** For a single-cell control
  (THRESHOLD, VOLUME) the body touches ~15 cells and the origin is free over 256 values,
  so a lone body-read/host-write coincidence is not significant. The chain is diagnostic
  **only where the parameter set has geometric structure** (EQ bands stride 4/6, delay
  taps, reverb banks) — exactly the biquad's 5/5. This is itself a result: the lever
  works on *arrays*, not on scalars, until the absolute origin is pinned (`-addressing.md`
  §6 item 1).
* **The name↔cell alignment is INFERRED** except for the family-pinned parameters (LFO,
  biquad bands, the universal tail, compressor attack/release). Record order ≠ UI order.
* **VOLUME vs REV SEND** — both are 0..0.8 tail levels at `0x90`/`0x06`; which name is
  which is not forced by ordering alone.
* **No comparator instruction** was found (§3), and none is expected to exist.

## 6. Coverage

**No new full-word decode**, so honest source coverage is **unchanged at 18.3 %
(545/2974)** — counting a validated reader-role or an operand-meaning as a full word
decode would be the over-claim this series refuses. What changed:

* Words that **gained an operand MEANING** this pass: the `C40` envelope-detector family
  (coefficient = attack/release time constant, in the compressor context) and, confirmed
  as *readers* from the parameter side, `082` (LFO controls) and the `op21/op63` tail
  cells `0x90/0x06`. That is one family newly given an operand meaning and three
  reader-role confirmations of already-annotated words.
* One clean **negative**: no comparator opcode exists (present-AND-absence over the corpus).
* One new **artifact**: the per-effect NAMED-parameter → host-cell binding table (38
  effects), regenerable from the tool.

## 7. What remains

1. **The absolute origin** (`-addressing.md` §6 item 1) — the one number that would turn
   every scalar-parameter reader from INFERRED into MEASURED. The chain is built and
   waiting for it.
2. **The delay-tap readers.** `DELAY L/R`, `DELAY 1‑4` map (MEASURED) to `0x26/0x28/…`
   via the ms→samples helper; those cells set DRAM tap lengths, and the `880.1.*` bracket
   words that read them are the reverb work's target — a structured (array) case where the
   chain should become diagnostic once the DRAM-address vs DRAM-data question
   (`-semantics.md` §5.2) is settled.
3. **The compressor gain law**, as an arithmetic function of THRESHOLD/RATIO/detected
   level — decodable only with the origin and a P/acc trace, not by static coincidence.
