# `AVSDRV.SYS` UNPACKED — the 19 uPD6380 microprograms, and their word size

*Continues `kn5000-dsp-avsdrv.md` (the acquisition record — do not edit that one).
Side-quest for the KN5000 effects DSP (NEC uPD6383GF); the uPD6380 is its
PC-98 sibling and `AVSDRV.SYS` is NEC's own driver for it.*

**Result in one line: the `AVSLOAD$` packer is a small custom LZSS with a
1040-byte ring and a 16-bit (11-bit offset / 4-bit length) match token; both
payload images were extracted and verify as valid MZ executables; the uPD6380
driver is `avs_86.exe`; its `INT 0D9h` function loader carries exactly 19
microprograms indexed 00H…12H, and the upload loop divides the byte count by
**three** — the uPD6380 microprogram word is 3 bytes = **24 bits**, NOT the
5-byte/36-bit word of our uPD6383. The two families DIVERGE.**

---

## 1. The depacker (MEASURED, then PROVEN BY CONSTRUCTION)

`AVSDRV.SYS` is an MZ file with a 512-byte header, so **CS:0 == file 0x200**
(cross-checked: the device header's `strategy=0x0976 / interrupt=0x0981` land on
real code at file 0xB76 / 0xB81).

Routines, given as **file offsets**:

| file | role |
|---|---|
| 0x0E75 | command-tail scanner: `/86`, `/cs`, `/??`, `//` |
| 0x10F7 | the `//` path — decompress both images to `avs_86.org` / `avs_cs.org` |
| 0x11FA | **the depacker** |
| 0x12B2 | emit `n` bytes from ring → `ES:DI`, or `INT 21h/AH=40h` in file mode |
| 0x1344 | match copy inside the ring, byte at a time (so overlap works) |
| 0x138D | literal run: `n` bytes of source → ring |
| 0x13F3 | `wrap(x) = (x + 0x410) mod 0x410` ← **ring size 0x410 = 1040 bytes** |
| 0x130D | end test: carry when the normalised `DS:SI` passes the end pointer |
| 0x0F35 | MZ relocation fixer (the resident path only) |

Algorithm:

```
ring[1040] = {0}          # rep stosw ax=0 at 0x120A-0x120C, buffer at CS:0x20
R = 0
while src < src_end:
    if src[0] & 1:                        # MATCH   (flag = LOW BIT, polarity 1)
        t   = u16le(src); src += 2
        n   = (t & 0x001E) >> 1           #  4 bits, 0..15,  NOT biased
        off = (t & 0xFFE0) >> 5           # 11 bits, 0..2047, taken mod 1040
        for i in 0..n-1: ring[(R+i)%1040] = ring[(R-off+i)%1040]
    else:                                 # LITERAL RUN
        n = (src[0] & 0xFE) >> 1; src += 1   # 0..127 literals
        for i in 0..n-1: ring[(R+i)%1040] = src[i];  src += n
    emit ring[R .. R+n)
    R = (R + n) % 1040
```

Answers to the shape questions: window **1040 bytes** (not a power of two — the
modulo is a real `idiv`, which is why this is *not* stock Okumura LZSS and not
LHA); offset/length split **11/4** inside a 16-bit token; flag polarity **bit0
set = match**; buffer initialised to **0x00** (not 0x20); lengths **unbiased**
(a length of 0 is legal and harmless); no end-of-stream marker — the loop is
bounded by a source end pointer. Ruled out: `-lh0-`/`-lh5-` (no LHA member
header anywhere in the payload), and Okumura-style 8-bit flag bytes (the
`AVSDRV$$Ver 5.10` banner survives intact at file 0x1416 inside the packed
region, which an every-8th-byte flag would have interrupted — that was the first
clue that the flag is per-token, not per-eight).

A dead branch at 0x13C3–0x13EB would pad a short literal run with `0x1A`; it is
unreachable (`CX` is always 0 at the `jcxz`).

### 1.1 Where the packed data is

Pointer table at CS:0x85F… (file 0xA5F…), immediately after the 28-byte copy of
the target's MZ header at CS:0x843. Values are linear, CS:0-relative:

| slot | value | file range | content |
|---|---|---|---|
| 0x85F/0x863 | 0x120A / 0x9019 | 0x0140A–0x09219 | `avs_86` body, packed |
| 0x863/0x867 | 0x9019 / 0x936F | 0x09219–0x0956F | `avs_86` MZ header+relocs, packed |
| 0x867/0x86B | 0x936F / 0xDFFB | 0x0956F–0x0E1FB | `avs_cs` body, packed |
| 0x86B/0x86F | 0xDFFB / 0xE32C | 0x0E1FB–0x0E52C | `avs_cs` header+relocs, packed |

0xE52C is exactly the file size (58 668) — a free consistency check.

## 2. The two images — EXTRACTED AND PROVEN

`tools/avsdrv_depack.py AVSDRV.SYS <outdir>` (kept out of the repo, in
`~/compartilhado/pc98_tdb/avsdrv/`):

| file | bytes | sha256 |
|---|---|---|
| `avs_86.exe` | 48 336 | `c87b1ada447d0b247aa63efe4c0b695cad0369c260c39e3478b99a028ab4df32` |
| `avs_cs.exe` | 30 048 | `c81859f97ae9f4d4817c37e0a34ad7a81d70f8e1d3e3767b0cbd94c8f64118c5` |

Proof, not entropy:

* Both start `4D 5A` and the MZ length field reproduces the produced length
  **exactly**: `avs_86` `e_cp=0x5F, e_cblp=0xD0` → 94·512+208 = **48 336**;
  `avs_cs` `e_cp=0x3B, e_cblp=0x160` → 58·512+352 = **30 048**. A wrong
  depacker cannot hit that twice.
* `e_cparhdr = 0x40` in both → 1024-byte header, which is precisely the length
  of the separately-packed "header" chunk. Two independent framings agree.
* Readable strings appear at sane places: `AVSDRV$$Ver 5.10Rev 1.00.` at 0x40A
  of `avs_86`, `Ver 5.20Rev 1.00.` at 0x40A of `avs_cs`, plus in `avs_cs`
  `(C) Copyright NEC Corporation 1986`, `CS version`, `CONFIG.SYS`,
  `AVSDRV [/E] [/F] [/P] [/R]`, `SndIDreg[A460h] = `, `CS4231Idx[0F44h] = `.

### 2.1 ⚠ CORRECTION to the acquisition note's expectation

The task expected `/cs` to be the uPD6380 image. **It is not.** Counting
`MOV DX,imm16` port constants in the *unpacked* images:

| | A460 | A462 | A464 | A466 | A468 | A46A |
|---|---|---|---|---|---|---|
| `avs_86.exe` | 2 | **42** | **29** | 44 | 36 | 14 |
| `avs_cs.exe` | 0 | **0** | **0** | 0 | 5 | 2 |

`avs_cs` is the **CS4231 codec** driver (PC-9801-118 class) and never touches
the DSP command/data ports. **`avs_86.exe` is the uPD6380 driver.**

This also corrects an instrument-blindness in the acquisition note: the
`MOV DX,0A462h` hits it found *in the packed file* (2 of them) were coincidences
in compressed data. The genuine count is 42, and they only become visible after
unpacking. The conclusion ("this is the uPD6380 driver") was right; the
evidence for it was luck.

## 3. `INT 0D9h` and the I-RAM upload loop (MEASURED, `avs_86.exe` file offsets)

`AH = 00h` (`$INITFUNC`, "load a DSP function") — handler at **0x1D4A**:

```
0x1D66   cmp ah,0x13 / jb ok      <-- 19 functions, 00H..12H, exactly the
                                     data book's list.  Anything >=13H rejected.
0x1D8B   [8E8] = function number
0x1D99   copy per-parameter defaults out of the record (descriptor stride 9)
0x1DBB   the loader:
           call 0x3889    ; A462: preserve b7, set b5|b1|b0   (b5 = I-RAM modify)
           call 0x36A0    ; mute
           call 0x1E01    ; fixed 9-word then 22-word warm-up sequence
           si=[rec+8]  cx=[rec+0Ah]  bh=0 ; call 0x1E43     <- block B
           call 0x3858    ; A462: preserve b7, CLEAR b5, set b1|b0
           si=[rec+4]  cx=[rec+6]   bh=0 ; call 0x1E43     <- block A
           call 0x2769    ; re-apply volumes / parameters
```

**The transfer loop, 0x1E43 — the headline evidence:**

```
0x1E50   mov ax,cx        ; cx = BYTE length of the block
0x1E52   xor dx,dx
0x1E54   mov cx,3
0x1E57   div cx           ; ***** words = bytes / 3 *****
0x1E5B   call 0x3729      ; first word (emits the command + start address)
0x1E61   call 0x3751      ; every following word
```

`0x3729` — one word, with the block opener:

```
call 0x38B3        ; A462 <- (in & 0x20) | 0x03      keep b5, b7=0 => COMMAND
call 0x3959        ; poll A462 until (in & 0x48) == 0x08   (handshake)
A464 <- 0x01       ; COMMAND BYTE 01 = "write memory"
call 0x38E1        ; A462 <- (in & 0x20) | 0x83      keep b5, b7=1 => DATA
A464 <- BH         ; START ADDRESS (one byte, word units)
--- 0x3751 (per-word entry) ---
cx = 3 ; three times: wait; lodsb cs:[si]; A464 <- al
inc bh             ; address auto-increments ONE PER 3 BYTES
```

So: **3 bytes are pushed per DSP word**, MSB first, through the data port
`A464h`; the block is opened by command byte **01h** written while `A462h`
bit 7 = 0, followed by a single **byte** start address written with bit 7 = 1;
the address counter then auto-increments once per three bytes. `A462h` bit 5
is *preserved* by every wait/mode helper and therefore selects which memory the
transfer lands in — it is set (`0x3889`) for the first block and cleared
(`0x3858`) for the second. Handshaking is a bounded poll: `0x3959` waits for
`A462h & 0x48 == 0x08`, `0x3925`/`0x393F` wait for `A466h` bit 0 to go 1 then 0
(a frame tick), and all of them fall into an error exit after 65536·1 spins.
Other commands seen on `A464h`: **02h** = write a 16-bit value (byte-swapped and
rotated left 3, 0x3771), **03h** = terminate (0x37CA), **04h** = write a 16-bit
pair at an address (0x37E1), **05h** = read back (0x381F).

Contrast with the KN5000 (`notes/kn5000-dsp-header.md`, `-parameters.md`): there
the uPD6383 is fed over the maincpu's parallel port in **5-byte groups** with the
header giving explicit I-RAM/coefficient word counts. Same idea — a command
byte, an address, then a fixed number of bytes per word, with the count derived
by dividing the byte length — but the divisor is **5 there and 3 here**.

## 4. ★ THE 19 MICROPROGRAMS — and the word size

The record table is a 19-entry word array. Its code segment is based **0x18C0**
bytes into the load module (MEASURED: brute-forcing the base, only 0x18C0 makes
all 19 entries decode to plausible records — every other base gives at most 4).
Record layout:

```
+0x04 offset, +0x06 byte length   MICROPROGRAM  (block A)
+0x08 offset, +0x0A byte length   COEFFICIENT / data image (block B)
+0x0C parameter count
+0x0E..+0x11 parameter slot indices
+0x12.. parameter descriptors, stride 9: +2 default value,
        +6 BYTE address in coefficient RAM -> `div 3` at 0x1FB5 gives the word
```

| № | name | µcode @file | bytes | **words** | coef @file | bytes | words | nparm |
|---|---|---|---|---|---|---|---|---|
| 00H | `$Thru` | 0x04930 | 66 | 22 | 0x04972 | 33 | 11 | 4 |
| 01H | `$Echo` | 0x04993 | 294 | 98 | 0x04AB9 | 84 | 28 | 9 |
| 02H | `$LPF` | 0x04B0D | 207 | 69 | 0x04BDC | 255 | 85 | 6 |
| 03H | `$HPF` | 0x04CDB | 207 | 69 | 0x04DAA | 213 | 71 | 6 |
| 04H | `$Geq` | 0x04E7F | 528 | 176 | 0x0508F | 279 | 93 | 16 |
| 05H | `$Rev` | 0x051A6 | 429 | 143 | 0x05353 | 360 | 120 | 2 |
| 06H | `$Hall` | 0x054BB | 510 | 170 | 0x056B9 | 228 | 76 | 5 |
| 07H | `$Loc` | 0x0579D | 390 | 130 | 0x05923 | 120 | 40 | 3 |
| 08H | `$Adj` | 0x0599B | 147 | 49 | 0x05A2E | 45 | 15 | 8 |
| 09H | `$Pan` | 0x05A5B | 477 | 159 | 0x05C38 | 408 | 136 | 2 |
| 0AH | `$Chor` | **0x06100** | 477 | 159 | 0x062DD | 363 | 121 | 9 |
| 0BH | `$Doubl` | **0x06100** | 477 | 159 | 0x06448 | 363 | 121 | 7 |
| 0CH | `$Flang` | **0x06100** | 477 | 159 | 0x065B3 | 363 | 121 | 10 |
| 0DH | `$Vibrt` | **0x06100** | 477 | 159 | 0x0671E | 363 | 121 | 9 |
| 0EH | `$Ensem` | **0x06100** | 477 | 159 | 0x06889 | 363 | 121 | 14 |
| 0FH | `$Pitch` | 0x069F4 | 519 | 173 | 0x06BFB | 72 | 24 | 2 |
| 10H | `$Surr` | 0x06C43 | 240 | 80 | 0x06D33 | 69 | 23 | 8 |
| 11H | `$Kara` | 0x06D78 | 531 | 177 | 0x06F8B | 111 | 37 | 4 |
| 12H | `$ADPCM` | 0x06FFA | 312 | 104 | 0x07132 | 108 | 36 | 4 |

The blobs are contiguous: file **0x04930 … 0x0719E**, 11 442 bytes, no gaps —
each block ends exactly where the next begins. Extracted to
`~/compartilhado/pc98_tdb/avsdrv/dsp/fnNN_{ucode,coef}.bin` (38 files;
`sha256sum *.bin | sha256sum` = `9fd0c754190587a8fd9e8022eeb78b4ad77845d1f9f81f2640ba91de52b1942a`).

### 4.1 ★★ WORD SIZE = 3 BYTES (24 bits). Evidence:

1. **The upload loop literally divides by three** (`mov cx,3 / div cx` at
   0x1E54, file 0x1E43) and then pushes exactly three bytes per iteration.
   *MEASURED, and it is the only arithmetic in the routine.*
2. **All 38 block lengths are divisible by 3**, with no remainder anywhere
   (66, 33, 294, 84, 207, 255, …, 108). Under a 4- or 5-byte word, 33, 66 and
   207 are impossible. *MEASURED.*
3. **The address counter increments once per three bytes** (`inc bh` after the
   3-byte inner loop), so `bh` is a word address in 3-byte units.
4. **The parameter path independently divides a byte address by 3** to get a
   word address (0x1FB5). A second, unrelated code path, same unit.
5. **The data lays out on a 3-byte grid.** Over the whole coefficient corpus,
   byte 0 of each 3-byte group is `0x20` in **92 %** of words (7 distinct values
   total), while bytes 1–2 take 158/143 distinct values — i.e. a 1-byte tag plus
   a 16-bit payload. Over the microprogram corpus, byte 0 takes 25 values with a
   clear opcode-like distribution (`09` 26 %, `00` 19 %, `03` 15 %, `3F` 5 %,
   `33` 4 %). No such structure appears at stride 4 or 5.

**=> The uPD6380 packs 24-bit words in 3 bytes. Our uPD6383 packs 36-bit words
in 5. The families DIVERGE at the instruction-word level.** The lag-4
autocorrelation hint noted on the KN5000's other DSP is *not* corroborated here
either — the answer is 3, not 4 and not 5.

### 4.2 Two further confirmations that the table is decoded correctly

* The parameter counts match NEC's own data book, function by function:
  `$Thru`=4 (four output levels), `$Rev`=2 (level, time), `$Hall`=5,
  `$Pitch`=2 (L/R pitch), `$Geq`=16 (a graphic EQ). *These were never inputs to
  the decode — they fell out of `rec+0x0C`.*
* `$Chor`, `$Doubl`, `$Flang`, `$Vibrt`, `$Ensem` **share one identical 159-word
  microprogram at 0x06100** and differ only in their coefficient images. The
  data book says exactly this: those five "share a modulated-delay shape"
  (`kn5000-dsp-abv.md` line 257). Independent, and it also settles which block
  is which: block A (`rec+4`) = code, block B (`rec+8`) = data.

### 4.3 First look at the content (MEASURED, not yet decoded)

`$Thru` microprogram, 22 words:

```
380000 034107 09c108 09800d 034100 09800d 000020 034194 09800d 000040
3fe00a 034107 09c108 09800d 034100 09800d 000020 034194 09800d 000040
365a0d 3e6015
```

Visibly two identical 10-word bodies (left and right channel — `$Thru` has four
output levels, two per side) bracketed by `380000` at the head and
`365a0d 3e60xx` at the tail; every block in the corpus is framed the same way,
and `38xxxx` recurs mid-block (e.g. `380030` inside `$Rev`) as an
address/segment set. `$Thru`'s coefficient block is nine copies of `20fffb`
(≈ +1.0 in a 16-bit fraction, i.e. unity gain) between the same brackets.

`$Rev`'s coefficient block contains an obvious smooth table —
`200000 202830 205050 207858 20a028 20c7c0 20ef08 2015f1 …` rising to `20fffb`
and back down — a sine/window LUT.

### 4.4 Cross-corpus comparison with the KN5000 — NEGATIVE, and why

The task's step 5 was conditional on the formats matching. **They do not**, so a
word-level comparison is not meaningful and none was attempted beyond confirming
the divergence:

* uPD6380: 24-bit instruction words; coefficients are a 1-byte tag + **16-bit**
  value. uPD6383 (KN5000): 36-bit words in 5 bytes, signed **Q0.23**
  coefficients. Neither the word width nor the coefficient width matches, so the
  KN5000 markers (`104.2.00.000` all-pass, `880.1.60.*`/`880.1.20.*` external-
  DRAM bracket) cannot appear as-is and do not.
* SPECULATIVE but worth the next pass: the *architectural* idioms should still
  transfer. The 6380 corpus has the same shapes we decoded on the 6383 — a
  bracketed program frame, an implicit cursor (the auto-incrementing `bh`), a
  shared modulated-delay kernel behind chorus/flanger/vibrato/ensemble, and an
  LUT-driven modulator. Decoding the 24-bit opcode field (byte 0: `09`, `03`,
  `00`, `3F`, `33`, `2A`, `34`, `06`, `02`, `0B`, `3C`, `38`, `36`) against the
  known 6383 semantics is the obvious follow-up, and now has a clean 19-program
  corpus with per-program parameter maps to work from.

## 5. Files

* `tools/avsdrv_depack.py` — the depacker + the microprogram extractor.
* NEC binaries stay out of git, in `~/compartilhado/pc98_tdb/avsdrv/`
  (`avs_86.exe`, `avs_cs.exe`, `dsp/fnNN_{ucode,coef}.bin`), hashes above.
