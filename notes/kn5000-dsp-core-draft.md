# NEC uPD6383GF — a MAME device and disassembler, and the undecoded-word worklist

KN5000 IC311 effects DSP. Date: 2026-07-22.
Files: `src/devices/cpu/upd6383/upd6383d.{cpp,h}` (disassembler),
`src/devices/cpu/upd6383/upd6383.{cpp,h}` (device), instantiated by
`src/mame/matsushita/kn5000.cpp` as `:dsp1` (IC311).

**This is a DRAFT / RESEARCH INSTRUMENT, not a working core.** The instruction set is not
decoded. Six word forms are implemented, every other word is trapped and logged, and there is
**no sound interface and no audio** — a partially-correct effects DSP produces audio that
*diverges*, and plausible-but-wrong sound is worse than silence (the KN7000 lesson). The core
is instantiated in the KN5000 machine config but is instantiated **disabled**: the host
interface is exercised, nothing executes.

Companions: `kn5000-dsp-INDEX.md` (start there), `-encoding.md` (the field map),
`-header.md` (the I-RAM map and the host patch slots), `-semantics.md` (the solved biquad),
`-cursor-general.md`, `-class2-round2.md`, `-effect-map.md`.

---

## 1. What is implemented, and what is trapped

Six forms carry a real mnemonic. Each one's evidence is quoted in the source next to the code
that implements it; nothing else is given a mnemonic, on purpose.

| form | mnemonic | status |
|---|---|---|
| `000.2.00.000` | `nop` | **PROVEN BY CONSTRUCTION** — sub-CPU writer `LABEL_038922` emits this bit pattern, setting the `class4` nibble to 2 explicitly |
| `801.0.NN.821` | `ldptr #$NN` | **PROVEN BY CONSTRUCTION** — the firmware assembles these bytes at sub-CPU `LABEL_0387E6`; in the poke region it always opens a burst of 1..30 data words |
| `801.0.00.021` | `rstcur` | **VERIFIED** — algo39's class-A count at its ten section starts runs 0,6,12,18,24 \| reset \| 0,6,12,18,24 |
| `202.A.dd.1D5` | `mac (p)+dd` | **DETERMINED** — all 144 survivors of the 19,674,720-point search agree (`-semantics.md` §3.1) |
| `202.A.dd.1D4` | `mac.lb (p)+dd` | **DETERMINED**, same source (additionally latches B) |
| `212.A.dd.407` | `mulst (p)+dd` | **DETERMINED UNIQUELY**, no residual freedom: `mem[p] <- acc ; P = coef[cursor++] * acc` |

Everything else is emitted as `?word 0x0XXXXXXXXX` with the field breakdown, and — where the
corpus has a MEASURED structural landmark — an annotation in brackets that says what the word
*marks* while making clear that what it *does* is unknown: the terminator (with its unit
index), the external-DRAM bracket, the all-pass marker, the LFO read, the envelope detector,
class 8, the carry-latch reads, the P-consumers, the table-lookup idiom, and the two families
where `class4` is immediate data rather than a class. Landmarks deliberately keep the `?`
prefix: an annotation is not a decode, and the `?` is what makes the worklist greppable.

Deliberately NOT decoded although the notes discuss them: `lo12 = 0x820/0x825/0x827` (INFERRED
pointer-load siblings — inferring the family is not knowing which register each loads); the
biquad words `[0] [1] [5] [8]`, whose readings the search left constrained-to-two and which are
broken only by an encoding argument; class 8; the terminator.

The device executes exactly those six forms and traps everything else **without changing any
state**, logging `(word, PC, I-RAM word index, program id, cursor, dp, acc)` once per distinct
word plus a full histogram at exit.

## 2. It builds, it validates, and the KN5000 still boots

* `./build.sh` — clean build.
* `-validate kn5000` → exit 0. `-validate kn7000` → exit 0.
* KN5000 boots to its **main play screen** (verified from a snapshot, not from logs), both
  before and after the `kn5000_dsp1_device` dissolution, with a byte-identical I-RAM:
  `PMEM: 1-`, `16 Beat 1`, `♩=120`, RIGHT1 Piano / RIGHT2 Bigband Brass / LEFT Modern E.P.1.
  Unchanged from before the wiring, which is what "instantiated disabled" is for.

## 3. ★ The acceptance test: live I-RAM vs the static extraction

After a cold boot the core's I-RAM was dumped and compared byte for byte against what
`tools/kn5000_dsp_extract.py` pulls out of the Sub CPU ROM.

```
   I-RAM  0.. 59   common header          IDENTICAL to the ROM stream at 0x01E496
   I-RAM 60.. 82   algorithm-change stub  identical EXCEPT words 64 and 71 (see below)
   I-RAM 83        never written          zero
   I-RAM 84..153   effect unit 0          IDENTICAL to algo01.bin (CHORUS, 70 words)
   I-RAM 200..332  effect unit 1          IDENTICAL to algo16..27's shared image (133 words,
                                          the reverb -- the only unit-1 program in the corpus)
   I-RAM 352..382  host poke slots        written
```

The two stub words that differ are **exactly** the two host patch slots the header note
identifies, and they differ to **exactly** the values it records:

```
   word 64   ROM 001190E445   ->   live 0C40A80445   ( 011.9.0E.445 -> C40.A.80.445 )
   word 71   ROM 001190F446   ->   live 0C41900446   ( 011.9.0F.446 -> C41.9.00.446 )
```

Both are listed verbatim in `kn5000-dsp-header.md` §4 as observed patched values, with the
invariant `lo12` (`445`/`446`) that identified them. So the live wiring reproduces the paper
analysis **including its exceptions** — the strongest available check that the upload decode
(command 0x01, 16-bit big-endian word address, 5-byte words) is right.

Boot-time load sequence: **54 transfers, 3331 payload bytes**, matching the capture already on
record (`notes/data/kn5000_dsp1_upload_coldboot.txt`); every command-0x01 payload is 2 bytes
plus an exact multiple of 5.

## 4. The worklist — undecoded words by frequency

Produced by running the real disassembler over the corpus:

```
python3 tools/kn5000_dsp_extract.py <subprogram rom> <scratch>/progs     # 96 images
g++ ... -o <scratch>/dasmharness tools/kn5000_dsp_dasm_harness.cpp      # recipe in that file
python3 tools/kn5000_dsp_dasm_report.py <scratch>
```

`tools/kn5000_dsp_dasm_harness.cpp` drives the **real MAME disassembler object**; in a full
MAME build `unidasm -arch upd6383 <image>` does the same thing (build.sh registers the arch),
but a FOCUSED build does not produce unidasm, hence the harness.

Scope: the **38 distinct images** of the 91 valid programs (the 5 malformed streams — algos 79,
88, 89, 90, 91, which do not end with the terminator — are excluded, reproducing the corpus
statistics of `-encoding.md` exactly: 91 programs, 38 images, 2974 words).

```
   words over the 38 distinct images   2974
   decoded                              267   (9.0 %)
   undecoded                           2707   (91.0 %)
   distinct undecoded words             655
   distinct undecoded (hi12,class4,lo12) FAMILIES   185
```

**Read the coverage honestly: 9 % is the whole point of the exercise.** Six decoded forms out
of a 655-word vocabulary is where the paper analysis actually stands once you are forced to
execute it.

### 4.1 Top 40 undecoded words

| rank | word | fields | n | % of undecoded | cum % | images | annotation |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | `0x0212200000` | `212.2.00.000` | 88 | 3.3% | 3.3% | 29 |  |
| 2 | `0x0000A00415` | `000.A.00.415` | 76 | 2.8% | 6.1% | 21 |  |
| 3 | `0x00822001C0` | `082.2.00.1C0` | 64 | 2.4% | 8.4% | 18 | LFO read (INFERRED) |
| 4 | `0x00124011CE` | `012.4.01.1CE` | 53 | 2.0% | 10.4% | 25 | table-lookup idiom, third word (INFERRED) |
| 5 | `0x000020040E` | `000.2.00.40E` | 52 | 1.9% | 12.3% | 25 |  |
| 6 | `0x0040000C63` | `040.0.00.C63` | 46 | 1.7% | 14.0% | 25 |  |
| 7 | `0x08801202C7` | `880.1.20.2C7` | 40 | 1.5% | 15.5% | 15 | external-DRAM bracket CLOSE (INFERRED) |
| 8 | `0x0A00000041` | `A00.0.00.041` | 35 | 1.3% | 16.8% | 13 | hi12[11:8]==A: host-poke data form, bits [23:12] are immediate |
| 9 | `0x01022FF687` | `102.2.FF.687` | 35 | 1.3% | 18.1% | 13 | P-consumer, stores latch B (INFERRED) |
| 10 | `0x0804816415` | `804.8.16.415` | 35 | 1.3% | 19.4% | 13 | class 8: post-sum step (rescale/round/saturate?), OPERATION UNKNOWN |
| 11 | `0x0102200000` | `102.2.00.000` | 34 | 1.3% | 20.6% | 19 |  |
| 12 | `0x0212A01412` | `212.A.01.412` | 34 | 1.3% | 21.9% | 12 |  |
| 13 | `0x0212201412` | `212.2.01.412` | 30 | 1.1% | 23.0% | 3 |  |
| 14 | `0x00002001D5` | `000.2.00.1D5` | 30 | 1.1% | 24.1% | 11 |  |
| 15 | `0x09001601D5` | `900.1.60.1D5` | 29 | 1.1% | 25.2% | 10 |  |
| 16 | `0x0C4032044C` | `C40.3.20.44C` | 29 | 1.1% | 26.2% | 10 | envelope detector (INFERRED) |
| 17 | `0x00006184CD` | `000.6.18.4CD` | 29 | 1.1% | 27.3% | 16 | table-lookup idiom, class-6 addr8 = table selector (INFERRED) |
| 18 | `0x0000A001D3` | `000.A.00.1D3` | 28 | 1.0% | 28.3% | 11 | read into carry latch A (INFERRED) |
| 19 | `0x0212200419` | `212.2.00.419` | 28 | 1.0% | 29.4% | 13 |  |
| 20 | `0x088012064B` | `880.1.20.64B` | 28 | 1.0% | 30.4% | 13 | external-DRAM bracket CLOSE (INFERRED) |
| 21 | `0x0094A00200` | `094.A.00.200` | 28 | 1.0% | 31.4% | 16 |  |
| 22 | `0x0092200700` | `092.2.00.700` | 28 | 1.0% | 32.5% | 16 |  |
| 23 | `0x002A200000` | `02A.2.00.000` | 28 | 1.0% | 33.5% | 15 |  |
| 24 | `0x0880160000` | `880.1.60.000` | 26 | 1.0% | 34.5% | 25 | external-DRAM bracket OPEN (INFERRED) |
| 25 | `0x0092A00200` | `092.A.00.200` | 24 | 0.9% | 35.4% | 14 |  |
| 26 | `0x08801602D9` | `880.1.60.2D9` | 23 | 0.8% | 36.2% | 11 | external-DRAM bracket OPEN (INFERRED) |
| 27 | `0x0104200000` | `104.2.00.000` | 23 | 0.8% | 37.1% | 5 | all-pass marker -- step UNKNOWN |
| 28 | `0x0000A001D5` | `000.A.00.1D5` | 22 | 0.8% | 37.9% | 11 |  |
| 29 | `0x01042001CE` | `104.2.00.1CE` | 22 | 0.8% | 38.7% | 12 |  |
| 30 | `0x0000200415` | `000.2.00.415` | 22 | 0.8% | 39.5% | 10 |  |
| 31 | `0x0202AF3415` | `202.A.F3.415` | 22 | 0.8% | 40.3% | 10 |  |
| 32 | `0x0182200407` | `182.2.00.407` | 21 | 0.8% | 41.1% | 12 |  |
| 33 | `0x0000201407` | `000.2.01.407` | 19 | 0.7% | 41.8% | 11 |  |
| 34 | `0x0202200000` | `202.2.00.000` | 18 | 0.7% | 42.4% | 11 |  |
| 35 | `0x0026200000` | `026.2.00.000` | 18 | 0.7% | 43.1% | 9 |  |
| 36 | `0x00002FE407` | `000.2.FE.407` | 18 | 0.7% | 43.8% | 13 |  |
| 37 | `0x0000A011D5` | `000.A.01.1D5` | 18 | 0.7% | 44.4% | 8 |  |
| 38 | `0x08801308BC` | `880.1.30.8BC` | 17 | 0.6% | 45.1% | 17 | framing word, carries no DRAM information (MEASURED) |
| 39 | `0x00006284CD` | `000.6.28.4CD` | 17 | 0.6% | 45.7% | 9 | table-lookup idiom, class-6 addr8 = table selector (INFERRED) |
| 40 | `0x0028200000` | `028.2.00.000` | 17 | 0.6% | 46.3% | 13 |  |
distinct undecoded FAMILIES (hi12,class4,lo12): 185

### 4.2 By family — `addr8` is an operand, so the family is the real unit of work

`addr8` is a signed pointer post-increment (MEASURED), so grouping by
`(hi12, class4, lo12)` and treating `addr8` as data is the right granularity for a worklist.
185 families cover the 655 distinct words.

| rank | family | n | % | cum % | images |
|---:|---|---:|---:|---:|---:|
| 1 | `000.2.**.407` | 132 | 4.9% | 4.9% | 31 |
| 2 | `212.2.**.000` | 103 | 3.8% | 8.7% | 32 |
| 3 | `000.A.**.415` | 91 | 3.4% | 12.0% | 27 |
| 4 | `000.2.**.40E` | 77 | 2.8% | 14.9% | 37 |
| 5 | `082.2.**.1C0` | 64 | 2.4% | 17.3% | 18 |
| 6 | `104.2.**.1CE` | 57 | 2.1% | 19.4% | 27 |
| 7 | `012.4.**.1CE` | 53 | 2.0% | 21.3% | 25 |
| 8 | `000.A.**.1D5` | 53 | 2.0% | 23.3% | 22 |
| 9 | `000.2.**.1CD` | 49 | 1.8% | 25.1% | 28 |
| 10 | `092.2.**.700` | 46 | 1.7% | 26.8% | 25 |
| 11 | `040.0.**.C63` | 46 | 1.7% | 28.5% | 25 |
| 12 | `000.6.**.4CD` | 46 | 1.7% | 30.2% | 25 |
| 13 | `104.2.**.1D5` | 46 | 1.7% | 31.9% | 8 |
| 14 | `102.2.**.1CD` | 43 | 1.6% | 33.5% | 7 |
| 15 | `102.2.**.000` | 42 | 1.6% | 35.0% | 21 |
| 16 | `212.A.**.412` | 42 | 1.6% | 36.6% | 15 |
| 17 | `202.A.**.415` | 42 | 1.6% | 38.1% | 13 |
| 18 | `102.A.**.4C8` | 41 | 1.5% | 39.6% | 14 |
| 19 | `000.2.**.000` | 40 | 1.5% | 41.1% | 24 |
| 20 | `880.1.**.2C7` | 40 | 1.5% | 42.6% | 15 |
| 21 | `880.1.**.000` | 38 | 1.4% | 44.0% | 31 |
| 22 | `000.2.**.1D5` | 38 | 1.4% | 45.4% | 13 |
| 23 | `000.2.**.647` | 38 | 1.4% | 46.8% | 15 |
| 24 | `012.2.**.1C0` | 35 | 1.3% | 48.1% | 19 |
| 25 | `A00.0.**.041` | 35 | 1.3% | 49.4% | 13 |
| 26 | `212.A.**.1D5` | 35 | 1.3% | 50.7% | 20 |
| 27 | `102.2.**.687` | 35 | 1.3% | 52.0% | 13 |
| 28 | `804.8.**.415` | 35 | 1.3% | 53.3% | 13 |
| 29 | `000.2.**.447` | 34 | 1.3% | 54.5% | 21 |
| 30 | `182.2.**.000` | 32 | 1.2% | 55.7% | 16 |

### 4.3 What the ranking says, in plain terms

* **There is no small set of six words that unblocks everything.** The top 40 *words* are 46 %
  of undecoded occurrences and the top 29 *families* are 55 %; the distribution has a long
  tail of 185 families. Anyone hoping the answer is "these six words are 80 % of what we cannot
  execute" should stop hoping — this measurement says the opposite, and that is a result.
* **The single highest-value target is `212.2.**.000` (103 occurrences, 32 of 38 images)** and
  its relatives `212.2.**.412` / `212.A.**.412` / `212.A.**.1D5`. `hi12 = 0x212` is the one
  family the constraint search **determined** in its class-A form (`212.A.**.407` = write the
  accumulator and multiply by it), and `-semantics.md` §3.2 reads it as "write the operand into
  `mem[ptr]` and multiply by it". The class-2 twin appears in nearly every image. Decoding what
  bit 23 removes from a word whose class-A form is known is the cheapest real gain available,
  and `-class2-round2.md` §1.4 already supplies the minimal pair (the phaser's ninth section).
* **`000.2.**.407` (132, 31 images) and `000.2.**.40E` (77, 37 images) are the most universal
  undecoded families in the corpus** — `40E` appears in 37 of 38 images. Whatever they are,
  they are housekeeping, and no note currently has a positional argument for either.
* **`000.A.**.415` / `202.A.**.415` / `804.8.**.415` (91 + 42 + 35).** The `lo12 = 0x415` group
  spans class A, class 2 and class 8 and includes `804.8.16.415`, the class-8 word whose
  *position* is determined and whose *operation* is not. A single `lo12` value shared across
  three classes is a strong hint that `lo12` carries the destination/route while the class
  carries the arithmetic — testable against the existing corpus, and not yet tested.
* **The all-pass and DRAM landmarks are already annotated but still undecoded**
  (`104.2.**.1CE` 57, `104.2.**.1D5` 46, `880.1.**.2C7` 40, `880.1.**.000` 38). These are the
  words the reverb work needs, and `-semantics.md` §5.2 states precisely what is missing:
  whether `880.1.20.*` latches the write *address* or the *data*.
* **`082.2.**.1C0` (64, 18 images) = the LFO read** and **`040.0.**.C63` + `000.6.**.4CD` +
  `012.4.**.1CE` = the 3-word table-lookup idiom** (46 + 46 + 53, all 25 images). The idiom is
  identified as an idiom with MCC +1.000 but not one of its three words is decoded; it is the
  largest *self-contained* undecoded unit in the corpus and probably the best-posed one.

## 5. Did the implementation contradict the notes?

Implementing a paper decode is a strong test of it. Everything checked out; the specific
findings are:

1. **No contradiction was found.** Every form implemented from the notes was implementable
   exactly as written, and the biquad section renders in the disassembly precisely as
   `-semantics.md` §3.3 lays it out — the nine-word section is visible ten times in algo39,
   with `mac / mac.lb / mac / ?687 / ?class-8 / mulst / ?647` in the stated order.
2. **The live wiring re-verified two paper results at once** (§3): the ROM-derived header,
   stub and both effect bodies land byte-identically in a real I-RAM, and the only two
   deviations are the documented host patch slots with the documented values.
3. **A nuance worth recording about `class4`.** `-header.md` §6 shows `class4` is immediate
   data inside the `hi12[11:8]==0xC` family and in the host-poke form, while `-encoding.md` §5
   treats it as a class field. Both are right about their own population, but a disassembler
   has to choose per word: this one keeps the field split for display and *annotates* the two
   families where the nibble is data. Anyone extending it must not treat `class4` as a class in
   those families.
4. **`opcode_alignment()` had to be 1, not 5.** The instruction word is 5 bytes and PC is
   counted in bytes throughout (including in the device's I-RAM space, modelled as 384 x 5
   bytes). This is a modelling choice, not a hardware claim, and it is what lets one
   disassembler serve both the device and `unidasm -arch upd6383`.
5. **Nothing was learned that changes the biquad result, because nothing could be**: with the
   core disabled, no instruction has been executed on real data yet. The interpreter evidence
   in `-semantics.md` §4 remains the only dynamic test of the decode, and it is a Python one.

## 6. Next, in order of value

1. **`212.2` vs `212.A`** — bit 23 on a family whose class-A form is determined. Highest
   frequency, existing minimal pair, no new data needed.
2. **The `lo12 = 0x415` group across classes A/2/8** — would test "lo12 = route, class4 =
   arithmetic" and would come with `804.8.16.415`, i.e. class 8, as a bonus.
3. **The table-lookup triple** `040.0.**.C63 / 000.6.**.4CD / 012.4.**.1CE` — one self-contained
   idiom, 25 images, MCC +1.000, three undecoded words.
4. **`880.1.20.*`: address latch or data latch?** — the one place where the reverb reading in
   `-semantics.md` §5.2 is admittedly incomplete.
5. **The 83 header+stub words**, per the ADDENDUM to `-encoding.md`: ~90 % of their vocabulary
   appears in no effect body, and they are where LC1-LC3, `COND`, `BRAKST` and the GF flags
   must live. They are now in a real I-RAM at word 0..82 and can be disassembled from there.
