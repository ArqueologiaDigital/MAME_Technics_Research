# NEC uPD6383GF — the C-RAM / D-RAM SPACE SELECTOR, and absolute C-RAM addresses

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-23.
Tool: `tools/kn5000_dsp_spaces.py` (imports `_class2` / `_biquad` / `_params`; **none edited**).
Disassembler change: `src/devices/cpu/upd6383/upd6383d.{cpp,h}` (JOB 1 only).

Two closely-related jobs, both about which of the chip's two on-chip **256×24** RAMs — the
COEFFICIENT RAM (**C-RAM**) and the STATE/DATA RAM (**D-RAM**) — a microword touches.

Claims are tagged **MEASURED**, **INFERRED**, **PROVEN BY CONSTRUCTION**, **SPECULATIVE**,
**FALSIFIED**. §6 is misses/limits. **No audio; the core stays instantiated DISABLED; the
KN5000 driver was not touched; only the DISASSEMBLER was edited (JOB 1).**

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_spaces.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
# sections: job1 label fields hostmap registers verdict
```

---

## Headline

1. **★★ JOB 1 SHIPPED: the disassembler now prints ABSOLUTE C-RAM coefficient addresses.**
   Every CLASS-A word (`class4 == 0xA`) reads one coefficient from C-RAM through the implicit
   cursor. The cursor **base is 0x00** — MEASURED across all 16 swept effects in the captured
   uC-IF stream, which frame every coefficient upload with `801.0.00.821`
   (`-origin-capture.md`) — and it advances **+1 per class-A word**, reset by `801.0.00.021`.
   So a class-A word's coefficient has a **known absolute C-RAM address `0x00 + k`**, and the
   disassembler appends `; C-RAM[0xNN] (coeff, base 0x00 MEASURED)`. **MEASURED.** (§1)
2. **★★★ JOB 2 VERDICT: there is NO encoded space-selector field. The space is
   POINTER-IDENTITY.** A microword does not carry a C-RAM/D-RAM bit, because **no word ever
   names a single C-RAM cell**: C-RAM is reached ONLY through the implicit coefficient cursor
   (no address field, gated by class-A), D-RAM (state) ONLY through the signed-`addr8` data
   pointer, and the external delay RAM ONLY through the `880.1.60/20` bracket. Which space a
   word touches follows entirely from **which addressing mechanism it invokes**. This is
   *Method step 4*'s answer, and it is itself the decode. (§2–§5)
3. **★★ THE LABELLED SET PROVES THE ABSENCE.** From the SOLVED biquad (`-semantics.md`) every
   operand of the EQ section is known. Result: **0 single-cell C-RAM accessors**, and every
   non-cursor cell access is D-RAM state. The selector bit a per-word decode would need has
   **no positive example to fit** — the machine never encodes that choice. (§2)
4. **★★ CROSS-FAMILY CONTROLS HOLD (present AND absence).** PRESENCE: every host coefficient
   address is cursor-reachable (197/197, `-cursor-general.md` §2) — coefficients are ALWAYS
   class-A-consumed, in the biquad AND reverb AND chorus, never single-cell addressed.
   ABSENCE: state is cleared/written ONLY through the `+2`/`000.1` pointer (`-cursor-general.md`
   §5.1). NEGATIVE: no unexplained `hi12` bit (`[9:8]`, `[3:1]`, 7, 6, 5, 0) is pinned to one
   value for D-RAM accesses — none carries C/D information. (§3)
5. **★ THE HOST-SIDE MIRROR: an address is NOT enough to name a space.** In **18 of 38 images**
   the *same* numeric address (e.g. `0x00`) is written as both a C-RAM coefficient and a D-RAM
   state cell — because they are two separate 256-cell RAMs. The space always comes from the
   writer/pointer (`+0` → C-RAM reg `0x821`, `+2` → D-RAM `000.1` pointer), never from the
   number. Exactly the body-side finding, seen from the host. (§4)
6. **Build/validate:** `upd6383d.{cpp,h}` rebuilt clean; `-validate kn5000` and `-validate
   kn7000` both exit 0. The change is confined to `disassemble()`; the device's runtime path
   (`text()` in the trap-log) is byte-for-byte unchanged, so boot and the I-RAM acceptance
   test cannot be affected by construction. Coverage recomputed the scoped way is **unchanged
   at 18.3 %** — no new *word* is decoded; what is added is an absolute, space-tagged address
   on the 822 class-A words. (§5)

---

## 1. JOB 1 — absolute C-RAM coefficient addresses (MEASURED)

The coefficient cursor is a running counter: base **0x00** (MEASURED, `-origin-capture.md`),
**+1 per class-A word** (`-biquad-map.md` §2, `-cursor-general.md` §1 — the loader's bank holds
`class-A + 1` words in 26 of 38 images), reset by `801.0.00.021`. Crucially the advance is per
**class-A** word (`class4 == 0xA`), **not** per bit-23 word: the biquad's class-8 post-sum step
(`804.8.16.415`) carries bit 23 but does **not** consume a coefficient, which is exactly why the
make-up gain still lands on slot `NN+5` (`-semantics.md` §3). Using bit 23 would mis-place it.

The disassembler recovers `k` by scanning **backward** from `pc` in whole 5-byte words to the
nearest `801.0.00.021` (or the buffer start = the per-frame origin, base 0x00), counting class-A
words. This is correct regardless of call order — it does not rely on linear disassembly.

Sample (mirror of the compiled `disassemble()`, algo 39 band 0):

```
0019: ... 000.A.00.1D3   ; C-RAM[0x00]   (b1)
001E: ... 212.A.01.412   ; C-RAM[0x01]   (b0)
0023: ... 202.A.01.1D5   ; C-RAM[0x02]   (b2)     <- decoded form prints `mac (p)+1' + this suffix
0028: ... 202.A.01.1D4   ; C-RAM[0x03]   (-a1)
002D: ... 202.A.00.1D5   ; C-RAM[0x04]   (-a2)
0032: ... 102.2.FF.687   (class 2 -- no C-RAM, a D-RAM store)
0037: ... 804.8.16.415   (class 8 -- FROZEN, no cursor advance)
003C: ... 212.A.FF.407   ; C-RAM[0x05]   (make-up gain = NN+5)   <- class-8 correctly skipped
```

**Validation against the host** (`--job1`): the C-RAM band-start sequence must equal the host's
op-0x70 coefficient bases — a table (`T1`) the microcode never sees. **6 images match band for
band; the 5 that do not are ALL documented phenomena, not cursor errors:**

* **PARAMETRIC EQ** — channel 0 matches `00 06 0C 12 18` exactly; channel 1's C-RAM starts
  correctly **repeat** `00 06 …` (the two channels SHARE coefficients across the rewind), while
  the host's op-0x70 *second* group `64 68 6C 70 74` are the **D-RAM state bases**, not
  coefficients (`-cursor-general.md` §5.2). The C-RAM prediction is right.
* **PEQ+COMPRESSOR / +COMPR+DIST / +COMPR+OVERDR** — off by the known **+4** (non-class-A
  coefficient consumers, `-cursor-general.md` §4).
* **PEQ+OVERDR+DELAY** — the `maxdiff=3` section finder also caught an overdrive tone stage,
  not the 2nd PEQ.

Origin-free control: every image's per-band C-RAM **stride is 6** (six class-A words per biquad
section), matching the host's stride-6 coefficient blocks. **MEASURED.**

## 2. JOB 2 — the labelled set from the SOLVED biquad (MEASURED)

`-semantics.md` §3.1 gives every operand of the EQ section. Tagging each by space:

```
  idx  word         class  reads C-RAM   touches D-RAM   role
  [0]  000.A.00.1D3   A      C-RAM         D-RAM         P=b1*S0 ; latch A<-S0
  [1]  212.A.01.412   A      C-RAM         D-RAM         S0<-x ; acc=P ; P=b0*x
  [2]  202.A.01.1D5   A      C-RAM         D-RAM         acc+=P ; P=b2*S1
  [3]  202.A.01.1D4   A      C-RAM         D-RAM         acc+=P ; P=-a1*S2 ; latch B<-S2
  [4]  202.A.00.1D5   A      C-RAM         D-RAM         acc+=P ; P=-a2*S3
  [5]  102.2.FF.687   2        -           D-RAM         acc+=P ; S3<-latch B
  [6]  804.8.16.415   8        -             -           class 8: post-sum step on acc (no cell)
  [7]  212.A.FF.407   A      C-RAM         D-RAM         S2<-acc ; P=makeup*acc
  [8]  000.2.03.647   2        -           D-RAM         acc<-P ; S1<-latch A
```

**Single-cell C-RAM accessors: 0. Single-cell D-RAM accessors: 2** (`[5]`, `[8]`). Every
class-A word reads one coefficient (C-RAM, cursor) AND one state cell (D-RAM, `mem[ptr]`) — one
operand from each space, nothing to select (`-biquad-map.md` §7). Every non-class-A cell access
is D-RAM. **The labelled set has no single-cell C-RAM example, so there is no positive class for
any selector bit to fit.**

## 3. JOB 2 — every candidate selector field, tested (predict-then-check)

`--fields`, over the 2974-word body corpus:

```
   read a C-RAM coefficient  : 822   (all class-A: bit 23 + mode 2)
   touch a D-RAM state cell  : 2372  (classes 2 and A -- mode 2)
   do BOTH in one word       : 822   (the class-A multiply -- one operand from each space)
   read C-RAM but not class-A :  0    <- a single-cell C-RAM access DOES NOT EXIST
```

So `reads C-RAM ⟺ class-A ⟺ bit 23 + mode 2`, exactly. The candidate mechanisms from the brief:

| candidate | verdict |
|---|---|
| a bit in `hi12` (`[9:8]`, `[3:1]`, 7, 6, 5, 0) | **NOT a selector.** Among the 2372 D-RAM cell accessors every one of these bits still takes BOTH values (bit 0 is constant-0, but that only marks the `0x801` immediate family, carrying no C/D contrast). None is pinned to "this cell is state". |
| the class / MODE (`class4 & 7`) | **This IS the mechanism, not a C/D flag.** Mode 2 = the signed-`addr8` D-RAM data pointer; bit 23 additionally adds the C-RAM cursor read. It selects *which pointer*, and the pointer's space is fixed — see §5. |
| the escape-format pointer loads `801.0.NN.{821,825,827,820,822}` | **This is where the space actually lives** — per-region pointer setup (§4). |

**PREDICTION → CHECK, reported honestly:** the brief predicted an unexplained `hi12` bit might
select C vs D. **That prediction MISSES** — no `hi12` bit does, and it cannot, because there is
no C-RAM single-cell access to contrast against a D-RAM one.

## 4. JOB 2 — the escape registers → spaces (the real selector, at the setup layer)

The host writer's **descriptor field** routes every parameter write to a space (`_params.py`
`OPCODE_EVAL`): **`+0` → the C-RAM coefficient pointer** (writer `0387E6`, the `0x821`
register), **`+2` → the D-RAM state pointer** (writer `038539`/`03846C`, the `000.1` pointer).
Mapped over the escape loads (`-pointer.md`, `-headerdecode.md`, `-cursor-general.md`):

```
  lo12 0x821   C-RAM coeff base 0x00 (host) — AND the header seeds the D-RAM data pointer
               through 0x821 too (0x70/0x50): so 0x821 is a general "load pointer N"; the
               SPACE is the region streamed after it, not the register id.
  000.1.NN.000 D-RAM STATE base (class-1 pointer, writer 038539/03846C, +2): the parameter
               stream clears state through THIS pointer (cursor-general §5.1).
  lo12 0x825   coefficient-bank / external-DRAM register region (0x25; host 0x00/0x1E/0x26).
  lo12 0x827   a second state/parameter pointer (0x6C/0x64 per unit); pointer.md's runner-up.
  lo12 0x822   reverb high delay-block base / unit-1 region (+0x80 base, cursor-general §1.2).
  lo12 0x820   immediate data inside the bit-11 escape — not a pointer load at all.
```

**The host-side mirror (`--hostmap`).** Partitioning every image's `T1` host addresses by
writer-descriptor and looking for a C-address that equals a D-address: **18 of 38 images
collide** (e.g. CHORUS writes both a coefficient and a state cell at `0x00`). Because C-RAM and
D-RAM are separate 256-cell RAMs, the number alone is ambiguous; the space is carried by the
pointer/writer. This is the same fact as the body-side one, from the host.

> **So the "selector" is at the POINTER-SETUP level, and per-word "selection" is which
> pre-loaded pointer register the word's addressing MODE uses** — the cursor (→ C-RAM), the
> signed-`addr8` pointer (→ D-RAM), or the `880` bracket (→ external delay RAM). The word
> encodes the mode; the space is a property of the register that mode drives. **INFERRED
> (strong), PROVEN BY CONSTRUCTION at the host-writer layer.**

## 5. What the disassembler can and cannot honestly print

* **CAN, and now does:** the absolute C-RAM address of every class-A word (§1). That space is
  determined (the cursor) and its base is MEASURED (0x00). 822 class-A words over the body
  corpus gain an absolute, space-tagged coefficient address.
* **CANNOT:** tag a single-operand word `C-RAM[..]` vs `D-RAM[..]` from a field, because the
  machine does not encode that choice (§2–§4). The disassembler therefore prints C-RAM
  absolutes only, and withholds a D-RAM absolute — the state base is the header's per-unit
  `0x70`/`0x6C`, not yet pinned per word (`-addressing.md` §5; the fit still wants an origin
  `0x19` that no header register supplies).

**Coverage.** Recomputed the scoped way (`-hi12.md coverage`): **18.3 % (545/2974), unchanged.**
No new *word* is decoded; JOB 1 adds an *address annotation* to words already counted (the
class-A `mac`/`mulst` forms), and JOB 2's result is a structural fact about the *absence* of a
field, which — per the whole series' discipline — is not laundered into a coverage point.

## 6. Misses, limits, and what remains

* **The `hi12`-bit prediction missed** (§3), reported as prominently as a hit. There is simply
  no C-RAM single-cell access in the corpus for any bit to select.
* **The D-RAM absolute base is still unpinned** (`-addressing.md` §5–§6): the biquad's `+4`
  stride matches the host state block exactly, but the origin that lands it is `0x19`, which is
  none of the header's `0x70`/`0x6C`/`0x25`. Until that one number is closed, no D-RAM absolute
  is emitted. This is the remaining clean addressing question.
* **The compressor's four non-class-A coefficient consumers** (`-cursor-general.md` §4) would,
  if identified, be the first counter-example to "coefficients are class-A only" — they consume
  coefficients (C-RAM) without being class A. They are still not identified; if decoded, they
  would refine "class-A ⟺ C-RAM read" to "class-A OR {those four}". The verdict's *mechanism*
  (space = pointer, not a bit) would stand regardless.
* **All static.** Not one address here was watched on the C-RAM/D-RAM bus. One address-bus
  trace from the enabled core would confirm base 0x00 and the wrap modulus directly.

## 7. Cross-checks to earlier notes

| earlier claim | source | status here |
|---|---|---|
| "possibly nothing selects C-RAM vs D-RAM: one operand from each" | `-biquad-map.md` §7, `-cursor-general.md` §5.1 | **CONFIRMED and SHARPENED** to a verdict: the space is pointer-identity; there is no encoded selector, because no word single-cell-addresses C-RAM (§2–§5) |
| coefficient cursor base is 0x00, +1 per class-A word | `-origin-capture.md`, `-biquad-map.md` §2 | **CARRIED INTO THE DISASSEMBLER** as absolute C-RAM addresses (§1) |
| the disassembler should print absolute addresses "only once the register/space selection is decoded — NOT under a fabricated per-effect origin" | `-origin-capture.md` §"where next" | **DONE for C-RAM** (space IS decoded: the cursor), **withheld for D-RAM** (base still open) |
| bit 23 = cursor-fetch enable | `-axes.md`, `upd6383d.h` | **REFINED**: bit 23 is broader than coefficient-consumption; the cursor advances on the stricter `class4 == 0xA` (bank-size test), which is why class 8 is frozen and the make-up gain stays at `NN+5` (§1) |
| escape loads `801.0.NN.{821,825,827,820,822}` are per-region pointer setups | `-pointer.md`, `-headerdecode.md` | **MAPPED to spaces** and identified as *the* selector, at the setup layer (§4) |
