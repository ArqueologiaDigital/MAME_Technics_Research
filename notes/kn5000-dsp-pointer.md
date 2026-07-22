# NEC uPD6383GF — the data pointer's ORIGIN, found by running the core

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.

Follows `kn5000-dsp-hi12.md`, which decoded `hi12` as a horizontal microword and then **ruled the
pointer origin out on static evidence**, closing with:

> **What would settle it, ranked by cost:**
> 1. Run the core for one sample period and watch the C-RAM/D-RAM address bus. […] The device
>    exists at `src/devices/cpu/upd6383/`; it is instantiated **disabled**. One number out.

This note does that. The instrument is `upd6383_device::write_pointer_trace()`, added to the MAME
device; the corpus-side reproduction is `tools/kn5000_dsp_pointer.py`.

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED** or **SPECULATIVE**.
§7 lists misses and falsifications, §8 what the instrument is blind to. **There is still no
audio, no sound interface, and the core is still instantiated DISABLED.**

Reproduce:

```
python3 tools/kn5000_dsp_pointer.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom
# and, from a booted KN5000, kn5000_dsp1_upload_ptrtrace.txt (written at exit)
```

---

## Headline

1. **★★★ THE ORIGIN IS IN THE INSTRUCTION STREAM AFTER ALL — 83 WORDS EARLIER THAN ANYBODY
   LOOKED.** `-hi12.md` §5.2's load-bearing sentence is *"words with `lo12 == 0x821` (`ldptr`) in
   the **38 body images**: 0"*. The corpus statistic "2974 words over 38 images" **excludes the
   common header (I-RAM 0..59) and the algorithm-change stub (60..82) by construction** — 83 words
   that every effect executes and that no search in this series has ever covered. They contain
   **fourteen** pointer-family loads, including three immediately before each unit's terminator:

   ```
       I-RAM 42  801.0.70.821    I-RAM 50  801.0.50.821
       I-RAM 43  801.0.6C.827    I-RAM 51  801.0.64.827
       I-RAM 44  801.0.25.825    I-RAM 52  801.0.25.825
       I-RAM 49  400.1.0E.000    I-RAM 59  400.1.0F.007     <- END, unit 0 / unit 1
   ```

   **MEASURED**, three ways: in the ROM record at `0x01E496`, in the archived cold-boot capture,
   and in the **live I-RAM of a booted KN5000** read back by the device. (§1)
2. **★★★ THE VERDICT: unit 0 origin `0x70`, unit 1 origin `0x50`, via the `0x821` register.**
   Three candidates come out of the header; one is falsified by construction and the survivors are
   separated by a host-map measurement. **`0x825` is dead**: it is loaded with the **same** value
   (`#$25`) in *both* unit segments, and both effect units are resident simultaneously
   (MEASURED, `-header.md` §0), so the two units' state would alias completely. Between `0x821`
   and `0x827`, the host writes its parameters through `0x821` (13 distinct addresses spanning
   `0x00..0xB2`) and through `0x825` (3 addresses), and **never once through `0x827`** — and a
   body has to read the parameters the host writes. **INFERRED (strong)**, `0x827` not excluded.
   (§3, §4)
3. **★★★ AND IT EXPLAINS WHY THE STATIC SEARCHES HAD TO FAIL.** `-hi12.md` §5.1 searched for a
   pointer that **returns** — net-zero over a program — because "the program runs once per sample;
   its state cells must be in the same place next sample". It found net deltas of `−87 … +1149`,
   zero in 0 of 38. That search was well posed and its negative result is now *explained*: the
   pointer does not return because **it is reloaded from the header every frame**. The premise
   was right and the conclusion drawn from its failure ("the origin leaves no mark in the
   instruction stream") was wrong. (§2)
4. **★★ A CONTROL-FLOW MODEL FALLS OUT, AND IT UNIFIES FOUR SEPARATELY-RECORDED FACTS.** The
   header's two segments each set one unit's pointers and end with that unit's index; the bodies
   end with the *same* index. Read as a per-frame dispatch it explains at once why bodies at 84
   always end `**.1.0E.**` and bodies at 200 `**.1.0F.**`, why the header has exactly two
   near-parallel segments, why the 2-deep stack is enough, and — the one that has cost this
   project the most time — **why two exhaustive bitfield scans never found a branch word carrying
   the entry addresses 84 or 200: the dispatch is by UNIT INDEX, not by an immediate.**
   **INFERRED (strong).** (§2)
5. **★★ IMPLEMENTING THE DECODE FALSIFIED ONE OF THE NOTES I WAS IMPLEMENTING, AND I REPORT IT
   FIRST.** `-hi12.md` §3 measured "bit 10 with bit 11 clear = END OF PROGRAM; 38 in 2974, one per
   image, zero elsewhere". The MAME core, run over the **resident** I-RAM, halted at **word 6**.
   The header carries that bit **fourteen** times in sixty words, only two of them terminators.
   The body result reproduces exactly; the *bit meaning* does not generalise off the corpus it was
   measured on. (§5)
6. **★★ THE PHASER'S SHARED CELL NOW HAS AN ADDRESS — AND ITS PARTNER MISSES.** `-axes.md` §2.4
   declined to name it (*"I am not claiming the cell's address"*). All twenty of algo 5's all-pass
   sections resolve to **one** absolute cell, `0x76`. **But** the modulator block that must *fill*
   that cell writes `0x7B` — off by 5, and by a *different* amount in each of the three phaser
   images, so it is not a register offset either. Under a correct model they must coincide. The
   origins cancel out of that comparison entirely, so **the miss is in the pointer-DELTA rule, not
   in the origin.** (§6)
7. **★ COVERAGE IS UNCHANGED AT 18.3 % (545/2974), AND SAYING SO IS THE POINT.** This pass decoded
   no new word. It bought a machine-state fact, a control-flow model and a falsification. Counting
   any of those as vocabulary would be the same over-claim `-axes.md` §6.1 and `-hi12.md` §6 both
   refused. (§9)

---

## 1. THE CENSUS — where the loads actually are (**MEASURED**)

`tools/kn5000_dsp_pointer.py` §1, over the ROM:

```
   common header (I-RAM 0..59, 60 words):  11 pointer-family words
       15  C0A.2.92.820     29  C42.4.57.820     42  801.0.70.821   <- unit 0
       22  C04.3.12.820     31  C0A.4.B1.820     43  801.0.6C.827
       40  C4A.1.C0.820                          44  801.0.25.825
                                                 50  801.0.50.821   <- unit 1
                                                 51  801.0.64.827
                                                 52  801.0.25.825

   algo-change stub (I-RAM 60..82, 23 words):  3
       62  801.0.26.825     69  801.0.90.821     77  859.0.86.822

   the 38 body images (2974 words):
       hi12==0x801 & lo12==0x821 (ldptr)  : 0        <- -hi12.md sect. 5.2, reproduced
       any pointer-family lo12            : 0
```

The body figure is **`-hi12.md`'s own number, reproduced exactly** — which is the check that this
is the same corpus and that nothing has been quietly redefined. The bodies really do contain no
load. The header does.

**The same words are in the live machine.** A booted KN5000's I-RAM, read back through the device
and compared word for word against the static extraction, is **identical** across the header
(60/60), both effect bodies (`algo01` CHORUS at 84, the shared reverb image at 200), and the stub
except for **exactly** the two documented host patch slots at words 64 and 71, with **exactly**
the documented values. The acceptance test of `-core-draft.md` §3 is intact after every change in
this pass.

## 2. THE DISPATCH MODEL (**INFERRED**, strong)

```
       40  C4A.1.C0.820          50  801.0.50.821   <== LOAD POINTER 821 #$50
       41  400.A.00.21A          51  801.0.64.827   <== LOAD POINTER 827 #$64
       42  801.0.70.821   <==    52  801.0.25.825   <== LOAD POINTER 825 #$25
       43  801.0.6C.827   <==    53  010.9.D0.20C
       44  801.0.25.825   <==    54  800.1.60.00B
       45  010.A.00.20C          55  000.2.01.007
       46  800.1.60.00B          56  C64.6.A2.007
       47  800.8.0C.000          57  000.2.01.000
       48  C64.5.A2.000          58  000.1.8A.007
       49  400.1.0E.000   END/0  59  400.1.0F.007   END/1
```

Reading:

```
   I-RAM   0..39   common per-frame preamble
          40..49   set up unit 0's pointers, then END/unit 0   ->  body at  84
          84..     unit-0 effect body, ends  xxx.1.0E.000      ->  back to 50
          50..59   set up unit 1's pointers, then END/unit 1   ->  body at 200
         200..     unit-1 effect body, ends  612.1.0F.000      ->  frame done
```

This is a *reading*, not a measurement, and it is offered because of how much it makes cohere:

| separately-recorded fact | source | what the model does with it |
|---|---|---|
| bodies at 84 end with unit index `0x0E`, at 200 with `0x0F` | `-encoding.md` §7, MEASURED | the body returns to the segment that dispatched it |
| the header is exactly two near-parallel 10-word segments, one per unit | `-header.md` §2, MEASURED | they are the two dispatch sites |
| **no branch word carrying 84 or 200 exists** — two exhaustive bitfield scans | `-necfamily.md` §6, MEASURED | there is none to find: the dispatch is **by unit index** |
| the stack is **two** deep | CDJ-500 block diagram | one level is all a segment→body→segment call needs |
| the effect bodies are hand-unrolled with no loop | `-necfamily.md` §6, MEASURED | consistent: control lives in the header, not in the bodies |

**It also retires the premise that made §5.1 of `-hi12.md` search for a returning pointer.** The
state cells do have to be in the same place next sample — and they are, because the header puts
the pointer back. Net delta over a body is then free to be anything, which is exactly what was
measured (`−87 … +1149`, zero in 0 of 38). A negative result that is now *explained* rather than
merely recorded.

## 3. THE THREE CANDIDATES, AND THE ONE THAT DIES BY CONSTRUCTION

```
   unit 0   lo12 821 -> #$70     lo12 827 -> #$6C     lo12 825 -> #$25
   unit 1   lo12 821 -> #$50     lo12 827 -> #$64     lo12 825 -> #$25
```

> **`0x825` FALSIFIED as the body operand pointer (PROVEN BY CONSTRUCTION).** It holds `#$25` in
> *both* unit segments. Both effect units are resident and running in the same frame (MEASURED,
> `-header.md` §0: the regions 84..199 and 200..333 do not overlap and both are loaded). If the
> bodies walked `0x825`, unit 0 and unit 1 would address the identical state cells. It is a
> plausible **coefficient/parameter-bank** pointer — the host's `0x825` pokes cluster at
> `0x00/0x1E/0x26`, right where the header and stub set it — and that is what it is recorded as.

### The D-RAM extent test, which does NOT separate the survivors (**MEASURED, reported as a
negative**)

D-RAM is 256×24, so a body's walk offset by the true origin should lie inside `0..255`.

```
   pointer-delta rule "classes {2,A} move the pointer":
     unit 0 (37 images):  origin #$70  in-range 30/37   extent  -21 .. 246
                          origin #$6C  in-range 30/37   extent  -25 .. 242
                          origin #$25  in-range 26/37   extent  -96 .. 171
     unit 1  (1 image ):  every candidate 0/1
```

`0x70` and `0x827`'s `0x6C` are four apart and score identically; `0x25` is mildly worse. **Unit 1
fails outright under every one of the 512 class subsets** — the reverb's walk leaves any 256-cell
window no matter which classes are credited with a delta. That is not evidence against the
origins; it is evidence that **the delta rule is wrong** (§6).

## 4. WHAT SEPARATES `0x821` FROM `0x827`: the host map (**MEASURED**)

Splitting the archived cold-boot uC-IF stream by target region — I-RAM ≥ 352 is the host **poke**
window (`-header.md` §0) — the pointer loads sort like this:

```
   resident I-RAM (< 352)   lo12 821 -> {50, 70, 90}
                            lo12 825 -> {25, 26}
                            lo12 827 -> {64, 6C}

   host poke slots (>=352)  lo12 821 -> {00,09,0A,50,6E,8C,90,97,9E,A6,AC,AE,B2}   13
                            lo12 825 -> {00,1E,26}                                  3
                            lo12 827 -> NONE                                        0
```

The host writes effect **parameters**; a body must **read** them. The host writes through `0x821`
and `0x825` and never once through `0x827`; `0x821`'s poke addresses span `0x00..0xB2`, the range
the header's own `0x821` values sit in, and `0x50` appears in both lists.

> **ASSIGNED (INFERRED, strong): the body's operand pointer is the `0x821` register.**
> **Unit 0 origin `0x70`. Unit 1 origin `0x50`.**
> `0x827` is the runner-up and is **not** excluded — it is a real pointer the header sets per
> unit, it is simply never a host-write target in this capture, and one cold boot is one sample.

## 5. ★ THE FALSIFICATION THE INTERPRETER FOUND

Implementing a paper decode is a strong test of it, and this time it failed one.

```
   bit 10 set, bit 11 clear:
       38 body images (2974 words) :  38   one per image, all final, none elsewhere
       common header   (60 words)  :  14   at I-RAM 6 11 14 19 21 23 24 28 33 36 39 41 49 59
                                           -- only 49 and 59 are unit-index terminators
       algo-change stub (23 words) :   0
```

The core, started at I-RAM 0 over the *resident* image, halted at **word 6** (`400.A.00.419`).

> **UPHELD**: within an effect body, bit 10 predicts "final word" with no exceptions in 2974
> words, and the residue-closure argument of `-hi12.md` §3.2 is untouched.
> **FALSIFIED as stated**: "bit 10 (bit 11 clear) = END OF PROGRAM" is not a property of the bit.
> Twelve interior occurrences in sixty header words is 20 % of the header.

The reading that survives both is **"end of segment / return"**, with the header a chain of about
fourteen short segments — which is independently what §2's dispatch model needs, and it is why
the two facts are reported together. **SPECULATIVE.**

**What the core does about it, and why.** It applies strip-and-halt only to the form the 38
measurements are actually of — bit 10 with `class4 == 1` and `addr8 ∈ {0x0E, 0x0F}` — and traps
every other bit-10 word. Extrapolating a bit meaning past its evidence is how a draft core starts
producing plausible-but-wrong results, which is the failure mode this whole device exists to
avoid.

## 6. ★ THE PHASER: a hit and a miss, both from the same walk

Running the walk from the origins in §4:

```
   algo  5  origin #$70 :  chain READS {76}                 modulator WRITES {7B}
   algo 68  origin #$70 :  chain READS {76}                 modulator WRITES {77}
   algo  3  origin #$70 :  chain READS {7E,7F}              modulator WRITES {7B,7C}
```

**HIT.** `-axes.md` §2.2 measured that the phaser's twenty three-word all-pass sections have
`addr8` deltas cancelling to exactly zero, so they *share one operand cell* — a statement about
differences, deliberately origin-free. With an origin, that cell has an **address**: `0x76`, and
all twenty sections agree. Falsifier 1 is not merely reproduced, it is *upgraded*. (The other two
falsifiers — the biquad's `+4` per-band walk and the reverb diffuser's stationary pointer — are
likewise pure differences and are reproduced unchanged by `tools/kn5000_dsp_pointer.py` §4: 30
sections net-zero with the 8 chain-terminal exceptions, and 8 of 9 reverb diffusers stationary.)

**MISS, and it is the more informative half.** The `212.A.**.1D5` block that `-axes.md` §2.4
identifies as the writer that *fills* the shared cell lands on `0x7B`, not `0x76`. The
discrepancy is **not constant across images** (write − read = +5 in algo 5, +1 in algo 68,
−3 in algo 3), so it is not a fixed inter-register
offset. Under any correct model the writer and the reader must name the same cell.

Both addresses are `origin + Σ(deltas)`, so **the origin cancels out of the comparison entirely.**
The error is in the Σ — in which words carry a pointer delta. That is the same thing the unit-1
extent failure says (§3), from an unrelated effect family. Two independent measurements agreeing
on where the remaining error is, is the most useful thing in this note after the origin itself.

## 7. Corrections, misses, and falsifications

| earlier claim | source | status here |
|---|---|---|
| "the origin cannot be pinned from the ROM alone"; "the pointer is reset at program start to a per-unit base **that the instruction stream never names**" | `-hi12.md` §5.4 | **FALSIFIED.** The instruction stream names it, in the common header, which every static search excluded by construction (§1) |
| `801.0.NN.821` is "a *host-poke* word, absent from every effect body" | `-hi12.md` §5.2 | **HALF UPHELD.** Absent from every body: reproduced exactly. "Host-poke word": incomplete — it is *also* a resident header word, and that is the one that matters |
| the pointer must **return** over one program pass | `-hi12.md` §5.1 | **PREMISE RETIRED.** It is *reloaded*, not returned; the −87…+1149 spread is expected, not anomalous (§2) |
| bit 10 (bit 11 clear) = END OF PROGRAM | `-hi12.md` §3 | **UPHELD in the bodies (38/38), FALSIFIED as a bit meaning** (14 header occurrences, 12 interior) (§5) |
| `400.1.0E/0F.000` counted as 7 fully-decoded words | `-hi12.md` §6 | **WEAKENED, not withdrawn.** Still fully decoded *as* "segment end, unit N" within a body; "end of PROGRAM" is no longer the justification |
| channel bases `0x40`/`0x54` are origin-relative and not an anchor | `-hi12.md` §5.3 | **UPHELD**, and now resolvable: under origin `0x70` they are absolute `0xB0`/`0xC4`, two contiguous `0x14` blocks. Contingent on the delta rule, so **not** claimed |
| "I am not claiming the cell's address" (the phaser's shared gain) | `-axes.md` §2.4 | **CLAIMED, as `0x76`** (INFERRED) — with the writer/reader mismatch reported alongside it (§6) |
| the D-RAM extent would discriminate the candidates | *this note's own plan* | **MISSED.** It does not separate `0x821` from `0x827` and unit 1 fails under every class subset (§3) |
| coverage 18.3 % | `-hi12.md` §6 | **UNCHANGED**, deliberately (§9) |

## 8. What this instrument is blind to

1. **The trace is not execution of the machine.** The core is disabled; `write_pointer_trace()`
   walks the resident I-RAM under the decoded subset. It reads a *real* I-RAM filled by the *real*
   host, which is why it found the header — but no undecoded word is being executed, so no value
   in C-RAM or D-RAM means anything yet.
2. **The pointer-delta rule is not established, and it is the binding constraint.** Everything in
   §3 and §6 that involves Σ(deltas) inherits it. `addr8` is a signed post-increment (MEASURED)
   and classes 1/3/5/6/8 provably do not carry one; which of the rest do is open, and §6 shows the
   current guess is wrong.
3. **One cold boot is one sample.** The host-map asymmetry in §4 rests on a single capture in a
   single machine state, loading CHORUS and the reverb. A capture with the phaser active could
   overturn it — which is exactly the experiment in §10.
4. **Which pointer register is which is still unknown.** The chip has six (CP/DP/BP1/BP2/PR1/PR2).
   This note names the `lo12` *forms* `0x821`/`0x825`/`0x827` and their loaded values; it does not
   say which architectural register any of them is.
5. **`0x820` and `0x822` were not analysed.** Five of the fourteen header/stub pointer-family words
   use `lo12 = 0x820` inside the bit-11 escape (`C0A/C04/C42/C4A`), where `class4` is immediate
   data rather than a class, and one (stub word 77, `859.0.86.822`) uses `0x822`. They may not be pointer loads at all.
6. **The dispatch model has no falsifier yet.** §2 is chosen for coherence over five facts, not
   demonstrated. A capture showing a body being entered without its header segment running first
   would kill it.
7. **Only IC311.** DSP2 (MN19413, IC310) has a different word size and none of this transfers.

## 9. COVERAGE, HONESTLY: 18.3 %, UNCHANGED

```
   words over the 38 distinct images  : 2974
   the six MAME forms                 :  267   ( 9.0 %)   <- -core-draft.md
   -axes.md baseline                  :  520   (17.5 %)
   -hi12.md revised                   :  545   (18.3 %)
   ★ after this pass                  :  545   (18.3 %)
```

Recomputed the same scoped way, by the same tool (`tools/kn5000_dsp_hi12.py coverage`). **This
pass decoded no new word**, and nothing here is counted as one:

* the **origin** is a machine-state fact, not a word decode;
* the **dispatch model** is control flow, not vocabulary;
* the **bit-10 falsification** *removes* confidence rather than adding coverage;
* the 680 bit-4 words remain uncounted, per `-hi12.md` §6.

The structural result — a pointer that is now an address — is worth far more than a coverage
point, and the way to keep that true is to not launder it into one.

## 10. What is next, and what would separate the two survivors

1. **★ THE EXPERIMENT THAT SEPARATES `0x821` FROM `0x827`, and it needs no new tooling.** Select
   **PHASER** on a running KN5000 and capture the uC-IF stream. The phaser's shared gain is a
   host-swept parameter (`0x381062 = +0.438` swept by ±0.025, `-axes.md` §2.4), so the host **must**
   poke the cell the chain reads.
   * **Prediction**: the poke is a `801.0.NN.821` word, i.e. the parameter arrives through the
     `0x821` register — confirming §4 on an effect that actually exercises the cell.
   * **The address is a second, independent read on the delta rule**: `0x76` is what the current
     Σ predicts under origin `0x70`. If the host pokes `0x76`, the delta rule is right for the
     phaser and §6's miss is localised to the modulator block. If it pokes something else, the
     difference measures the delta rule's error directly, at a known point.
   * If it pokes through `0x827`, §4 is wrong and `0x827` is the operand pointer.
2. **Fix the pointer-delta rule.** It is now the single binding unknown (§8 item 2), and §6 gives
   it a *labelled* target for the first time: two words, in three images, whose computed addresses
   must be made equal. That is a far better-posed problem than "which classes move the pointer".
3. **Disassemble the header properly.** Fourteen bit-10 words, fourteen pointer-family loads,
   and about 90 % of its vocabulary appears in no effect body (`-encoding.md` ADDENDUM). It is
   where `COND`, `BRAKST`, LC1–LC3 and the GF flags must live, it is now known to be the control
   layer rather than preamble, and it is sitting in a real I-RAM at words 0..82. **This is the
   highest-value remaining static target and this note is the reason.**
4. The datasheet (`-INDEX.md` backlog 6).
