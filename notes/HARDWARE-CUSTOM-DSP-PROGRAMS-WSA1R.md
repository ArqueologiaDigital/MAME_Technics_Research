# Running CUSTOM µPD6383 microcode on the real SX-WSA1R

**Third document in the hardware set.** `HARDWARE-QUESTIONS-PENDING-FELIPE.md` is parked (KN5000
in storage); `HARDWARE-EXPERIMENTS-WSA1R.md` is live but *passive* — it measures what the stock
firmware already does. This one is the active version: **if we can put our own microcode into
IC30, the decode stops being inference.**

Why it matters more than everything else in the set: an audio measurement sees a program's
*output*. A custom program lets us **make one unknown word's effect audible on purpose** — set a
known machine state, execute exactly one word under test, route the result to the output, and read
the answer off a scope or a WAV. That reaches blocks no audio experiment can, including the
**bit-11 family (169 words)**, which is control words and otherwise invisible.

⚠ **Read §A0 before any hardware work.** Nothing here is worth risking the instrument for.

---

# ⛔ STATUS AND STANDING DECISIONS — read this first

## ★★★ REVERSED, 2026-09-14 (same day): **IMPLEMENT THE CUSTOM ROM.**

Felipe set the goal *"implement the custom rom"*. **§A5 is now authorised work** and this document
is a work order again. The superseded decision is kept immediately below, because this file promised
that a change would be recorded here in writing with a date, and because the reasoning for caution
still governs *how* it is built — emulator first, originals preserved, additive by construction.

⇒ Build status and the implementation log live in **`WSA1R-SYSEX-MONITOR-BUILD.md`**.

### ~~Superseded: Felipe, 2026-09-14 — DO NOT IMPLEMENT THE CUSTOM ROM CODE~~

~~This document is a design record, not a work order. The SysEx debug monitor of §A5 is written
down so the reasoning is not lost and so it can be picked up deliberately later — it is not to be
built, and no session should start writing monitor code, patching a ROM image, or preparing a burn
on the strength of this file.~~ **Superseded by the goal above the same day.**

| item | status |
|---|---|
| Program ROMs socketed (IC12/13/21/28) | ✅ **CONFIRMED** by Felipe, 2026-09-14 |
| §A1.0 — dump the four sockets, verify hashes | **open, zero risk, do this first** *(Felipe)* |
| Is IC22 (`AM29F400T` flash) socketed? | **open question** *(Felipe)* |
| Are any wave mask ROMs socketed? | **open question** *(Felipe)* |
| ROM package / exact markings | open, not a blocker *(Felipe)* |
| Schematic: are GF1–3 / RQ1–3 (pins 83–88) brought to a CPU port? | **open question** *(Felipe)* |
| §A3 — find the body-upload trigger | open, analysis only *(mine)* |
| §A4 — decode the SysEx ring consumer at `0x601646` | open, analysis only *(mine)* |
| §A5 — build the monitor | ★ **AUTHORISED 2026-09-14** — see `WSA1R-SYSEX-MONITOR-BUILD.md` |
| §A1 — burn and install a ROM | open, *after* A5 is proven in MAME |
| Part B — the probe experiments | unblocked once A5 runs |

★ **What is still live and needs no ROM work at all:** §A1.0 (dumping, which is pure data
recovery), the two schematic/socket questions, §A3 and §A4 (both pure analysis of ROMs we already
have), and **everything in `HARDWARE-EXPERIMENTS-WSA1R.md`** — the eight passive audio experiments,
which need nothing but a MIDI cable, an audio interface and the stock instrument.

## What a reader needs to know, in one paragraph

The µPD6383's microcode is 80.8 % decoded (**1397 undecoded of 7273 pooled words**) and every large
remaining block is shut *because the ROMs do not contain the discriminating evidence*. Real hardware
could supply it three ways, in rising order of power and of intrusiveness: **passive audio
measurement** (the other document — live, no risk); **triggering programs the firmware already has
but never uploads** (§A3 — analysis only); and **running our own microcode** (§A1/§A5 — needs a
burned ROM, and is *not* being pursued). This file documents the third so that the option is
understood rather than rediscovered.

---

# PART A — how custom microcode could get in

## A0 — What the firmware actually does, measured

Established, and it constrains every route below:

* **IC30 is the program DSP; IC5/IC6 are coefficient DSPs** with no I-RAM at all
  (`FINDINGS-dsp-runtime-effect-uploads.md`).
* **IC30's I-RAM is written exactly once, at boot**: 630 write events, words **48…110** — i.e. a
  `01 00 30` load of the 63-word resident kernel, filling I-RAM `0x30…0x6E`. Under every trigger
  tried since (per-effect change, group toggle, 3-unit combi, preamble-latch clear) the count of
  further I-RAM writes is **0**.
* **Only 45 of the 918 distinct static corpus words are ever resident**, and all 45 are the kernel.
  The other ~873 are real programs that the hardware, as shipped, never executes.
* The upload container is fully decoded: a record is `01 UU AA` — command, unit, **load address** —
  followed by 5-byte microwords, emitted by `P7Stream_Run`'s op-3 arm at `0xF9AAFB`.
* The pool holds **57 command-01 loads at address 0x6E**: the per-effect bodies
  (`PoolDir_Records` field +12). **0x6E is exactly where the kernel's load ends**, so the kernel is
  built to be followed by a body at `0x6E` — and that body is never sent.

★ **That last point is the insertion point.** We do not need to displace the kernel. The machine
already expects a program at `0x6E` and never puts one there.

## A5 — ★★★★★ A CUSTOM SysEx DEBUG MONITOR IN ROM — Felipe's proposal, and it dominates A1

**Burn once, then iterate over MIDI forever.** This is the right architecture and it supersedes A1
as the *goal*; A1 becomes merely the delivery mechanism for it.

Why it dominates every other route:

* **One burn, unlimited experiments.** A1 as written needs a re-burn per probe program. A monitor
  needs one, ever.
* **Exact integers, not analogue levels.** Results come back as bytes over MIDI instead of DC
  levels through a DAC — no measurement error, no gain staging, no `notes.txt`.
* **Milliseconds per probe, not a 60-second recording.** Which changes the *kind* of work possible:
  a script can walk **all ~321 distinct undecoded word shapes** automatically. 1397 undecoded words
  stops being a hand-decode and becomes a sweep.

### The CPU split, stated honestly

MIDI is on **CPU 1** (`MIDI_RX_Byte`, `0xFA5496`, prom_a). The DSP host port is on **CPU 2**
(`P7Stream_Run`, `0xF9A646`, prom_c). So a SysEx→DSP path must cross the inter-processor link.

* **(ii) preferred — patch prom_a only, and reuse the link primitive that already exists.** The
  flash download path already does exactly "CPU 1 pushes arbitrary bytes into CPU 2's 64 KiB RAM
  staging buffer at `0x00010000`" (§A2). If our handler borrows that, the *only* prom_c-side
  addition is "run `P7Stream_Run` on the buffer instead of burning it" — a handful of bytes.
* **(i) fallback — patch both ROMs.** More capable, two chips to socket.

### Where the code goes — measured, not guessed

`FINDINGS-prom_a-remote-flash.md` §2 documents four modules in prom_a delimited by the ROM's own
padding, **uniform `0x0E` (RET), verified byte by byte**, each running to the next boundary:

| module | pad range | free bytes |
|---|---|---:|
| `0xFB2000` | `0xFB8CA6-0xFB8FFF` | 858 |
| **`0xFB9000`** | **`0xFBA236-0xFBABFF`** | **2 506** |
| `0xFBAC00` | `0xFBB42E-0xFBB7FF` | 978 |
| `0xFBB800` | `0xFBFFD4-0xFBFFFF` | 44 |

**2 506 contiguous unused bytes is ample for a monitor.** Hook it by patching one call in the
SysEx path; if no SysEx of ours arrives, the machine is bit-for-bit stock.

### The protocol — keep it dumb, length-prefixed and checksummed

| command | does | notes |
|---|---|---|
| `IDENT` | returns monitor version + build hash | so we always know what is running |
| `LOAD addr, words[]` | writes I-RAM | wraps the native `01 UU AA` container |
| `POKE space, addr, val` | C-RAM / D-RAM-reg / descriptor | the three write paths are already decoded — tags `0x26`/`0x4C`/`0x15` |
| `RUN n` | let the DSP run *n* frames, then report | bounded; never an unbounded spin |
| `RQ set` | host-writes RQ1–3 | ★ see below |
| `GF read` | host-reads GF1–3 | ★ see below |
| `DUMP addr, len` | reads CPU 2 RAM back | anything CPU 2 can see, we can see |

Every message carries a length and a checksum; every reply echoes the command and a status byte.

### ★★★★★ The two host-side lines, and why they are self-bootstrapping

This is the part of your idea that reaches further than I had realised. `upd6383.h` records, from
the **CDJ-500 pin table** (pins 83–88), that the chip has:

* **RQ1–RQ3** — *host-written*, and **testable by an instruction's COND field**
* **GF1–GF3** — *set by instructions*, and **host-readable**

…followed by the admission that matters: *"neither the COND field nor the instructions that touch
GF have been located, so these are storage only."* Both are unlocatable from ROM alone — and a
monitor locates them **by search**:

* **RQ → finds the COND field.** RQ is ours to set. Load a program that branches, sweep RQ across
  its 8 values, and observe which words change behaviour. **That locates the conditional field of
  the instruction word** — an ISA discovery no static analysis or audio measurement can reach.
* **GF → becomes a digital output port.** Brute-force candidate words: load a probe containing
  one, run, read GF. **The word that moves GF is the GF-setting instruction.** Once found, every
  probe in Part B reports its answer as bits instead of through the DAC.

⚠ **Check this first, and it is a schematic question:** does the WSA1R board actually route GF1–3
and RQ1–3 to a CPU-readable/writable port? Neither MAME driver wires them, so nobody here knows.
If the board leaves them unconnected, readback falls back to Part B's audio encoding — the monitor
is still worth it, GF is an **upgrade, not a prerequisite**.

### Risk, and how it is contained

* **Additive by construction:** lives in padding, hooks one call, stock behaviour without our
  messages.
* **Emulator first:** MAME runs both ROMs and has the I-RAM write-tap, so the whole monitor —
  protocol included — is debugged in emulation before a chip is burned.
* ⚠ **The one real hazard:** a defect in the handler could hang CPU 1's MIDI interrupt and the
  machine would appear dead. Mitigations, non-negotiable: hook as late in the path as possible,
  bound every loop, and never block waiting on CPU 2.
* Originals stay in a drawer (§A1 step 2).

### ⚠ A5b — the chip's own emulator-mode pins: noted, and NOT recommended

The CDJ-500 pin table calls IC311 pins 13/14 (`Fs-RST`, `Fs-MASK`) **emulator-mode overrides**,
"pull up in regular modes", and on the KN5000 both are strapped to `+5D` — which is why the
per-frame PC restart cannot be inhibited there. A chip-level emulator mode able to hold or
single-step the program counter would be a superb probe.

⛔ **But it needs pins driven on a rare instrument's DSP, and I am not recommending it.** Do not cut
traces or lift pins. It is recorded here only so that *if* the WSA1R schematic happens to bring
those pins to a jumper or a pull-up resistor, we know what they are.

## A1 — ★★★★ Replace IC28 (`prom_c`) with a burned, socketed equivalent

**The delivery mechanism for A5, and on its own the only fully specifiable route today.**

The DSP stream pool lives in `prom_c` = **`qsigcwsa1cx.ic28`, 512 KiB**
(`prom_c/p7/p7_stream_pool.s`). Patch a stream there and the boot upload carries our words into
IC30.

**Design:** leave the boot kernel byte-identical and **append a `01 00 6E` record** carrying the
probe body, so the machine boots and sounds exactly as before except at `0x6E`. That is the
lowest-risk possible edit — it fills a slot the firmware already leaves empty.

### ★★★★★ ANSWERED 2026-09-14: **the program ROMs are SOCKETED** (Felipe)

That removes the single biggest obstacle in this file. No desoldering, no socket to fit, no
irreversible board work — the chips come out, a burned copy goes in, and the original goes back
whenever we like. **A1 is on the table, and with it A5.**

Still to confirm, but none of it is a blocker any more:

1. **The package**, so the programmer adapter is right — 512 KiB byte-wide is almost always
   **DIP-32**, but confirm by counting pins.
2. **The exact marking** on IC28 (and IC12/IC13/IC21), in case it says anything beyond
   `QSIGCWSA1CX`.
3. **Is IC22 socketed too?** That is the `AM29F400T` flash, and it is `NO_DUMP` in the driver —
   see §A1.0.

### ★ A1.0 — do this first, and it costs nothing: DUMP the sockets

Now that they lift out, the zero-risk first step is to **read all four program ROMs and check them
against the hashes the project already has**:

| socket | file | CRC32 | SHA1 |
|---|---|---|---|
| IC12 | `qsigcwsa1ax.ic12` | `5f34af46` | `90a2369f8e4d2fcdf26875272267624b07bc200d` |
| IC13 | `qsigcwsa1bx.ic13` | `f3f84441` | `93adec2a04b7d93a2ec2bfb059227ff3959906e0` |
| IC28 | `qsigcwsa1cx.ic28` | `855c8ac4` | `9b2911e4b21a08d9744b91844630489f54dde856` |
| IC21 | `qsigcwsa1dx.ic21` | `735ae465` | `82df50816c20cd8f2d29551326d2633e7791f306` |

**Why this matters more than it looks.** It is not about the data — we have it. It **validates your
reader, adapter and settings against a known-good answer before anything is ever written.** Four
matching hashes means the toolchain is trustworthy; a mismatch means stop, and we find out why on a
read instead of on a burn.

★ **And two things that would be genuinely new dumps, if those chips are socketed too:**

* **IC22, the `AM29F400T` flash (512 KiB) — `NO_DUMP`.** Nobody knows what it holds. It is the
  target of the whole flash-download path in §A2, so its contents decide whether that route can
  ever reach DSP microcode. Dumping it answers a question this project cannot otherwise touch.
* **The six 16 Mbit wave mask ROMs** (`ic43/44/45/47/48/49`) — all `NO_DUMP`, and the reason the
  WSA1R emulation has **no audio at all**. Almost certainly soldered surface-mount, so probably not
  available — but if any one of them is in a socket, say so, because that is a far bigger prize
  than anything in this document.

**Drop-in candidates** — 4 Mbit byte-wide 5 V parts:

| part | type | why |
|---|---|---|
| **SST39SF040** | flash, 5 V | ★ preferred — **rewritable in seconds**, no UV eraser, iterate freely |
| **AM29F040B** | flash, 5 V | same, widely available |
| 27C040 / 27C4001 | UV EPROM | works, but 20 min under UV per iteration |
| 27C040 OTP | one-time | ⛔ avoid — one mistake per chip |

⚠ Verify pinout against the original before anything: 4 Mbit DIP-32 is *usually* consistent, but
`/OE`, `/CE` and the `A18` position must be checked, and the board may drive `/OE` in a way an
EPROM tolerates and a flash does not. ★ With sockets this is cheap to get wrong safely — a
mismatched part simply will not work, and the original goes straight back in.

**The safety procedure, in order — do not reorder it:**

1. **Read the originals first** and check every dump against the hashes in §A1.0. If a read does
   not match, stop — the reader or the adapter is wrong, and everything after depends on this.
2. **Keep the original chips.** They are socketed, so experiments run on burned copies and the
   originals go back in whenever you want the instrument stock again.
3. ★ **Test every image in MAME first.** The emulator runs this exact ROM, so a patched image can be
   booted, and the DSP's I-RAM write-tap will show whether our words actually land at `0x6E`. **No
   image goes into the hardware until it has been observed loading correctly in emulation.** This is
   the single biggest advantage we have and it makes the hardware step nearly risk-free.
4. Burn, verify by read-back, install, listen.

**Worst case if the microcode is wrong:** silence, noise, or a stuck effect. The DSP is downstream
of both CPUs and cannot prevent the machine booting. **Worst case if the *image* is wrong** (a
mis-sized file, a bad offset): the machine may not boot — which is why step 1 and step 3 exist, and
why the original chip stays in a drawer rather than in the bin.

## A2 — ★★★ The flash download path — official, no soldering, transport not yet identified

There is a **complete flash-programming driver in CPU 2's ROM**, and the inter-processor link is
its download channel (`FINDINGS-prom_c-flash.md`, 16 routines at `0xFC856C-0xFC89C4`):

```
   Flash_ReadSectorToBuffer -> Flash_SectorErase -> Flash_SectorBlankCheck
        -> Flash_ProgramSectorFromBuffer / Flash_ProgramSlice1K -> ack (link cmd 0xE6)
```

…targeting a **512 KiB flash at `0x00E80000`** (the `AM29F400T` at **IC22**, currently `NO_DUMP`)
through a **64 KiB RAM staging buffer at `0x00010000`**, driven by three deferred jobs in
`Link_ServiceTask` gated on bits 5/6/7 of `0x00852C`/`0x00852A`. CPU 1 can also **read the image
back**, streaming it in 8 KiB blocks (`Remote_E80000_Read32Blocks`, `FINDINGS-prom_a-remote-flash.md`).

So a factory data-download mechanism exists and is understood **on CPU 2's side**. Two things are
not:

* ⛔ **What feeds CPU 1.** MIDI SysEx? A service jig? Disk? Unknown. Until that is decoded I cannot
  tell you what to send.
* ⛔ **Whether the DSP pool is reachable this way at all.** The pool is in *mask ROM* IC28; the
  flash is a different device at a different address. Whether anything in the P7 path consults the
  flash is **unknown**. It may be that this route can never touch DSP microcode.

**⇒ This is my work, not yours:** decode the SysEx ring consumer (below) and the CPU-1 side of the
link jobs, and find out what IC22 holds. Until then A2 is a promising unknown, not a plan.

## A3 — ★★★★ Trigger the 57 bodies that are already in ROM — zero hardware risk

The 57 `01 UU 6E` body records exist, are opcode-framed, and the emitter is identified
(`P7Stream_Run` op-3 arm, `0xF9AAFB`). What is unpinned is **which caller feeds
`PoolDir_Records[idx]+12`** — the per-effect path feeds `+0`/`+8` (coefficients) and the group path
feeds a fixed table.

If that trigger is found, **873 static words start executing on real silicon** with no modification
to anything. Every experiment in `HARDWARE-EXPERIMENTS-WSA1R.md` becomes far more informative,
because the effects would run their real bodies instead of the kernel alone.

**⇒ Also my work** (disassembly + emulator), and it is the cheapest item in this file. It is worth
doing *before* A1, because it may make A1 unnecessary for several experiments.

## A4 — ⛔ SysEx as a direct microcode loader — not specifiable today

The MIDI parser accepts **two** identifiers, `0x7E` (Universal Non-Real Time) and `0x50` (a
manufacturer ID), sets "accepted" only for those, and appends each accepted byte to a **ring buffer
at `0x601646`** via `T_Ring601646_Put` (`0xF41E3C`). **The ring's consumer is undecoded.**

So: the machine certainly has a SysEx command set, and I cannot yet name one command. Asking you to
send speculative bytes to a rare instrument would be exactly the wrong trade. What *is* safe and
useful now is the **capture** in the other document (`SYSEX BULK DUMP` from the panel).

⇒ Decoding that ring consumer is the prerequisite for the version of this you actually want, and
it is the task most likely to make A1's soldering unnecessary.

---

# PART B — the experiments custom microcode would enable

The pattern is the same throughout, and it is what makes this so much stronger than listening:

> **Set a known state → execute exactly ONE word under test → route the affected register to the
> output → read the answer as a DC level or a waveform.**

Because we author the whole program, internal registers become *observable*. That is the
instrument the project has never had.

## Harness rules (these are not optional)

* **A beacon first.** Every probe program begins by emitting a recognisable pattern — e.g. a
  square wave at a known rate. If the beacon is absent, the program did not run, and we must never
  confuse that with "the word under test did nothing". This is RULE 13 for microcode.
* **A null probe.** Ship one program identical to the probe but with the word under test replaced
  by a known no-op. Every reading is a *difference* from that.
* **One word per program.** Not two. The whole point is isolation.
* **Emulator first, always.** Each image is booted in MAME with the I-RAM write-tap before it
  goes near the hardware.
* **Use only proven-executed words for the harness itself** — the 45 resident kernel words are the
  ones known to work on real silicon; `runtime-resident-iram-words.txt` is that list.

## B1 — ★★★★★ The bit-11 family — 169 words, unreachable any other way

The largest single open block, and the one `HARDWARE-EXPERIMENTS-WSA1R.md` explicitly cannot touch.
Nine shapes: `C63` ×99, `8BC` ×49, `822` ×7, `839` ×4, and `827`/`864`/`921`/`C62`/`F22` ×2.

Static analysis has taken this as far as it goes: the family decomposes as
`lo_sel = lo12 & 0xFF` and `lo_mid = (lo12 >> 8) & 7`, filling **11 cells of a possible 1024**,
with two minimal pairs; `169/169` are in a characterised addressing mode and `158/169` carry an
anchored accumulator function. **The only thing unknown is what the alternate `lo12` opcode
does.**

**Probe:** write distinguishable constants into every register a candidate reading could touch
(pointer, cursor, the register file, tempA/tempB), execute one bit-11 word, then read each
candidate back to the output in turn. **Whichever register changed, and to what, is the answer** —
directly, with no oracle and no inference.

⇒ If this works, it is +169 words and it closes the largest block in the project.

## B2 — ★★★★★ `f31` 3…7 — 189 words, and the cleanest possible decode

`f31` is `hi12[3:1]`, the **accumulator function**. Values 0/1/2 are anchored as LOAD/ADD/HOLD;
3…7 are unknown, and §149 closed the route because *"every anchored criterion is blind to the axis
by construction"*.

**Probe:** load the accumulator with a known constant, execute one word whose `f31` is 3 (then 4,
5, 6, 7) with a known operand on the bus, and output the accumulator. Each `f31` value's arithmetic
becomes a **measured function of two known inputs**. Vary the operand across a few values and the
function is pinned, not guessed.

⇒ This is the highest words-per-effort item in the file: one harness, five programs, 189 words.

## B3 — ★★★★ `SRC 0x11` — 139 words, breaking a dependency cycle by construction

`SRC 0x11` is a documented **dependency cycle**: the candidate readings (ACCB, `mem[ptr]`, …) each
require something the others settle.

**Probe:** put a *different, recognisable* constant in each candidate source — accb, `mem[ptr]`,
tempA, tempB — then execute one `SRC 0x11` word and output the result. **The constant that comes
out names the source.** A cycle only exists while the sources cannot be distinguished; here we
choose them.

## B4 — ★★★★ The class-6 table index — 171 words, six refuted candidates at once

The idiom reads a 24-entry table in the register file at `0x1D`; the table's contents are recovered
but **not its index**, and six candidate index forms were built and all six refused. §179 also
found the first eight entries repeated after the 24 — the signature of a *windowed* read.

**Probe:** put a slow ramp into each candidate index source in turn, execute the class-6 word, and
output the result. **The source that makes the output trace the known sine is the index.** And
sweeping the ramp finely shows whether consecutive entries are stepped or interpolated — settling
the wrap-guard question the LFO recording (E1) can only infer.

## B5 — ★★★ The waveshaper's 40-vs-32 contradiction

`addr8` at the waveshaper reads **40** entries; the register-file window holds **32**
(`0x1D…0x3C`). Forty do not fit in thirty-two.

**Probe:** a program that reads register-file entries `0x1D…0x4C` in sequence and outputs each.
**The output is the table.** It settles the entry count, the wrap behaviour past 32, and whether
`addr8` is a count at all — a question static analysis has argued both ways.

## B6 — ★★★ Addressing modes 3…6, and mode 4's missing second witness

Modes 0/1/2 are characterised; 3/4/5/6 are not, and **mode 4 is 99 words with exactly one witness
and "no replication available as the question is posed"**.

**Probe:** fill D-RAM with a marker pattern where every cell holds its own address, set the pointer
to a known value, execute one word in the mode under test, then read `mem[ptr]` out. **The marker
that emerges is the address the mode computed.** This converts addressing from inference to
arithmetic, for every mode, in one harness.

## B7 — ★★ The delay arena's real organisation

Same marker technique aimed at the delay RAM rather than D-RAM: write known markers, read with each
candidate delay-addressing form, and the marker identifies the address. This is the internal
counterpart of E2's external delay-time measurement, and together they'd pin the arena from both
sides — including the RAM organisation that `STRATEGIC-REVIEW` item **X1** wants a datasheet for.

## B8 — ★★ ACT hapaxes and the remaining action codes

`ACT 0x0B` (159 words, three criteria already measured blind), plus `0x1A` ×32, `0x1B` ×29,
`0x1D` ×16, and the hapaxes `0x11` ×4, `0x17` ×2, `0x16` ×1. Rare in the corpus, so statistics will
never settle them — but a probe does not need them to be common. Same pattern: known state, one
word, read every candidate destination.

---

## Order of work — ★ RESUMED 2026-09-14

1. **A3** — find the body trigger. No hardware, no risk, and may deliver 873 executing words on its
   own. *(mine)*
2. **A4/A2** — decode the SysEx ring consumer and the CPU-1 link side. Either could let **A5** ride
   an *existing* command instead of a new ROM, which would remove the burn entirely. *(mine)*
3. ✅ **Sockets: ANSWERED — the program ROMs are socketed.** So the remaining asks of you are
   **A1.0** (dump all four and check the hashes — this validates your toolchain before anything is
   written, and tells us whether IC22 and the wave ROMs are reachable too) and the schematic
   question: does it bring the DSP's **GF1–3 / RQ1–3** (pins 83–88) to a CPU port or to a
   jumper/pull-up? That one decides whether the monitor's readback is digital or has to go through
   the DAC.
4. ★ **A5, built and debugged entirely in MAME** — monitor, protocol and probe harness. IN
   PROGRESS; log in `WSA1R-SYSEX-MONITOR-BUILD.md`.
5. **A1** — burn and install, only once A5 runs correctly in emulation.
6. **B2 → B1 → B3 → B4** — `f31` is the most words per program, bit-11 is the largest block,
   `SRC 0x11` breaks a cycle, and the class-6 index closes the oldest question. ★ With A5 in place
   these would stop being one-off experiments and become a **sweep over all ~321 distinct undecoded
   shapes** — which is what makes A5 worth documenting even unbuilt. Kept as design.

⚠ **The honest summary of A:** **A5 is the right target** — a debug monitor turns the whole
remaining decode into an automatable sweep, and it is the only route that can locate the COND field
and the GF-setting instruction, because both are host-side lines invisible to ROM analysis. It needs
a delivery mechanism, and today that is **A1** (a socket). **A3** and **A4** are cheap, are mine, and
either could deliver A5 over an existing path with no burn at all. Part B is worth the trouble
whichever wins — the probe designs are identical however the microcode arrives, and only the
*readback* differs: bits over MIDI if the board wires GF, DC levels through the DAC if not.
