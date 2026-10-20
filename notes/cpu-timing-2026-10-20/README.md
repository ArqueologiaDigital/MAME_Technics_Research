# The MN10300 core at the instrument's speed (2026-10-20)

Item G22 of `OVERLAY-GAPS.md`. Until now the core charged one cycle per instruction at 32 MHz and nothing for
memory, so code that touches slow memory ran far faster here than on Felipe's KN7000 (Another World runs smoothly
in MAME and slowly on the unit). Felipe counts that as an emulation bug: the emulator has to be trustworthy as the
development environment. The core now runs at 64 MHz with the cycle counts the unit measured, a fetch queue,
instruction and data caches, and per-chip-select bus costs, all in one table:
`src/devices/cpu/mn10300/mn10300_timing.h`. Calibrating it is an edit there.

**Results** (the final binary, md5 `3077b137f86844bbb8515d25c2d19008`, kn7000_mame `cpu-timing`; against the
published one, `48e8493944ac8cc09f0f2d57e5a559a2`, kn7000_mame `262f794`. The runs below used `6d86f03a`, the same but
for three bus registers the firmware never reads, which read back from `3077b137` on, as on the unit; the oracle is
the same bit for bit):

- **64 MHz, confirmed on the unit**: pass 9's ADD is 15.6 ns, one cycle at 64.02 MHz (the 16 MHz crystal x 4, the
  part's "4-fold" mode). The old 32 MHz was a guess that made one cycle per instruction look right for simple code.
- **Pass 9 in this emulator against the unit:** 99 of 109 reliable tests within 3 %, 107 within 10 %; every memory
  test within 1.2 %. Before: everything one cycle at 32 MHz.
- **Pass 8:** 194 calibration samples per tick (unit 197, before 206); 24.33 us per DSP access (24.24; 23.25); the
  firmware's DSP index write 1.67 us (1.69; 1.67).
- **Another World** (its own speed build and figures, kn5000-anotherworld `26aabecb`, in MAME): the intro with the
  overlay 17.0 frames per second (published 38.0), the old blit 2.2 (8.7), the paced lake 25.2 (25.0).
- **The boot** reaches the same screens: on the KN7000 the splash under a second later and the home screen by the
  same 12 s snapshot; all eight machine/BIOS cases identical from 20 s on; no unimplemented opcode.
- **The floppy** needed one driver fix (IRQ1 for a sector's last byte), without which STYLE CONVERT could not load.
- **The gate:** 16 passed, 1 failed (the audio oracle, now `5069aedab573b1c63ef6df7689382bd9`), 1 skipped.
- **Host speed** improves (fewer instructions per emulated second): `-bench 30` 61-65 % against 48-51 % on a loaded
  host.

## Sources

| source                                                               | what it gives                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|----------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| MN1030/MN103S Series Instruction Manual (13250-040E)                 | `kn7000_scratchpad_snapshot/mn103s_manual.pdf`. The MN103002A is its AM31 core (p.2). Cycle counts per instruction (chapter 2, and the appendix pp.160-182) for cache hits and no stall (p.25); the AM31 memory map, cachable/uncachable (p.11); the five-stage pipeline (pp.103-109); load-use stalls (pp.120-121, 128); 8-byte fetch blocks (pp.125-127); LIR for Lcc (p.107). Nothing on wait states, chip selects or the caches' size: "cycle changes in memory space" are in the part's LSI manual, which we do not have (p.25) |
| MN103002A datasheet abstracts (datasheetarchive.com)                 | 4 KB 2-way instruction cache, 4 KB 2-way data cache; 66 MHz in "4-fold" (x4 PLL) mode, 15 ns per instruction                                                                                                                                                                                                                                                                                                                                                                                                                         |
| the firmware (`technics-roms-disasm/kn7000/disasm/program.asm`, 941) | CHCTR (`0x20000070`): 0x30 then 3 at boot (`0x4840FFA6`), bit 7 later (`0x4841009F`); its cache routines (`0x484022E0`, `0x4841015B`-`0x4841021A`) disable with bit 0/1, wait on bit 2/3, invalidate with 4/5, skip the purge when bit 6 (write-through) is set, and purge the data cache by reading `0x28400000` and `0x28401000`, 0x80 lines 0x10 apart: two ways of 128 16-byte lines. The bus set-up (`0x484D7111`) writes MEMCTR0-7 and the DRAM registers                                                                      |
| pass 8 on the unit (`cnv_romdump`, 2026-10-20-dsprate)               | the calibration loop (64 turns of `add -1,d0; bne` and a timer read): 197 per 1 ms tick; the firmware's DSP index write (the re-latch) 1.69 us; 24.24 us per DSP data-port access                                                                                                                                                                                                                                                                                                                                                    |
| pass 9 on the unit (`cnv_romdump`, 2026-10-20-cputime)               | 119 timed tests, decoded in `technics_roms/roms/kn7000/real_dump_v1.3_b893/pass9-check-2026-10-20.txt` (private): ADD = 1 cycle at 64.02 MHz; the instruction classes; loads and stores per region, cached and uncached; the registers as the firmware left them                                                                                                                                                                                                                                                                     |
| upstream MAME, the GNU simulator                                     | nothing: upstream's mn10300 also charges 1 cycle per instruction; the GNU sim (`am33.igen`) has no timing                                                                                                                                                                                                                                                                                                                                                                                                                            |

## The model (`mn10300_timing.h`)

Time is charged in quarter cycles of the 64 MHz clock. Per instruction:

1. **The instruction cache.** On entering a new 16-byte line: a hit is free; a miss fills the line from its chip
   select (the cost below). Uncached code (or the cache off) reads the rest of the line over the bus.
2. **The fetch queue.** 8 bytes, refilled at 2.1 bytes per cycle; an instruction waits until all its bytes are in.
   After a taken jump it holds the target's 8-byte block from the target on, plus what a call or return (4-5
   cycles) fetched in its extra cycles; the next block comes 0.75 cycles later. An untaken Bcc costs 1 cycle and
   2 bytes of fetch. Lcc refills from LIR (the loop's first 4 bytes).
3. **A load-use stall** when the instruction reads a register the previous single load is still writing: until
   2 cycles after a cached load (1 or 2 from elsewhere).
4. **The execute cost**, from the manual, or from the unit where they differ:

| class                                          | manual (AM31)                   | unit [P9]                       | model                                  |
|------------------------------------------------|---------------------------------|---------------------------------|----------------------------------------|
| ALU, mov, ext, shifts, 1-4 byte loads/stores   | 1                               | 1                               | 1                                      |
| imm32/d32/abs32 forms (6 bytes)                | 2                               | 2.75                            | 2 + the fetch queue                    |
| Bcc/bra taken; untaken                         | 3; 1                            | 3; 1.75 in a run                | 3; 1 + 2 bytes of fetch                |
| Lcc taken / untaken; setlb                     | 1 / 2; 1                        | 1 (LBUF)                        | 1 / 2; 1                               |
| jmp d16 / d32 / (An)                           | 2 / 3 / 3                       | 3.5 (d16)                       | 3 / 4 / 3 + the refill                 |
| call d16: n saved registers                    | 2 + n                           | 10 with ret (n=0), 13 (n=4)     | max(5, 4 + n); d32 max(6, 5 + n)       |
| ret / retf / rets / calls                      | max(5,1+n) / max(2,1+n) / 5 / 3 | 5 / 4 / 5 / 4                   | max(5,1+n) / max(4,1+n) / 5 / 4        |
| movm pop / push                                | 1 + n / max(1, n)               | 3.87 / 9 for a pair of 1 / of 4 | max(3, 1 + n) / max(1, words)          |
| mul/mulu, div/divu by operand bytes            | 3-34, 4-38                      | the same                        | the same                               |
| bset/bclr (An), (d8,An); (abs32); btst         | 5; 6; 4-5                       | -                               | the manual                             |
| load-use (next instruction reads the register) | +1 to +2                        | +2 (cached)                     | +2 cached, +1 word / +2 sub-word other |
| udf (the extension unit)                       | "*"                             | -                               | 1, multiplies 2 (GUESS)                |
| interrupt acceptance                           | -                               | -                               | 7 + the two stack writes (GUESS)       |

Data accesses add:

- **On-chip registers:** 7 cycles at `0x34xxxxxx` (INTC, timers, serial; `0x36` ports taken as the same), 3 at
  `0x20`/`0x32` (CHCTR, MEMCTR) [P9 TMBC TMMD ICR MEM0 CHC].
- **The data cache** for 0x00000000-0x1FFFFFFF and 0x40000000-0x7FFFFFFF: write-back, allocating on a write miss
  [P9 RAX4: a store to a new line = a fill + a write-back]. A miss costs its line's fill, plus the dirty victim's
  write-back.
- **Uncached accesses** (0x80000000-0xBFFFFFFF, or the cache off) cost their chip select's time. Stores are posted:
  the next external access waits for them (pass 9's stores, back to back, cost their full time either way).

Per chip select (CSn at 0x40000000 + n x 64 MB, uncached at + 0x40000000), cycles beyond a cache hit:

| CS  | window       | what                                      | uncached load 16 / 32   | uncached store 16 / 32               | line fill                                           | write-back      |
|-----|--------------|-------------------------------------------|-------------------------|--------------------------------------|-----------------------------------------------------|-----------------|
| 0   | `0x40000000` | IC18 mask ROM (x16), EXP slots            | 7 / 15 (fill / 8)       | as loads                             | 64.07 [P9 BTW4]                                     | 64              |
| 1   | `0x44000000` | IC23 backup SRAM (x16)                    | 8.06 / 17.06 [P9 SRL]   | as loads (GUESS)                     | 59.94 (as CS5)                                      | 59.94           |
| 2   | `0x48000000` | program + table flash (x32)               | 7 (fill / 4)            | as loads                             | 31.84 [P9 PRW4]; 28.56 below `0x48400000` [P9 TBW4] | as fill         |
| 3   | `0x4C000000` | fast SRAM, the library (x32)              | 3.5 (fill / 4)          | as loads                             | 17.87 [P9 LBW4]                                     | as fill         |
| 4   | `0x50000000` | work DRAM (x32)                           | 5.18 [P9 RUL]           | 4.75 [P9 RUS]                        | 23.92 [P9 RAW4]                                     | 21.33 [P9 RAX4] |
| 5   | `0x54000000` | IC21 flash, IC19 ROM, EXP (x16)           | 8.06 / 17.06 [P9 CUL]   | as loads (GUESS)                     | 59.94 [P9 C2W4]; IC19 57.44 [P9 PIW4]               | as fill         |
| 6   | `0x58000000` | TGs, FDC, DSP index, strap (x16)          | 35.03 / 71.06 [P9 STRP] | as loads, posted (GUESS)             | (not cached)                                        |                 |
| 7   | `0x5C000000` | LCD controller IC104, DSP data port (x16) | 43.41 / 87.82 [P9 LCL2] | 27.13 / 55.88 [P9 LCS2 LCS4], posted | (not cached)                                        |                 |

**MEMCTR.** The firmware's values, which pass 9 read back, are 0x8904, 0x0804, 0x0824, 0x0424, 0x0865, 0x0004, 0, 2
(class-1 board). Bits 12:8 look like a wait count (941's outer DSP accessor masks exactly 0x1F00 to raise MEMCTR3),
and bit 5 is set on exactly the three 32-bit memories. But the costs do not follow bits 12:8 everywhere: CS5 has 0
there and costs what CS1 (8) does, and CS6/CS7 (0) are the slowest. For CS0-CS3 they do follow it at about a cycle per
unit (CS3: 4 -> 4.5 cycles per word, CS2: 8 -> 8, CS0: 9 -> 8 per halfword), so a firmware change there (941's DSP
accessor sets MEMCTR3 = 0x924 around its port access) moves those costs by one cycle per unit; CS4-CS7 keep their
measured costs. Which chip select the DSP's `0x9C000000` port is on is open: by the 64 MB map it is CS7, yet 941
raises MEMCTR3's waits around it.

**CHCTR and MEMCTR are registers now.** They read back what the firmware wrote (the driver's I/O window read 0),
with CHCTR's busy bits set while a cache is on (the unit reads 0x8F). So the firmware's cache routines now run (they
test CHCTR's enable bits first), and MEMCTR0 reads bit 15 set as on the unit, so the bus set-up now writes the DRAM
register 0x287 instead of 0x3BF, as the unit's does. `0x32000010`/`40`/`42` read back too: after the boot all eleven bus registers and CHCTR read what pass 9 read on
the unit (`busregs.lua`).

**Counters.** The debugger state list has TINSN (instructions), TMEM (quarter cycles memory added), TICMISS and
TDCMISS; `prof.lua` prints them.

## Calibration: pass 9 and pass 8, the unit against this emulator

The emulator ran the same release binaries, from the same SD-card and floppy route, with `-bios v13` (PROGRAM
893, as Felipe's unit), through cnv_romdump's `test/run_test.sh --cputime` and `--dsprate`; the files were decoded
with the same `check_cpu_probe.py` and `check_dsp_probe.py`, on `6d86f03a` (above).

**Pass 9, test by test** (`pass9_unit_vs_mame.md`, from `p9_compare.py`): ADD implies 64.04 MHz here (unit 64.02).
Of the 109 tests with a reliable unit value, **99 are within 3 % and 107 within 10 %**. Every memory test (cached
hits, line fills from all seven regions, uncached loads and stores per region, on-chip registers, the strap, the
LCD) is within 1.2 %, and so are mul/div, the load-use pairs, call/ret, calls/rets, movm of 4. Before this change
every one of them read one cycle at 32 MHz (cnv_romdump README, "Pass 9 in MAME"). What is left:

| test       | unit cycles | MAME cycles | why                                                                                                         |
|------------|-------------|-------------|-------------------------------------------------------------------------------------------------------------|
| FLSH, TWSH | 10.0        | 11.27       | the firmware routine's short path entered at 8n+5: the queue model stalls its 6-byte cmp, the unit does not |
| JMP        | 3.50        | 3.19        | jmp d16 to the next instruction: the refill model gives 3.2 averaged over the eight alignments              |
| FLLG, TWLG | 60.1        | 57.5        | the long path: eight taken bhi to 6-byte compares; the unit loses 2.5 cycles more in refetches              |
| LSRI, MI16 | 1.25        | 1.31        | runs of 3-byte instructions after a loop's branch: the refill hold costs a little at the turn's start       |
| MVM1       | 3.87        | 3.99        | movm push + pop of one register: the model's minimum pop is 3                                               |
| FL1L       | 64.4 (warm) | 68.1        | one cold call: the first-run excess (the routine's line fills) is 4144 ns here, 4683 on the unit            |

Six unit values are unreliable (1-3 clean runs of 64): the 32-bit LCD loads (LCL4, LCQ4, LCR4) read 3-4 cycles in
their one clean run but 760 counts in their median one, which is two 16-bit loads, as modelled (88.8 cycles); the
line-fill walks from IC18, IC19, IC21 and the table flash (their clean value is also their minimum, and matches).

**The LCD varies.** On the unit some LCD tests' median runs are 2-2.4 times their clean ones (LCL1 865 against 357
counts, LCR2 748 against 308), others' are not (LCL2, LCS2, LCS4, LCM2: median within 2 % of the clean value). The
model uses the clean costs. If the LCD controller holds the CPU off while it fetches the display, a bulk LCD
transfer on the unit takes longer than modelled; Another World's profiler (LCD stores in a real game loop) is the
measurement that settles it.

**Pass 8** (`p8_decode.sh`), the calibration loop, the DSP accesses and the re-latch:

| measure                                           | unit  | before (32 MHz, 1 cycle) | now   |
|---------------------------------------------------|-------|--------------------------|-------|
| calibration samples per 1 ms tick                 | 197   | 206                      | 194   |
| DSP data-port access, us (2048 pairs)             | 24.24 | 23.25                    | 24.33 |
| the re-latch (the firmware's DSP index write), us | 1.69  | 1.67                     | 1.67  |

The samples per tick depend on what the tick handler does in those five ticks, which differs from run to run (191,
196, 185 and 194 with the intermediate builds); the unit's 197 is inside that spread. The re-latch fixed one choice:
stores to CS6/CS7 are posted (2.17 us with them paid in line, 1.67 posted), while work RAM's uncached stores are not
(pass 9's RUS tests show no overlap with the loop after them).


## What it changes

**At the home screen** the core now runs 9.4 million instructions per second (32 before), and 68 % of its cycles go
to memory, nearly all instruction-cache misses (1.5 million a second: the firmware's idle round of tasks and
interrupts spans far more than the 4 KB cache). During the boot's first ten seconds it runs 25.6 million a second
(`prof.lua`).

**The boot** (`ab_boot.sh` against the published binary, snapshots at 2, 3, 4, 5, 6, 8, 12, 20 and 45 s; `=` the
same image, `X` different):

| case          | 2   | 3   | 4   | 5   | 6   | 8   | 12  | 20  | 45  | opcode lines (A, B) |
|---------------|-----|-----|-----|-----|-----|-----|-----|-----|-----|---------------------|
| kn7000 v16    | X   | =   | X   | X   | =   | X   | =   | =   | =   | 0, 0                |
| kn7000 v15    | =   | =   | X   | X   | =   | =   | =   | =   | =   | 0, 0                |
| kn7000 v13    | =   | =   | X   | X   | =   | =   | =   | =   | =   | 0, 0                |
| kn7000 sp7001 | =   | =   | X   | X   | =   | =   | =   | =   | =   | 0, 0                |
| kn6000        | =   | =   | =   | =   | =   | X   | =   | =   | =   | 0, 0                |
| kn6500        | =   | =   | =   | =   | =   | =   | X   | =   | =   | 0, 0                |
| kn2400        | =   | =   | =   | =   | =   | =   | =   | =   | =   | 0, 0                |
| kn2600        | =   | =   | =   | =   | =   | =   | =   | =   | =   | 0, 0                |

On the KN7000 the splash appears under a second later (at 5 s on the published binary, between 5 and 6 s here) and
the logo animation runs a few frames behind; on the KN6000 a screen of the boot at 8 s differs, on the KN6500 the
"TRANSPOSE: C" message is still up at 12 s; from 20 s every case shows the same screens. `prof.lua` with a snapshot
every second (`boot_shift.py`): the splash 1 s later, the logo, the green KN7000 screen and the home screen at the
same second as before.

**The floppy's last byte.** Under the first model STYLE CONVERT never loaded its .CNV: every read that ended on a
track's last sector failed with ST0 `0x44`, ST1 `0x80` (EN). The DMA channel moves all but a sector's last byte; the
DMA-end ISR (941 `0x4840219C`) clears IRQ1 (group 0x18, positive edge, EXTMD `0xFFFF`), polls it 88 times for that
byte's DRQ, then takes the byte and raises TC. MAME's 82077 hands the last two bytes over in one burst (its DRQ rises
once and stays high), so the edge never came and the poll always ran out: in the published binary after 30 us, just
inside the controller's window for TC (the CRC, 32 us); at the instrument's speed after 55 us. The unit loads from
floppy, so on it the poll must see the edge. The driver now re-raises the request when the ISR clears it while DRQ is
still high (`kn7000.cpp`, the `intc_ack_cb` binding): TC 14.2 us after the last DMA byte, 75 instructions
(`fdc_lastbyte.sh`; published: 29.8 us, 950 instructions, the poll running out). Pass 8 and pass 9 load from the
floppy on this build.

**Another World** (`kn5000-anotherworld` `KN7APP.BIN` `26aabecb`, its speed build; `probes/cnv/run_perf.sh` with
`awcnv_speed.lua`, the run the owner makes, in MAME):

| figure                                              | published (`48e84939`) | this model (`6d86f03a`)                                   |
|-----------------------------------------------------|------------------------|-----------------------------------------------------------|
| benchmark, ns per access: LCD store 16 / 32 bits    | 43.0 / 43.0            | 967.5 / 1933.0                                            |
| LCD load 16 bits; work RAM store 32 / load 32       | 43.0; 43.0 / 43.0      | 1485.4; 526.7 / 352.0                                     |
| the intro, new blit with the overlay: fps, frame    | 38.0, 26.2 ms          | 17.0, 58.7 ms                                             |
| the old blit: fps, frame (blit + border)            | 8.7, 113.6 ms (105.6)  | 2.2, 436.8 ms (427.5)                                     |
| the lake, new blit (paced at 25): fps               | 25.0                   | 25.2                                                      |
| MEMCTR0-7, DRAM 40/42, CHCTR as the game reads them | all 0                  | 8904 804 824 424 865 4 0 2, 0 0, 8F (`3077b137`: 287 7D0) |

The game's benchmark runs for 1-4 ms with interrupts and the firmware's tasks on, so its figures include them:
pass 9 times a 16-bit LCD store at 439 ns, the game's benchmark here 967. Sampling the PC once per video frame while
the game runs (`aw_pcsample.lua`): about a third of the samples are in the game, a fifth in the program flash and
nearly half in the library (the firmware's kernel and tasks), with 52-55 % of all cycles going to memory. That share
of the firmware's tasks is this model's prediction; the unit's `AWPERF0.TXT` from the same build (its YIELD against
ASKED, and the benchmark) will test it.

**The audio oracle** (`money.lua`, the held C4) is now `5069aedab573b1c63ef6df7689382bd9` (published
`e415cb0c15ac74ada6bcfc5f7e4ef909`): nothing differs before the note; the note starts within one sample of the
published one's onset (`notes/dsp-probe-2026-10-20/wav_shift.py`: B - A = 0.021 ms), but lines up best 1.94 ms
later (93 samples) with 43 % of A's energy left over 0.5 s, and its first second is 12 % quieter (rms 226.8 against
258.9); from second 18 on the two decay alike (`tools/kn5000_wav_ab.py`). Per 20 ms window the two are the same
waveform about half a period apart, correlation 0.7-0.86 (`oracle_attack.py`). So the firmware's key-on work (tone
generator writes on CS6 at 36 cycles each, posted) now takes long enough to move the voices' start by about 2 ms and
their phase against each other. The KN5000 demo oracle (TLCS-900) is unchanged.

**Host speed** (`-bench 30`, kn7000 `-bios v13`, 29 emulated seconds, run twice each, host load 5-7 on 8 cores from
other work): published 47.7 % and 50.8 %, this model 60.7 % and 65.5 %. The model's per-instruction work is more than
paid for by running fewer instructions per emulated second; the effects DSP is what keeps both below full speed.

## Not modelled, or not measured

- **Instruction classes pass 9 did not time:** jmp d32 and (An), call d32, the bit operations, bvc/bvs/bnc/bns,
  rti and trap (the manual's values, adjusted as the measured relatives), udf (the extension unit: a guess), the
  interrupt acceptance (a guess).
- **Uncached reads of IC18, the flash and the library RAM:** taken as their line fills / transfers. Stores to IC23,
  IC21/IC19 and CS6: taken as their loads. Posting CS6/CS7 stores rests on pass 8's re-latch alone.
- **The LCD** varies on the unit (some tests' median runs 2.4 times their clean ones); the model uses the clean
  costs. The DSP data port is taken to cost what the LCD does.
- **MEMCTR's fields** are not documented: the costs are per chip select as measured; only CS0-CS3 follow bits 12:8.
  Which chip select 941's DSP accessor means to slow down (MEMCTR3, around `0x9C000000`) is open.
- **The fetch queue** is a fit: FLSH/TWSH (+12.5 %), JMP (-9 %), FLLG/TWLG (-4 %) and runs of 3-byte instructions
  (+5 %) are its worst. Branch targets' alignment matters as on the chip, but not in exactly its way. The hold
  after a jump is loosely fixed: `fetch_fit_control.py` finds 0 to 0.75 cycles about equally good (the core
  uses 0.75, which keeps the firmware routine's long path, FLLG, closest).
- **Not modelled:** the write buffer for cachable stores, DMA's bus cycles (the floppy's), DRAM refresh, the
  instruction queue across interrupts beyond a refill, DCBYPS/LDUSE (not found), CHCTR bit 7, cache locking (way
  bits 12-15).
- **What would calibrate next:** the unit's `AWPERF0.TXT` from Another World's speed build (the firmware's share of
  the CPU while a task runs, and LCD costs in a real loop); a stopwatch on the unit's boot (power on to the home
  screen: about 12 s here, as before); pass 9 tests for the untimed classes and for CS6 stores.

## Files

| file                                      | what it answers, and how to run it                                                                                                                                                                       |
|-------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `fetch_fit.py`                            | which fetch rate and queue size reproduce the unit's straight-line tests (`python3 fetch_fit.py [cpu_time.json]`, the unit's decoded pass 9)                                                             |
| `fetch_fit_control.py`                    | which refill rules after a jump (hold, overlap, untaken branches) reproduce the unit's call/return and branch tests (`python3 fetch_fit_control.py`)                                                     |
| `p9_compare.py`                           | pass 9 test by test, the unit against MAME: `p9_compare.py UNIT.json MAME.json`, both from `check_cpu_probe.py DIR --json OUT`                                                                           |
| `p8_decode.sh`                            | pulls pass 8's `DSPRATE.BIN` off a `run_test.sh --dsprate` run's SD image and decodes it (samples per tick, the re-latch, the verdict)                                                                   |
| `prof.lua`                                | the model's counters (and a snapshot) every second of a run: `PROF_END=30 PROF_SNAP=1 ... -autoboot_script prof.lua`                                                                                     |
| `boot_shift.py`                           | when each boot screen of binary A appears with binary B: `boot_shift.py SNAPS_A SNAPS_B` (prof.lua's snapshots, one per second)                                                                          |
| `fdc_lastbyte.sh`, `fdc_lastbyte_tap.lua` | when the firmware takes a floppy sector's last byte and raises TC, and what the controller answers: `fdc_lastbyte.sh BIN OUT SDIMG FLOPPY`                                                               |
| `aw_pcsample.lua`                         | where the CPU's time goes while Another World runs: `AW_SPEED_LUA=.../awcnv_speed.lua probes/cnv/run_perf.sh OUT aw_pcsample.lua` (from kn5000-anotherworld `kn7000/`, `EMU` = a folder with the binary) |
| `oracle_attack.py`                        | how two oracle captures differ around the note-on, per window: rms, difference, best lag and correlation: `oracle_attack.py A.wav B.wav 16.08 16.40 20`                                                  |
| `busregs.lua`                             | the bus controller registers and CHCTR as the CPU reads them after the boot, to compare with pass 9's snapshot of the unit                                                                               |
