# NEC uPD6383GF — THE PER-FRAME EXECUTION TRACE (what actually runs, in order)

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-26.
Task: *"which instructions would actually execute"* — the concrete, ordered, per-sample-frame
instruction list for the audio path, and a decoding roadmap ranked by **what blocks audio**
rather than by corpus frequency.

Reproduce:

```
# 1. capture the real microcode from the running machine (12 emulated seconds is enough)
cd <scratch>; ./kn7000 kn5000 -rompath ./roms -skip_gameinfo -window -nomaximize \
    -nothrottle -str 12 -nvram_directory ./nvram      # writes kn5000_dsp1_upload.{txt,bin}

# 2. build the frame traces
python3 tools/kn5000_dsp_perframe.py kn5000_dsp1_upload.txt \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom [--sets]
python3 tools/kn5000_dsp_perframe.py kn5000_dsp1_upload.txt <rom> --algo 0 --md   # the table
```

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED**, **SPECULATIVE** or
**FALSIFIED**. §6 is predict-then-check, misses and corrections; §7 is what this instrument is
blind to. **No audio path was added, the core is still instantiated DISABLED
(`kn5000.cpp:1147`, `set_disable()`), the driver was not touched and the disassembler was not
edited.**

---

## Headline

1. **★★★ THE FRAME IS 256–326 INSTRUCTION SLOTS, AND EVERY WORD ON IT EXECUTES EXACTLY ONCE.**
   No loop, no branch, no repeat: the bodies are hand-unrolled and the PC is restarted by the
   sample clock. The through / no-effect frame is **265 words**; the cold-boot default
   (CHORUS + reverb) is **286**; PARAMETRIC EQ is **321**; the corpus minimum is **256**
   (COMPRESSOR) and the maximum **326**. (§1, §3)
2. **★★★ THE CORPUS DENOMINATOR IS THE WRONG ONE. THE AUDIO PATH IS THE 83 WORDS EVERY PREVIOUS
   STATISTIC EXCLUDED.** Of the 83 resident scaffolding words (header 0..59 + epilogue 60..82)
   that run in *every* frame of *every* effect, **75 distinct families, of which 65 never occur
   anywhere in the 2974-word body corpus**, and **3 words** are decoded. Whatever carries audio
   in and out of this chip lives almost entirely in a region no corpus statistic has ever
   measured. (§4.1)
3. **★★ THE REVERB BODY IS ON THE PATH IN EVERY FRAME OF EVERY EFFECT.** Over all 100 algorithm
   streams in the Sub CPU ROM there is **exactly one** image that loads at I-RAM 200 (133 words,
   algos 16..27 = all 12 reverb presets). Effect selection changes the unit-**0** body and the
   coefficients; unit 1 always runs the same 133 words. **MEASURED.** So the practical floor for
   "any correct sound" is scaffolding + reverb = **216 words, 104 families, 29 decoded**. (§3, §4)
4. **★★ THE `880.1.**` DELAY-DRAM FAMILY IS A TOP BLOCKER AND ITS CURRENT READING IS WRONG.**
   32–36 of every frame's words (≈13 %) are `hi12 = 0x880, class4 = 1`. The annotation calls
   `addr8 = 0x60` OPEN and `0x20` CLOSE, but per frame they are **16 vs 18** (through),
   **14 vs 20** (chorus), **13 vs 16** (EQ) — never balanced, and a bracket must balance over a
   cyclic frame. They are two *different* DRAM operations, not a matched pair. **MEASURED
   imbalance; the "bracket" reading is FALSIFIED as a bracket.** (§6.3)
5. **★★ `hi12 == 0xC40` IS NOT AN "ENVELOPE DETECTOR" — IT IS THE 12-BIT-IMMEDIATE FORMAT.** The
   collision `-headerdecode.md` §4.1 flagged is now resolved, and against the envelope reading:
   `0xC4_` words occur in **19 of 38** programs including the **reverb** (4×, which has no level
   detector), and 3 of the 4 host-patched **wet-level** words are `0xC40`. `hi12[11:8] == 0xC`
   is the already-MEASURED "bits [23:12] are a 12-bit immediate" format; the *operation* is in
   `lo12`. The disassembler's `hi12 == 0xC40 → envelope detector` rule fires **before** its own
   C-format rule and so mislabels every one of them. (§6.2)
6. **★★ TWO PER-FRAME-ONLY DEFECTS IN THE CURRENT MODEL, INVISIBLE TO THE CORPUS.**
   (a) The C-format rule and the cursor-advance rule (`class4 == 0xA`) contradict each other on
   exactly **0 of 2974** body words but on **2 of 265** frame words (I-RAM 64 patched, I-RAM 82);
   (b) the coefficient cursor must be re-based **at least twice per frame** (unit-0 bank `0x00`,
   unit-1 reverb bank `0x90` — both MEASURED) yet `rstcur` occurs in **1 of 38** programs and in
   **no** frame except PARAMETRIC EQ's. Something on the path re-bases the cursor and we cannot
   name it. (§5.2, §6.4)
7. **★ THE CYCLE BUDGET RETIRES THE "LOOP COUNT" READING OF THE `lo12 = 0x820` IMMEDIATES.**
   25 MHz / 44.1 kHz = **567 cycles per frame** against 256–326 words = **1.74–2.21 cycles per
   word**. The five header immediates are 448, 658, 786, 1111, 1201 — every one of them is
   larger than the entire frame budget, so none can be a per-frame loop count. As delay-line
   offsets they are 10.2, 14.9, 17.8, 25.2 and 27.2 ms at 44.1 kHz. (§6.5)

---

## 0. Provenance: the microcode is REAL and was captured today

`kn5000.cpp:1149` gives the device `set_capture_file("kn5000_dsp1_upload")`. A fresh cold boot
was run today (`-str 12`, isolated NVRAM, windowed) and produced **54 transfers / 3331 payload
bytes**, whose payload section is **byte-identical** to the archived
`notes/data/kn5000_dsp1_upload_coldboot.txt` (the only textual difference is the newer
`I-RAM[a..b]` annotation the device now prints). **MEASURED, positive control PASSES.**

What the cold boot actually loads, and in this order (from the capture):

| I-RAM | words | content |
|---:|---:|---|
| 60..82 | 23 | epilogue / stub |
| 0..59 | 60 | common header (uploaded 3×, byte-identical each time) |
| 64, 71 | 1+1 | the two host-patched words, repatched on every effect change |
| 200..332 | 133 | unit-1 body — matched byte-for-byte to ROM algos **16..27** (ROOM REVERB) |
| 84..153 | 70 | unit-0 body — matched byte-for-byte to ROM algo **1 (CHORUS)** |
| 352..382 | many | host poke slots (see §5.3) |

So **the cold-boot default effect pair is CHORUS (unit 0) + ROOM REVERB (unit 1)** — MEASURED,
and it is exactly the pair `-headerdecode.md` §3 used for its 286-slot prediction.

Bodies for the other programs come from the Sub CPU ROM pool (`tools/kn5000_dsp_extract.py`),
which has been verified byte-identical to live uploads in this and two earlier notes.

---

## 1. What executes in one sample frame

The model is not new; what is new is running it to the end and counting. Each step is already
established:

```
   Fs edge  ->  PC := 0                       hardware restart (Fs-RST / PC-RST pins)
     0 .. 48     common header, unit-0 preamble          <- the audio INPUT stage is at 0..11
        49       400.1.0E.000   CALL unit 0
                     84 .. 84+N-1   unit-0 body (straight line)
                     ...  .1.0E.xxx  RETURN
     50 .. 58     common header, unit-1 preamble
        59       400.1.0F.007   CALL unit 1
                     200 .. 332     unit-1 body = ROOM REVERB, 133 words
                     612.1.0F.000   RETURN
     60 .. 81     epilogue / OUTPUT stage   (64 and 71 are the host-patched return levels)
        82       C00.A.47.407   wait for the next Fs
```

Evidence, in one place:

* **the CALL at 49 and the RETURN into 50** — PROVEN BY CONSTRUCTION from register reuse: the
  header loads `0x821/0x827/0x825 <- #$70/#$6C/#$25` at I-RAM 42–44 and `#$50/#$64/#$25` at
  50–52, no body contains a pointer load (0 of 2974 words), so unit 0's body must run between
  44 and 50 (`-headerdecode.md` §2.1, `-pointer.md` §1).
* **fall-through, not branch, after an end-of-block word** — I-RAM 42–44 is reachable only by
  falling through I-RAM 41, which is an end-of-block word (`-headerdecode.md` §2.3).
* **no software frame loop** — the block at 60..82 contains no end-of-block word at all, and
  ends on `C00.A.47.407`, whose `hi12 = 0xC00` occurs **0 times** in 2974 body words
  (`-headerdecode.md` §1, §3).
* **no loops inside the bodies** — two exhaustive bitfield scans for a branch target are
  negative, and the bodies are demonstrably hand-unrolled (algo16 repeats 32 words at period 8
  varying only `addr8`; algo39 repeats at period 9) — `-necfamily.md` §6.
* **the 2-level stack** (CDJ-500 block diagram: STACK1/STACK2) is exactly deep enough for one
  call at a time and no more.

**Therefore every word on the path executes EXACTLY ONCE per frame.** The "times per frame"
column of the tables below is 1 for all 265 rows, which is why it is stated here instead of
printed 265 times. (Caveat in §7: if one of the 125 still-undecoded families is a repeat/loop
word, these counts become lower bounds.)

### 1.1 What does NOT execute

For the through frame, **119 of the 384 I-RAM words are never reached**:

```
   83              1 word    the gap between the epilogue and the unit-0 body
   133 .. 199     67 words   the unused tail of the unit-0 body region
   333 .. 383     51 words   the unused tail of unit 1 + the host poke region (352..382)
```

265 executed + 119 unreached = 384. **MEASURED.** The wait word at I-RAM 82 is what makes this
true: a linear PC sweep would otherwise walk into the poke region. Consequence for §5.3: the
host poke words at 352+ are **not** on the frame path and must be executed out of band.

---

## 2. THE ORDERED TABLE — the minimum audio-carrying frame

Unit 0 = **NO OPERATION** (algo 0; the through / no-effect image, shared by **42 of the 100**
effect slots — the simplest audio-carrying case there is), unit 1 = **ROOM REVERB**.
**265 words, each executed once.** Column `cur` is the running coefficient-cursor index under
the naive "one continuous cursor, +1 per `class4 == 0xA` word, never reset" rule — printed
because §5.2 shows that rule cannot be right, and this is where it breaks.

### 2.1  I-RAM 0..49 — common header, unit-0 preamble (50 words)
The audio INPUT stage is here (words 0..11). Word 49 is the CALL to unit 0.

| # | I-RAM | word (36-bit) | `hi12.class4.addr8.lo12` | cur | decode / MEASURED landmark |
|---:|---:|---|---|---:|---|
| 0 |   0 | `009220120D` | `092.2.01.20D` |  | ?word |
| 1 |   1 | `0C0A0E0000` | `C0A.0.E0.000` |  | ?word  hi12[11:8]==C: bits [23:12] are a 12-bit IMMEDIATE, not class+addr |
| 2 |   2 | `0084202680` | `084.2.02.680` |  | ?word |
| 3 |   3 | `00122FF1CE` | `012.2.FF.1CE` |  | ?word |
| 4 |   4 | `02042021CE` | `204.2.02.1CE` |  | ?word |
| 5 |   5 | `0202A00448` | `202.A.00.448` | 0 | ?word |
| 6 |   6 | `0400A00419` | `400.A.00.419` | 1 | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 7 |   7 | `0090A011C8` | `090.A.01.1C8` | 2 | ?word |
| 8 |   8 | `00842011C0` | `084.2.01.1C0` |  | ?word |
| 9 |   9 | `00122FF1D5` | `012.2.FF.1D5` |  | ?word |
| 10 |  10 | `0282A01417` | `282.A.01.417` | 3 | ?word |
| 11 |  11 | `0400201447` | `400.2.01.447` |  | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 12 |  12 | `08801202D5` | `880.1.20.2D5` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 13 |  13 | `0282200000` | `282.2.00.000` |  | ?word |
| 14 |  14 | `0400A00000` | `400.A.00.000` | 4 | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 15 |  15 | `0C0A292820` | `C0A.2.92.820` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 16 |  16 | `0192A00455` | `192.A.00.455` | 5 | ?word |
| 17 |  17 | `0292A00455` | `292.A.00.455` | 6 | ?word |
| 18 |  18 | `0182A00415` | `182.A.00.415` | 7 | ?word |
| 19 |  19 | `051220044D` | `512.2.00.44D` |  | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 20 |  20 | `0000A0064D` | `000.A.00.64D` | 8 | ?word |
| 21 |  21 | `0410A0040E` | `410.A.00.40E` | 9 | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 22 |  22 | `0C04312820` | `C04.3.12.820` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 23 |  23 | `0692A00415` | `692.A.00.415` | 10 | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 24 |  24 | `0692200415` | `692.2.00.415` |  | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 25 |  25 | `00002002D9` | `000.2.00.2D9` |  | ?word |
| 26 |  26 | `088012040B` | `880.1.20.40B` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 27 |  27 | `0012201655` | `012.2.01.655` |  | ?word |
| 28 |  28 | `05042001D5` | `504.2.00.1D5` |  | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 29 |  29 | `0C42457820` | `C42.4.57.820` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 30 |  30 | `009AA00200` | `09A.A.00.200` | 11 | ?word |
| 31 |  31 | `0C0A4B1820` | `C0A.4.B1.820` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 32 |  32 | `0000AFF207` | `000.A.FF.207` | 12 | ?word |
| 33 |  33 | `0412A00200` | `412.A.00.200` | 13 | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 34 |  34 | `0000AFF407` | `000.A.FF.407` | 14 | ?word |
| 35 |  35 | `0012A001C0` | `012.A.00.1C0` | 15 | ?word |
| 36 |  36 | `0400A00000` | `400.A.00.000` | 16 | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 37 |  37 | `0092A011C0` | `092.A.01.1C0` | 17 | ?word |
| 38 |  38 | `0809000839` | `809.0.00.839` |  | ?word |
| 39 |  39 | `0410AFF647` | `410.A.FF.647` | 18 | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 40 |  40 | `0C4A1C0820` | `C4A.1.C0.820` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 41 |  41 | `0400A0021A` | `400.A.00.21A` | 19 | ?word  END OF BLOCK (falls through) -- and still performs the rest of the word |
| 42 |  42 | `0801070821` | `801.0.70.821` |  | ldptr #$70 |
| 43 |  43 | `080106C827` | `801.0.6C.827` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 44 |  44 | `0801025825` | `801.0.25.825` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 45 |  45 | `0010A0020C` | `010.A.00.20C` | 20 | ?word |
| 46 |  46 | `080016000B` | `800.1.60.00B` |  | ?word |
| 47 |  47 | `080080C000` | `800.8.0C.000` |  | ?word  class 8: post-sum step (rescale/round/saturate?), OPERATION UNKNOWN |
| 48 |  48 | `0C645A2000` | `C64.5.A2.000` |  | ?word  hi12[11:8]==C: bits [23:12] are a 12-bit IMMEDIATE, not class+addr |
| 49 |  49 | `040010E000` | `400.1.0E.000` |  | ?word  END OF BLOCK, unit 0 -- CALL/RETURN -- and still performs the rest of the word |

### 2.2  I-RAM 84..132 — unit-0 body: NO OPERATION (49 words)
The through / no-effect image, shared by 42 of the 100 effect slots. Its last word
(`42C.1.0E.000`) carries the unit-0 tag and RETURNs to header word 50.

| # | I-RAM | word (36-bit) | `hi12.class4.addr8.lo12` | cur | decode / MEASURED landmark |
|---:|---:|---|---|---:|---|
| 50 |  84 | `088013000B` | `880.1.30.00B` |  | ?word  framing word, carries no DRAM information (MEASURED) |
| 51 |  85 | `0000204000` | `000.2.04.000` |  | ?word |
| 52 |  86 | `00002FC407` | `000.2.FC.407` |  | ?word |
| 53 |  87 | `000020B1CD` | `000.2.0B.1CD` |  | ?word |
| 54 |  88 | `000020040E` | `000.2.00.40E` |  | ?word |
| 55 |  89 | `0212200000` | `212.2.00.000` |  | ?word  plain store: mem[ptr] <- acc (nothing asked of lo12) |
| 56 |  90 | `002E200000` | `02E.2.00.000` |  | ?word |
| 57 |  91 | `00002F9407` | `000.2.F9.407` |  | ?word |
| 58 |  92 | `00122061C0` | `012.2.06.1C0` |  | ?word |
| 59 |  93 | `00022051C0` | `002.2.05.1C0` |  | ?word |
| 60 |  94 | `002E200000` | `02E.2.00.000` |  | ?word |
| 61 |  95 | `0018A001D5` | `018.A.00.1D5` | 21 | ?word |
| 62 |  96 | `0104A001D5` | `104.A.00.1D5` | 22 | ?word |
| 63 |  97 | `0C402C0000` | `C40.2.C0.000` |  | ?word  envelope / level detector (INFERRED) |
| 64 |  98 | `0182A00000` | `182.A.00.000` | 23 | ?word |
| 65 |  99 | `000023C447` | `000.2.3C.447` |  | ?word |
| 66 | 100 | `0000A001D3` | `000.A.00.1D3` | 24 | ?word  read into carry latch A (INFERRED) |
| 67 | 101 | `029AAB821A` | `29A.A.B8.21A` | 25 | ?word |
| 68 | 102 | `080B000839` | `80B.0.00.839` |  | ?word |
| 69 | 103 | `0C40500647` | `C40.5.00.647` |  | ?word  envelope / level detector (INFERRED) |
| 70 | 104 | `0000200688` | `000.2.00.688` |  | ?word |
| 71 | 105 | `00922FF1D5` | `092.2.FF.1D5` |  | ?word |
| 72 | 106 | `0184A011D5` | `184.A.01.1D5` | 26 | ?word |
| 73 | 107 | `01822FF000` | `182.2.FF.000` |  | ?word |
| 74 | 108 | `0000209447` | `000.2.09.447` |  | ?word |
| 75 | 109 | `00122F71C0` | `012.2.F7.1C0` |  | ?word |
| 76 | 110 | `08801602D9` | `880.1.60.2D9` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 77 | 111 | `0000A09655` | `000.A.09.655` | 27 | ?word |
| 78 | 112 | `00002F7000` | `000.2.F7.000` |  | ?word |
| 79 | 113 | `0212200419` | `212.2.00.419` |  | ?word  writes mem[ptr] (bit 4), class-independent |
| 80 | 114 | `088012064B` | `880.1.20.64B` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 81 | 115 | `00002071CD` | `000.2.07.1CD` |  | ?word |
| 82 | 116 | `000020040E` | `000.2.00.40E` |  | ?word |
| 83 | 117 | `0212200000` | `212.2.00.000` |  | ?word  plain store: mem[ptr] <- acc (nothing asked of lo12) |
| 84 | 118 | `00002F7000` | `000.2.F7.000` |  | ?word |
| 85 | 119 | `002C20A1CD` | `02C.2.0A.1CD` |  | ?word |
| 86 | 120 | `00002FF1CE` | `000.2.FF.1CE` |  | ?word |
| 87 | 121 | `02122F9407` | `212.2.F9.407` |  | ?word  writes mem[ptr] (bit 4), class-independent |
| 88 | 122 | `002E200000` | `02E.2.00.000` |  | ?word |
| 89 | 123 | `08801602D9` | `880.1.60.2D9` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 90 | 124 | `0000A08655` | `000.A.08.655` | 28 | ?word |
| 91 | 125 | `00002F8000` | `000.2.F8.000` |  | ?word |
| 92 | 126 | `0212200419` | `212.2.00.419` |  | ?word  writes mem[ptr] (bit 4), class-independent |
| 93 | 127 | `088012064B` | `880.1.20.64B` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 94 | 128 | `00002F91CD` | `000.2.F9.1CD` |  | ?word |
| 95 | 129 | `000020040E` | `000.2.00.40E` |  | ?word |
| 96 | 130 | `0212200000` | `212.2.00.000` |  | ?word  plain store: mem[ptr] <- acc (nothing asked of lo12) |
| 97 | 131 | `0880160000` | `880.1.60.000` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 98 | 132 | `042C10E000` | `42C.1.0E.000` |  | ?word  END OF BLOCK, unit 0 -- CALL/RETURN -- and still performs the rest of the word |

### 2.3  I-RAM 50..59 — common header, unit-1 preamble (10 words)
Word 59 is the CALL to unit 1.

| # | I-RAM | word (36-bit) | `hi12.class4.addr8.lo12` | cur | decode / MEASURED landmark |
|---:|---:|---|---|---:|---|
| 99 |  50 | `0801050821` | `801.0.50.821` |  | ldptr #$50 |
| 100 |  51 | `0801064827` | `801.0.64.827` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 101 |  52 | `0801025825` | `801.0.25.825` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 102 |  53 | `00109D020C` | `010.9.D0.20C` |  | ?word |
| 103 |  54 | `080016000B` | `800.1.60.00B` |  | ?word |
| 104 |  55 | `0000201007` | `000.2.01.007` |  | ?word |
| 105 |  56 | `0C646A2007` | `C64.6.A2.007` |  | ?word  table-lookup idiom, class-6 addr8 = table selector (INFERRED) |
| 106 |  57 | `0000201000` | `000.2.01.000` |  | ?word |
| 107 |  58 | `000018A007` | `000.1.8A.007` |  | ?word |
| 108 |  59 | `040010F007` | `400.1.0F.007` |  | ?word  END OF BLOCK, unit 1 -- CALL/RETURN -- and still performs the rest of the word |

### 2.4  I-RAM 200..332 — unit-1 body: ROOM REVERB (133 words)
The ONLY unit-1 image in the corpus: algos 16..27 (all 12 reverb presets) share it,
so THIS BODY RUNS IN EVERY FRAME OF EVERY EFFECT. Its last word (`612.1.0F.000`)
carries the unit-1 tag and RETURNs to word 60.

| # | I-RAM | word (36-bit) | `hi12.class4.addr8.lo12` | cur | decode / MEASURED landmark |
|---:|---:|---|---|---:|---|
| 109 | 200 | `088013000B` | `880.1.30.00B` |  | ?word  framing word, carries no DRAM information (MEASURED) |
| 110 | 201 | `0000289415` | `000.2.89.415` |  | ?word |
| 111 | 202 | `0212A811D5` | `212.A.81.1D5` | 29 | ?word  writes mem[ptr] (bit 4), class-independent |
| 112 | 203 | `0202AFD1D5` | `202.A.FD.1D5` | 30 | mac (p)+-3 |
| 113 | 204 | `0202AF91D5` | `202.A.F9.1D5` | 31 | mac (p)+-7 |
| 114 | 205 | `020224B1CD` | `202.2.4B.1CD` |  | ?word |
| 115 | 206 | `000020040E` | `000.2.00.40E` |  | ?word |
| 116 | 207 | `0212A001D5` | `212.A.00.1D5` | 32 | ?word  writes mem[ptr] (bit 4), class-independent |
| 117 | 208 | `0212A00415` | `212.A.00.415` | 33 | ?word  writes mem[ptr] (bit 4), class-independent |
| 118 | 209 | `0202A001D5` | `202.A.00.1D5` | 34 | mac (p)+0 |
| 119 | 210 | `0202200407` | `202.2.00.407` |  | ?word |
| 120 | 211 | `08801602DA` | `880.1.60.2DA` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 121 | 212 | `0000A00695` | `000.A.00.695` | 35 | ?word |
| 122 | 213 | `00002BA000` | `000.2.BA.000` |  | ?word |
| 123 | 214 | `0212200419` | `212.2.00.419` |  | ?word  writes mem[ptr] (bit 4), class-independent |
| 124 | 215 | `088012064B` | `880.1.20.64B` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 125 | 216 | `0000200000` | `000.2.00.000` |  | nop |
| 126 | 217 | `0000A0A1D5` | `000.A.0A.1D5` | 36 | ?word |
| 127 | 218 | `0202200000` | `202.2.00.000` |  | ?word |
| 128 | 219 | `08801602D4` | `880.1.60.2D4` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 129 | 220 | `0104200000` | `104.2.00.000` |  | ?word  all-pass marker -- step UNKNOWN |
| 130 | 221 | `0000200419` | `000.2.00.419` |  | ?word  all-pass: y <- d_out - t (its partner) |
| 131 | 222 | `0012200680` | `012.2.00.680` |  | ?word  all-pass: d_in <- x + t (the WRITE), bit 4 breaks the 2-permutation |
| 132 | 223 | `0880120655` | `880.1.20.655` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 133 | 224 | `0102A0064B` | `102.A.00.64B` | 37 | ?word  gain multiply (same op in phaser all-pass and reverb diffuser) |
| 134 | 225 | `0000200000` | `000.2.00.000` |  | nop |
| 135 | 226 | `0000200000` | `000.2.00.000` |  | nop |
| 136 | 227 | `08801602D4` | `880.1.60.2D4` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 137 | 228 | `0104200000` | `104.2.00.000` |  | ?word  all-pass marker -- step UNKNOWN |
| 138 | 229 | `0000200419` | `000.2.00.419` |  | ?word  all-pass: y <- d_out - t (its partner) |
| 139 | 230 | `0012200680` | `012.2.00.680` |  | ?word  all-pass: d_in <- x + t (the WRITE), bit 4 breaks the 2-permutation |
| 140 | 231 | `0880120655` | `880.1.20.655` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 141 | 232 | `0102A0064B` | `102.A.00.64B` | 38 | ?word  gain multiply (same op in phaser all-pass and reverb diffuser) |
| 142 | 233 | `0000200000` | `000.2.00.000` |  | nop |
| 143 | 234 | `0000200000` | `000.2.00.000` |  | nop |
| 144 | 235 | `08801602D4` | `880.1.60.2D4` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 145 | 236 | `0104200000` | `104.2.00.000` |  | ?word  all-pass marker -- step UNKNOWN |
| 146 | 237 | `0000200419` | `000.2.00.419` |  | ?word  all-pass: y <- d_out - t (its partner) |
| 147 | 238 | `0012200680` | `012.2.00.680` |  | ?word  all-pass: d_in <- x + t (the WRITE), bit 4 breaks the 2-permutation |
| 148 | 239 | `0880120655` | `880.1.20.655` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 149 | 240 | `0102A0064B` | `102.A.00.64B` | 39 | ?word  gain multiply (same op in phaser all-pass and reverb diffuser) |
| 150 | 241 | `0000200000` | `000.2.00.000` |  | nop |
| 151 | 242 | `0000200000` | `000.2.00.000` |  | nop |
| 152 | 243 | `08801602D4` | `880.1.60.2D4` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 153 | 244 | `0104200000` | `104.2.00.000` |  | ?word  all-pass marker -- step UNKNOWN |
| 154 | 245 | `0000200419` | `000.2.00.419` |  | ?word  all-pass: y <- d_out - t (its partner) |
| 155 | 246 | `0012200680` | `012.2.00.680` |  | ?word  all-pass: d_in <- x + t (the WRITE), bit 4 breaks the 2-permutation |
| 156 | 247 | `0880120655` | `880.1.20.655` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 157 | 248 | `0102A0064B` | `102.A.00.64B` | 40 | ?word  gain multiply (same op in phaser all-pass and reverb diffuser) |
| 158 | 249 | `0000200000` | `000.2.00.000` |  | nop |
| 159 | 250 | `0000200000` | `000.2.00.000` |  | nop |
| 160 | 251 | `08801602D4` | `880.1.60.2D4` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 161 | 252 | `0104200000` | `104.2.00.000` |  | ?word  all-pass marker -- step UNKNOWN |
| 162 | 253 | `0000200419` | `000.2.00.419` |  | ?word  all-pass: y <- d_out - t (its partner) |
| 163 | 254 | `0012200680` | `012.2.00.680` |  | ?word  all-pass: d_in <- x + t (the WRITE), bit 4 breaks the 2-permutation |
| 164 | 255 | `0880120655` | `880.1.20.655` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 165 | 256 | `0102A0064B` | `102.A.00.64B` | 41 | ?word  gain multiply (same op in phaser all-pass and reverb diffuser) |
| 166 | 257 | `0000200000` | `000.2.00.000` |  | nop |
| 167 | 258 | `0000200000` | `000.2.00.000` |  | nop |
| 168 | 259 | `08801602DA` | `880.1.60.2DA` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 169 | 260 | `0000A00695` | `000.A.00.695` | 42 | ?word |
| 170 | 261 | `00002F3407` | `000.2.F3.407` |  | ?word |
| 171 | 262 | `0212200419` | `212.2.00.419` |  | ?word  writes mem[ptr] (bit 4), class-independent |
| 172 | 263 | `088012064B` | `880.1.20.64B` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 173 | 264 | `000024A407` | `000.2.4A.407` |  | ?word |
| 174 | 265 | `0000A001D5` | `000.A.00.1D5` | 43 | ?word |
| 175 | 266 | `0212A00415` | `212.A.00.415` | 44 | ?word  writes mem[ptr] (bit 4), class-independent |
| 176 | 267 | `0202A001D5` | `202.A.00.1D5` | 45 | mac (p)+0 |
| 177 | 268 | `0202200407` | `202.2.00.407` |  | ?word |
| 178 | 269 | `08801602D4` | `880.1.60.2D4` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 179 | 270 | `0104200000` | `104.2.00.000` |  | ?word  all-pass marker -- step UNKNOWN |
| 180 | 271 | `0000200419` | `000.2.00.419` |  | ?word  all-pass: y <- d_out - t (its partner) |
| 181 | 272 | `0012200680` | `012.2.00.680` |  | ?word  all-pass: d_in <- x + t (the WRITE), bit 4 breaks the 2-permutation |
| 182 | 273 | `0880120655` | `880.1.20.655` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 183 | 274 | `0102ABA64B` | `102.A.BA.64B` | 46 | ?word  gain multiply (same op in phaser all-pass and reverb diffuser) |
| 184 | 275 | `0000200000` | `000.2.00.000` |  | nop |
| 185 | 276 | `0000200000` | `000.2.00.000` |  | nop |
| 186 | 277 | `08801602D4` | `880.1.60.2D4` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 187 | 278 | `0104200000` | `104.2.00.000` |  | ?word  all-pass marker -- step UNKNOWN |
| 188 | 279 | `0000200419` | `000.2.00.419` |  | ?word  all-pass: y <- d_out - t (its partner) |
| 189 | 280 | `0012200680` | `012.2.00.680` |  | ?word  all-pass: d_in <- x + t (the WRITE), bit 4 breaks the 2-permutation |
| 190 | 281 | `0880120655` | `880.1.20.655` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 191 | 282 | `0102A0064B` | `102.A.00.64B` | 47 | ?word  gain multiply (same op in phaser all-pass and reverb diffuser) |
| 192 | 283 | `0000200000` | `000.2.00.000` |  | nop |
| 193 | 284 | `0000200000` | `000.2.00.000` |  | nop |
| 194 | 285 | `08801602D4` | `880.1.60.2D4` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 195 | 286 | `0104200000` | `104.2.00.000` |  | ?word  all-pass marker -- step UNKNOWN |
| 196 | 287 | `0000200419` | `000.2.00.419` |  | ?word  all-pass: y <- d_out - t (its partner) |
| 197 | 288 | `0012200680` | `012.2.00.680` |  | ?word  all-pass: d_in <- x + t (the WRITE), bit 4 breaks the 2-permutation |
| 198 | 289 | `0880120655` | `880.1.20.655` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 199 | 290 | `0102A0064B` | `102.A.00.64B` | 48 | ?word  gain multiply (same op in phaser all-pass and reverb diffuser) |
| 200 | 291 | `0000200000` | `000.2.00.000` |  | nop |
| 201 | 292 | `0000200000` | `000.2.00.000` |  | nop |
| 202 | 293 | `08801602D4` | `880.1.60.2D4` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 203 | 294 | `0104200000` | `104.2.00.000` |  | ?word  all-pass marker -- step UNKNOWN |
| 204 | 295 | `0000200419` | `000.2.00.419` |  | ?word  all-pass: y <- d_out - t (its partner) |
| 205 | 296 | `0012200680` | `012.2.00.680` |  | ?word  all-pass: d_in <- x + t (the WRITE), bit 4 breaks the 2-permutation |
| 206 | 297 | `0880120655` | `880.1.20.655` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 207 | 298 | `0102A0064B` | `102.A.00.64B` | 49 | ?word  gain multiply (same op in phaser all-pass and reverb diffuser) |
| 208 | 299 | `0000200000` | `000.2.00.000` |  | nop |
| 209 | 300 | `0000200000` | `000.2.00.000` |  | nop |
| 210 | 301 | `08801602DA` | `880.1.60.2DA` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 211 | 302 | `0000A00695` | `000.A.00.695` | 50 | ?word |
| 212 | 303 | `00002FE407` | `000.2.FE.407` |  | ?word |
| 213 | 304 | `0212200419` | `212.2.00.419` |  | ?word  writes mem[ptr] (bit 4), class-independent |
| 214 | 305 | `088012064B` | `880.1.20.64B` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 215 | 306 | `0000249407` | `000.2.49.407` |  | ?word |
| 216 | 307 | `0090A001D5` | `090.A.00.1D5` | 51 | ?word |
| 217 | 308 | `0212A00415` | `212.A.00.415` | 52 | ?word  writes mem[ptr] (bit 4), class-independent |
| 218 | 309 | `0202A001D5` | `202.A.00.1D5` | 53 | mac (p)+0 |
| 219 | 310 | `02022B8407` | `202.2.B8.407` |  | ?word |
| 220 | 311 | `0C40180000` | `C40.1.80.000` |  | ?word  envelope / level detector (INFERRED) |
| 221 | 312 | `0C40180000` | `C40.1.80.000` |  | ?word  envelope / level detector (INFERRED) |
| 222 | 313 | `00002FE407` | `000.2.FE.407` |  | ?word |
| 223 | 314 | `08801202D5` | `880.1.20.2D5` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 224 | 315 | `0282A00000` | `282.A.00.000` | 54 | ?word |
| 225 | 316 | `0000A0C452` | `000.A.0C.452` | 55 | ?word |
| 226 | 317 | `0212AF51D5` | `212.A.F5.1D5` | 56 | ?word  writes mem[ptr] (bit 4), class-independent |
| 227 | 318 | `0202AFC1D5` | `202.A.FC.1D5` | 57 | mac (p)+-4 |
| 228 | 319 | `02022081CD` | `202.2.08.1CD` |  | ?word |
| 229 | 320 | `00902FB40E` | `090.2.FB.40E` |  | ?word |
| 230 | 321 | `0212205000` | `212.2.05.000` |  | ?word  writes mem[ptr] (bit 4), class-independent |
| 231 | 322 | `0C40180000` | `C40.1.80.000` |  | ?word  envelope / level detector (INFERRED) |
| 232 | 323 | `0C40180000` | `C40.1.80.000` |  | ?word  envelope / level detector (INFERRED) |
| 233 | 324 | `00002FB407` | `000.2.FB.407` |  | ?word |
| 234 | 325 | `08801202D5` | `880.1.20.2D5` |  | ?word  external-DRAM bracket CLOSE (INFERRED) |
| 235 | 326 | `0282A00000` | `282.A.00.000` | 58 | ?word |
| 236 | 327 | `0000AFF452` | `000.A.FF.452` | 59 | ?word |
| 237 | 328 | `0212A041D5` | `212.A.04.1D5` | 60 | ?word  writes mem[ptr] (bit 4), class-independent |
| 238 | 329 | `0202AFA1D5` | `202.A.FA.1D5` | 61 | mac (p)+-6 |
| 239 | 330 | `020227B1CD` | `202.2.7B.1CD` |  | ?word |
| 240 | 331 | `088016040E` | `880.1.60.40E` |  | ?word  external-DRAM bracket OPEN (INFERRED) |
| 241 | 332 | `061210F000` | `612.1.0F.000` |  | ?word  END OF BLOCK, unit 1 -- CALL/RETURN -- and still performs the rest of the word |

### 2.5  I-RAM 60..82 — epilogue / output stage (23 words)
Contains the two host-patched effect-return words (64 and 71) and ends on
`C00.A.47.407`, the wait-for-frame-strobe word (0 occurrences in 2974 body words).
Words 64 and 71 are shown AS PATCHED at the end of the captured cold boot; their
as-uploaded defaults are `011.9.0E.445` and `011.9.0F.446`.

| # | I-RAM | word (36-bit) | `hi12.class4.addr8.lo12` | cur | decode / MEASURED landmark |
|---:|---:|---|---|---:|---|
| 242 |  60 | `009218D15B` | `092.1.8D.15B` |  | ?word |
| 243 |  61 | `001218D05B` | `012.1.8D.05B` |  | ?word |
| 244 |  62 | `0801026825` | `801.0.26.825` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 245 |  63 | `02A79051C3` | `2A7.9.05.1C3` |  | ?word |
| 246 |  64 | `0C40A80445` | `C40.A.80.445` | 62 | ?word  envelope / level detector (INFERRED) |
| 247 |  65 | `020018F1C1` | `200.1.8F.1C1` |  | ?word |
| 248 |  66 | `000018C107` | `000.1.8C.107` |  | ?word |
| 249 |  67 | `0980520402` | `980.5.20.402` |  | ?word |
| 250 |  68 | `009218C19B` | `092.1.8C.19B` |  | ?word |
| 251 |  69 | `0801090821` | `801.0.90.821` |  | ldptr #$90 |
| 252 |  70 | `02A61850C7` | `2A6.1.85.0C7` |  | ?word |
| 253 |  71 | `0C41900446` | `C41.9.00.446` |  | ?word  hi12[11:8]==C: bits [23:12] are a 12-bit IMMEDIATE, not class+addr |
| 254 |  72 | `0000106087` | `000.1.06.087` |  | ?word |
| 255 |  73 | `0E30C00404` | `E30.C.00.404` |  | ?word |
| 256 |  74 | `0C169AB000` | `C16.9.AB.000` |  | ?word  hi12[11:8]==C: bits [23:12] are a 12-bit IMMEDIATE, not class+addr |
| 257 |  75 | `082E80F000` | `82E.8.0F.000` |  | ?word  class 8: post-sum step (rescale/round/saturate?), OPERATION UNKNOWN |
| 258 |  76 | `0C00984000` | `C00.9.84.000` |  | ?word  hi12[11:8]==C: bits [23:12] are a 12-bit IMMEDIATE, not class+addr |
| 259 |  77 | `0859086822` | `859.0.86.822` |  | ?word  pointer-load family sibling, target register UNKNOWN |
| 260 |  78 | `0A3CD9F287` | `A3C.D.9F.287` |  | ?word  hi12[11:8]==A: host-poke data form, bits [23:12] are immediate |
| 261 |  79 | `00122FF1CE` | `012.2.FF.1CE` |  | ?word |
| 262 |  80 | `01042001CE` | `104.2.00.1CE` |  | ?word |
| 263 |  81 | `0102200000` | `102.2.00.000` |  | ?word  gain multiply (same op in phaser all-pass and reverb diffuser) |
| 264 |  82 | `0C00A47407` | `C00.A.47.407` | 63 | ?word  hi12[11:8]==C: bits [23:12] are a 12-bit IMMEDIATE, not class+addr |

---

## 3. Per-program summary (smallest frame first)

| program (unit 0) + reverb | words/frame | distinct words | distinct families | decoded words | decoded forms present |
|---|---:|---:|---:|---:|---|
| **COMPRESSOR** (algo 36, 40 w) | **256** | 155 | 120 | 29 (11.3 %) | `nop`×19, `mac`×7, `ldptr`×3 |
| **NO OPERATION** (algo 0, 49 w) | **265** | 162 | 128 | 29 (10.9 %) | `nop`×19, `mac`×7, `ldptr`×3 |
| **CHORUS** (algo 1, 70 w) | **286** | 173 | 132 | 30 (10.5 %) | `nop`×19, `mac`×8, `ldptr`×3 |
| **PARAMETRIC EQ** (algo 39, 105 w) | **321** | 150 | 119 | 70 (21.8 %) | `nop`×19, `mac`×27, `mac.lb`×10, `mulst`×10, `rstcur`×1, `ldptr`×3 |

Region split (identical for all four except the unit-0 body):

```
   header 0..49        50 words     (21 class-A coefficient multiplies)
   unit-0 body         40..110      (8 / 10 / 19 / 60 class-A for the four above)
   header 50..59       10 words     (0 class-A)
   unit-1 body        133 words     (33 class-A)
   epilogue 60..82     23 words     (2 class-A -- but see 5.2, both are C-format)
```

Per-frame datapath traffic, through frame: **64 class-A coefficient multiplies, 73 cursor-fetch
words, 56 accumulator→`mem[ptr]` stores, 36 delay-DRAM words**. At 44 100 Hz that is 2.82 M
coefficient multiplies/s and 1.59 M DRAM words/s — both comfortable for a 25 MHz part with a
4 Mbit fast-page DRAM, which is a (weak) consistency check on the whole model.

**Frame-size envelope over the whole corpus (MEASURED):** unit-0 body lengths are
40…110 words (33 distinct), the unit-1 body is always 133, so the frame is
`60 + body0 + 133 + 23` = **256 … 326 slots**, i.e. **1.74 … 2.21 cycles per word** out of the
567 cycles a 25 MHz clock gives at 44.1 kHz.

---

## 4. The distinct opcode set — and where the ignorance actually is

Because `hi12` is a horizontal microword and `addr8` is an operand (a signed pointer delta, a
unit index or a table selector — MEASURED), the honest unit of "opcode" is the family
**(`hi12`, `class4`, `lo12`)**. Full per-program sets: `--sets`.

### 4.1 The always-executed scaffolding is the bottleneck

| block | words | distinct words | distinct families | decoded |
|---|---:|---:|---:|---:|
| **scaffolding** (header 0..59 + epilogue 60..82) | 83 | 79 | **75** | **3** |
| **reverb body** (200..332) | 133 | 49 | 31 | 26 |
| **floor** = scaffolding + reverb (every frame, every effect) | **216** | 127 | **104** | 29 |
| through frame (floor + NO OPERATION) | 265 | 162 | 128 | 29 |

Two things fall out of that table:

* the **reverb**, the largest single block on the path, is the *best*-understood: 133 words,
  only 31 families, 26 words decoded — because its algorithm was solved to the bit;
* the **scaffolding** is 83 words with **75 distinct families** — almost every word is its own
  family, i.e. it is wide, non-repetitive control/IO microcode — and **65 of those 75 families
  never occur in any of the 38 effect bodies**:

```
000.1.**.007  000.1.**.087  000.1.**.107  000.2.**.007  000.2.**.2D9  000.A.**.207  000.A.**.407
000.A.**.64D  010.9.**.20C  010.A.**.20C  012.1.**.05B  012.2.**.1CE  012.A.**.1C0  084.2.**.1C0
084.2.**.680  090.A.**.1C8  092.1.**.15B  092.1.**.19B  092.2.**.20D  092.A.**.1C0  182.A.**.415
192.A.**.455  200.1.**.1C1  202.A.**.448  204.2.**.1CE  282.A.**.417  292.A.**.455  2A6.1.**.0C7
2A7.9.**.1C3  400.1.**.007  400.2.**.447  400.A.**.000  400.A.**.21A  400.A.**.419  410.A.**.40E
410.A.**.647  412.A.**.200  504.2.**.1D5  512.2.**.44D  692.2.**.415  692.A.**.415  800.1.**.00B
800.8.**.000  801.0.**.821  801.0.**.825  801.0.**.827  809.0.**.839  82E.8.**.000  859.0.**.822
980.5.**.402  A3C.D.**.287  C00.9.**.000  C00.A.**.407  C04.3.**.820  C0A.0.**.000  C0A.2.**.820
C0A.4.**.820  C16.9.**.000  C40.A.**.445  C41.9.**.446  C42.4.**.820  C4A.1.**.820  C64.5.**.000
C64.6.**.007  E30.C.**.404
```

**This list is the audio path.** It contains the input stage, the output stage, both host-patched
wet-level slots, the register loads and the frame terminator, and **not one of the 65 has ever
appeared in any frequency-ranked worklist**, because every such worklist was built from the
2974-word body corpus that excludes them by construction. The `-core-draft.md` §6 worklist ranks
`212.2` vs `212.A`, the `0x415` group and the table-lookup triple — all of which are *body*
questions. None of them is on the critical path for getting a sample in and out of the chip.

### 4.2 What is already decoded on the path

Only three of the six known forms appear in the through frame, 29 words in all:
`nop` ×19, `mac (p)+dd` ×7, `ldptr #$NN` ×3. PARAMETRIC EQ is the outlier at 70/321 (21.8 %)
because its 105-word body is the one program that was solved to the bit — it is the *only*
program where `mulst`, `mac.lb` and `rstcur` execute at all.

---

## 5. What must be modelled for audio to flow (and what is missing)

### 5.1 The five stages, in execution order

| stage | I-RAM | status |
|---|---|---|
| **input** | 0..11 — two near-parallel blocks distinguished by `addr8` 0x02 / 0x01, each closed by a `0x4xx` route word (`419`, `447`); `addr8 == 0x03` never occurs | **LOCATED, NOT DECODED.** Two channels, i.e. one stereo pair, not the chip's three DI ports |
| **per-unit setup** | 42..48 and 50..58 — `ldptr`/register loads + a class-5/class-6 twin (`C64.5.A2.000` / `C64.6.A2.007`) at the same position in each unit's block | pointer load PROVEN; the class-5/6 twin INFERRED to be the per-unit *send* |
| **unit-0 body** | 84.. | the selected effect; 40–110 words |
| **unit-1 body** | 200..332 | always ROOM REVERB, 133 words |
| **output** | 60..82 — including the only two words the host ever patches, I-RAM 64 (`lo12 = 0x445`) and 71 (`lo12 = 0x446`), tagged 0x0E / 0x0F in their as-uploaded default form | **LOCATED, NOT DECODED.** The invariant `lo12` per slot names the two effect-return buses |

New here: **both patched slots are in the C-format** (`hi12[11:8] == 0xC`), so the effect-return
level is carried as a **12-bit immediate in bits [23:12]**, not as a coefficient. Observed live
values, in upload order: slot 64 `0x540 → 0x540 → 0xA80`; slot 71 `0x640 → 0x640 → 0x900`.
`0xA80 = 2 × 0x540` exactly. **MEASURED values; the "immediate = level" reading is INFERRED**
(two values per slot is not a curve).

### 5.2 The coefficient cursor must be re-based on the path, and nothing on the path is known to do it

MEASURED facts that cannot all hold at once under the current cursor rule:

* the cursor is implicit, advances **+1 per `class4 == 0xA` word**, and is reset only by
  `rstcur` (`801.0.00.021`);
* the unit-0 coefficient bank base is **0x00** (measured across 16 swept effects, and the host
  always anchors its coefficient uploads at `00.821`);
* the unit-1 reverb bank base is **0x90**;
* the header executes **21 class-A words before the CALL at 49**, and the epilogue two more;
* `rstcur` occurs in **exactly one** of 38 programs (PARAMETRIC EQ, once) — `grep -c rstcur`
  over `dsp/disasm/*.dsm`.

So on entry to the unit-0 body a continuous cursor would stand at 21, not 0; on entry to the
reverb at 29, not 0x90. **Something re-bases it at the unit boundary and it is not an
instruction we can name.** Two candidates, neither established:

* **BNK-R** (the bank register in the CDJ-500 block diagram) switched by the unit tag — this
  would also explain `-headerdecode.md` §5's measurement that the header reads a *separate*
  coefficient bank (over 38 images, coefficients-uploaded minus body cursor-words centres on
  **+1**, never near +23);
* the **register-load family** `801/809/80B . 0 . NN . {821,822,825,827,839}`. Note
  `809.0.00.839` at header I-RAM **38** — value `0x00`, immediately before the unit-0 call —
  and `80B.0.00.839` in NO OPERATION; `.839` occurs **twice in the entire tree and nowhere
  else**. Note also `801.0.90.821` at epilogue I-RAM **69**, whose immediate `0x90` is exactly
  the reverb bank base, and which is also the word the host uses to *close* every coefficient
  upload. **INFERRED leads, both testable the moment one register-load target is pinned.**

This question is unreachable from the corpus: it only exists once you execute the header, the
body and the epilogue in one continuous stream.

### 5.3 The host poke region is off the frame path

I-RAM 352..382 is never reached (§1.1) because the frame stops at the wait word at 82. Yet the
host writes 5-byte *instruction-shaped* words there — pointer loads (`801.0.NN.821/825`) and
`hi12 = 0xA__` immediate-carrying words — and that is demonstrably how coefficients reach C-RAM
(`-origin-capture.md` §3). **INFERRED:** the host writes an instruction into the poke slot and
the chip executes it out of band; the CDJ-500 block diagram's **UCPC** ("a second
program-counter-like register") is the obvious mechanism. This matters for the sound path
because it is the only known route from the Sub CPU's parameter changes into the coefficients
the frame multiplies by, and because it means an emulation must give the poke region an
execution trigger that is *not* the frame PC.

---

## 6. Predict-then-check, misses and corrections

### 6.1 PASS — the frame-size prediction

`-headerdecode.md` §3 predicted, from the model alone, "60 + unit-0 body + unit-1 body + 23; for
algo 1 (70) + reverb (133) that is **286** instruction slots per sample", and "the largest pair
in the corpus (110 + 133) gives **326**". Both are reproduced exactly by the trace: **286** for
the cold-boot pair, **326** for the corpus maximum. It also predicted the pair itself: the
cold-boot capture does load algo 1 at 84 and the reverb at 200. **CONFIRMED, 3/3.**

### 6.2 CORRECTION — `hi12 == 0xC40` is a FORMAT, not an "envelope detector"

`-headerdecode.md` §4.1 flagged that three of the four host-patched wet-level words are `0xC40`
while `-effect-map.md` calls `0xC40` an envelope detector, and said one of the two must give.
Three measurements settle it against the envelope reading:

* `0xC4_` words occur in **19 of the 38 programs**, including CHORUS (4), VIBRATO, ROCK ROTARY,
  ENHANCER, MIX UP and — decisively — the **REVERB** (`C40.1.80.000` ×4, at body words
  111, 112, 122, 123). A reverb tank has no level detector.
* The four host-patched effect-return words are `C40.5.40.445`, `C40.A.80.445`,
  `C40.6.40.446`, `C41.9.00.446`. A wet level is not an envelope detector.
* `hi12[11:8] == 0xC` is the **already-MEASURED** 12-bit-immediate format
  (`-header.md` §6: inside that family `class4` is immediate DATA spanning bits [23:12], not a
  class). Reading the `C4_` words that way gives immediates 0x320 (×29), 0x2C0 (×12), 0x1E0
  (×8), 0x180 (×4), 0x500, 0x000 — a small, tidy constant pool, which is what an immediate
  looks like and not what a role looks like.

**Recommendation (not applied here):** in `dsp_disasm.py`/`upd6383d.cpp` `annotate()`, the
`hi == 0xC40` → *"envelope / level detector"* rule sits **above** the `(hi & 0xF00) == 0xC00` →
*"12-bit IMMEDIATE"* rule and therefore mislabels every one of these words, including the two on
the output stage. It should be demoted below it, and "envelope detector" kept as a per-program
comment in the dynamics images only. This does not touch `-paramsemantics.md`'s finding that the
compressor's attack/release constant lives in this idiom — an immediate is a perfectly good
place for a time constant.

### 6.3 CORRECTION — the delay-DRAM "bracket" does not bracket

`880.1.60.*` is annotated OPEN and `880.1.20.*` CLOSE (INFERRED, MCC +0.944 over the
DRAM-using effects). Counted **per frame** instead of per image:

| frame | OPEN (`addr8=60`) | CLOSE (`addr8=20`) | framing (`addr8=30`) |
|---|---:|---:|---:|
| NO OPERATION + reverb | 16 | 18 | 2 |
| CHORUS + reverb | 14 | 20 | 2 |
| PARAMETRIC EQ + reverb | 13 | 16 | 3 |

A bracket must balance over a cyclic frame; these never do, and the imbalance is
program-dependent. **The pair reading is FALSIFIED as a bracket.** What survives is that
`addr8 ∈ {0x20, 0x30, 0x60}` selects among a small set of DRAM operations and the real operand
is `lo12` (`2D4/2DA/2D5/64B/655/40E/00B/407…`). Inside the reverb the two do alternate
strictly — `30 | (60,20)×13 | 20,20 | 60` — so a *sequence* reading (address phase / data
phase) is still live; a *nesting* reading is not.

Worth recording as the reason the counts can be unbalanced at all: the reverb's **last**
DRAM word before its terminator is an "OPEN" (`880.1.60.40E`, I-RAM 331) and the header's
first two DRAM words are "CLOSEs" (`880.1.20.2D5` at 12, `880.1.20.40B` at 26). Around the
frame wrap those line up. **SPECULATIVE**, but it is a hypothesis that only a per-frame view can
even state, and it would be normal engineering: a DRAM access started at the end of one frame
and collected early in the next hides its latency.

### 6.4 NEW DEFECT — the C-format and the cursor rule contradict each other, but only on the path

`class4 == 0xA` advances the coefficient cursor; `hi12[11:8] == 0xC` says `class4` is not a class
at all. Words that are both:

* **0 of the 2974 body corpus words**;
* **2 of the 265 frame words** — I-RAM **64** as patched (`C40.A.80.445`) and I-RAM **82**
  (`C00.A.47.407`, the wait word).

So this is a real ambiguity that no amount of corpus work could have surfaced, and it lands on
the output stage and the frame terminator. If a future core applies C-RAM addressing
continuously across a frame, these two words shift every later coefficient address by 2.

### 6.5 The `lo12 = 0x820` immediates are not loop counts

Five words in the header (I-RAM 15, 22, 29, 31, 40), zero in the 2974-word body corpus, all
`hi12` starting `0xC` — i.e. the C-format again — with immediates **0x1C0, 0x292, 0x312, 0x457,
0x4B1** = 448, 658, 786, 1111, 1201. `-header.md` §6 offered "loop counts, timer reloads
(TR0–TR3) or DRAM offsets". The frame budget removes the first: **567 cycles per frame** total,
so even the smallest (448) could not be iterated within a frame while 264 other words also run.
**Loop count: EXCLUDED by arithmetic on established numbers.** As sample offsets into the delay
DRAM they are 10.2, 14.9, 17.8, 25.2 and 27.2 ms — physically ordinary pre-delay / early
reflection values, and they are effect-**independent**, which fits fixed delay-line base
addresses. **SPECULATIVE**, offered as the surviving reading, not as a result.

### 6.6 Misses

* **The audio input and output words are still not decoded.** This note *locates* them
  precisely (I-RAM 0..11 and 60..82, with 64/71 as the two host-controlled levels) and shows
  they are 65 families no previous statistic touched. That is a sharpened target, not a decode.
* **The unit-0 / unit-1 send words** (`C64.5.A2.000` at 48, `C64.6.A2.007` at 56 — identical
  except `class4`) remain INFERRED as the send.
* **The cursor re-base word is not identified** (§5.2). Two candidates, no test run.
* **Nothing here was executed.** The core is still disabled; this is a trace derived from a
  measured program image and an established control-flow model, not an observation of a running
  datapath. See §7.

---

## 7. What this instrument is blind to

* **"Exactly once per frame" depends on there being no repeat instruction.** The evidence is
  strong (two exhaustive branch-field scans negative, bodies demonstrably unrolled, a 2-deep
  stack, a cycle budget of only ~2 cycles/word) but the CDJ-500 pin table does name loop
  counters **LC1–LC3**, and 125 families on the path are undecoded. If one of them is a repeat,
  the word counts here are **lower bounds** on executions. The cycle budget bounds the damage:
  at 1.74–2.21 cycles/word there is no room for any loop of consequence.
* **`COND` is unmodelled.** The pin table says instructions can be conditional on RQ1–RQ3. If
  any word on the path is predicated, "executes" and "has an effect" are not the same thing.
  No conditional encoding has ever been found (`-headerdecode.md` §7.4).
* **One capture, one boot, one effect pair.** The epilogue has only ever been observed uploaded
  once. If some effect selection replaces the epilogue rather than patching two words, §1's
  ending changes.
* **The unit-0 body is the only thing effect selection changes here.** Four programs were traced
  (COMPRESSOR, NO OPERATION, CHORUS, PARAMETRIC EQ). The other 34 images differ only in the
  middle section, so the *shape* of every frame is the same; the family sets are not.
* **The `cur` column is printed under a rule §5.2 shows is wrong.** It is there to expose the
  breakage, not to be believed.

---

## 8. Where decoding should go next, ranked by what blocks audio

Ranked by *position on the critical path*, not by corpus frequency — which is the whole point of
this note. Frequencies below are executions in the **through frame** (265 words).

| # | target | per-frame | why it blocks audio |
|---|---|---:|---|
| 1 | **the input stage**, I-RAM 0..11 — `092.2.**.20D`, `084.2.**.680`, `012.2.**.1CE`, `204.2.**.1CE`, `202.A.**.448`, `400.A.**.419`, `090.A.**.1C8`, `084.2.**.1C0`, `012.2.**.1D5`, `282.A.**.417`, `400.2.**.447` | 12 | nothing downstream means anything until a sample enters. 11 of these 12 families exist **only** here |
| 2 | **the output stage**, I-RAM 60..82 — especially the patched pair `C40/C41 . ** . 445/446` and `2A7.9.**.1C3`, `200.1.**.1C1`, `980.5.**.402`, `2A6.1.**.0C7`, `859.0.**.822`, `A3C.D.**.287`, `C00.A.**.407` | 23 | the only place a result can leave the chip, and the only place the host controls a level |
| 3 | **`880.1.**` delay DRAM** — `2D4`(9) `655`(9) `64B`(5) `2D5`(3) `2DA`(3) `00B`(2) `2D9`(2) `000` `40B` `40E` | 36 | 13 % of every frame; the delay memory *is* the reverb/chorus/delay engine. Its current reading is wrong (§6.3) |
| 4 | **the coefficient re-base** — the register-load family `801/809/80B/859 . 0 . NN . {821,822,825,827,839}`, 11 words on the path (I-RAM 38, 42, 43, 44, 50, 51, 52, 62, 69, 77 and NO OPERATION body word 18) of which only the three `.821` are decoded | 11 | without it every coefficient address after the first unit boundary is wrong (§5.2) |
| 5 | **the reverb's own 6 hot families** — `000.2.**.419`, `012.2.**.680`, `102.A.**.64B`, `104.2.**.000`, `880.1.**.2D4`, `880.1.**.655`, 9 executions each | 54 | 20 % of the frame in six families, in the one body that runs in **every** frame, in the one algorithm already solved to the bit — the best decoded-algorithm-to-unknown-opcode leverage in the corpus |
| 6 | **`000.2.**.407` / `212.2.**.419` / `212.2.**.000` / `000.2.**.40E`** | 8/5/4/4 | the generic class-2 store/route words, present in both bodies and every program |
| 7 | the `C64.5`/`C64.6` send twin, the class-8 word `800.8.0C.000`, `010.9.**.20C` | 1 each | one word each, but each is a whole stage (send, post-sum, unit-1 variant of a class-A word) |

Not on this list, and deliberately: `212.2` vs `212.A`, the `0x415` group and the table-lookup
triple — the current worklist's top three (`-core-draft.md` §6). They are frequent in the corpus
and real, but they are *inside* effect bodies. Decoding all three still yields **silence**,
because nothing would get a sample into or out of the chip.

**The single cheapest high-value experiment this note points at:** the 65 scaffolding-only
families are exactly the words the Sub CPU *builds* — the header and epilogue are uploaded from
Sub CPU ROM 0x01E496 / 0x01E63C, and the two patched words are written by code that computes a
level from a UI parameter. That writer is in the dumped Sub CPU ROM and has not been read.
Proving by construction what the host puts into I-RAM 64 and 71 would decode the output stage
the same way `LABEL_0387E6` decoded `ldptr` — and it needs no hardware, no datasheet and no
running DSP.

---

## 9. Coverage

Recomputed the same scoped way as every note in this series: **18.3 % (545 / 2974) — unchanged.**
This pass decoded **no** word. What it produced instead is a different denominator: on the
**through frame's 265 words**, **29 are decoded (10.9 %)**; on the **83 scaffolding words that
carry the audio, 3 (3.6 %)**. Those are the numbers that predict whether sound can come out, and
they are both worse than the corpus figure. Saying so is the point.

Tool: `tools/kn5000_dsp_perframe.py`. Fresh capture verified byte-identical to
`notes/data/kn5000_dsp1_upload_coldboot.txt`.
