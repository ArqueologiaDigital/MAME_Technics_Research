# FINDINGS — the KN expansion buses, and where board code actually runs

**2026-08-03.** Resolves the two items `HANDOFF-expansion-connectors.md` left open by reading the
schematic **pages** (not `pdftotext`) and disassembling the firmware. **It corrects two claims in
that handoff and in blog Part 122** — see "Corrections" at the end. Read this over the older note.

Sources: `KN7000/service_manual/technics_sx-kn7000_keyboard.pdf` pp. 100, 112, 114 (schematic
sheets, read with `pdftotext -bbox` geometry + rendered crops); the interleaved program images of
kn7000 / kn6000 / kn6500, disassembled with `unidasm -arch mn10300 -basepc` (CPU base `0x48400000`).

## There are TWO separate expansion interfaces, on TWO different connector types

| interface | connectors (part) | width | carries | who reads it |
|---|---|---|---|---|
| **CPU peripheral bus** (EXP.CS) | `CN202 CN203 CN205 CN207` (`QJTG02840AA`, `K1MM40A00002`) | 40-pin | `A(1..19)`, `D(16..31)`, `EXP.CS0..3` (pin 38), `WE2` (39), `RE` (40), `DE` | the **CPU** |
| **wave bus** | `CN204 CN206` (A-side) · `CN208 CN209` (B-side) (`K1KA80A00100`) | 80-pin | `WAX(0..16)`, `WAY(0..21)`, `WD(0..15)`, `WOEX`, `WOEY`, `EXCEX0..3`, `EXCEY0..3` | the **tone generators** |

Four 40-pin + four 80-pin = one CPU connector and one wave connector per SY-EW slot (§8.12 inserts
`SY-EW01..EW04`, and warns a failure implicates *"the ADDRESS/DATA BUS as well as the strobe signal
lines"* — because **both** buses are involved).

A **SY-EW board is dual-natured**: the CPU loads samples into it as *SOUND RAM* over the 40-pin
peripheral bus, and a tone generator plays them back over the 80-pin wave bus.

## Q1 — DOES the EW path share the internal wave bus?  ★ YES (was "unknown")

The internal wave ROMs sit on the raw wave bus:

```
  A / master side (p112): IC203 C3CBQD000002, IC204 C3CBQD000001   on AWAX/AWAY/AWD, TG = IC201
  B / sub    side (p114): IC207 C3CBQD000004, IC208 C3CBQD000003   on BWAX/BWAY/BWD, TG = IC205
  (128 Mbit each = 64 MB of wave ROM total; all four still NO_DUMP)
```

The **same** buses are branched to the 80-pin expansion connectors:

- **data** — `BWD(0..15)` → `EXBWD(0..15)` through 47 Ω series-resistor packs (`Z242/Z244/Z245/Z246`
  on the B-side; A-side equivalents feed `EXAWD`). The connector's data lines are the wave ROMs'
  data lines, buffered.
- **chip-enable** — a dedicated `TC74VHC139` demux (`IC202` A-side, `IC206` B-side) decodes the top
  wave-address bits (`AWAX/BWAX 22/23`) into `EXACEX/EXACEY` and `EXBCEX/EXBCEY`, so expansion
  samples occupy their **own** enable space rather than colliding with the internal ROM enables.
- the 80-pin connector also carries the wave **address** (`WAX/WAY`) and the **output-enables**
  (`WOEX/WOEY`) directly.

⇒ **A board seated on an 80-pin connector sees every wave-bus transaction, including the TG reading
the internal ROMs** (shared `WD` data + `WAX/WAY` address + `WOE`). That makes a **passive,
solderless snoop-dump of the internal wave ROMs electrically feasible** from the expansion connector
— the non-invasive route the old note wanted but could not confirm.

⚠ Caveats before anyone builds this: (1) passive snooping only captures samples the firmware
actually plays; a *complete* readout needs the TG **tri-stated** so the harness can drive `WAX/WAY`
and read `WD` — one or two wires to the TG, not to the ROMs. (2) Which of the four slots taps the A
(master) vs B (sub) TG is not yet pinned down — only two 80-pin connectors sit on each side's sheet.

## Q2 — what asserts EXP.CS0–3, and can we run code from a board?

**EXP.CS0–3 are asserted by the system address decoder `IC3` (`TC74VHC139`, the `PSRT.EXP`
expansion region, decoding `A(23)`/`A(24)`)** — one strobe per expansion window (p100). They land on
the four 40-pin connectors. The four CPU windows are:

```
  0x41000000   0x41800000   0x56000000   0x57000000
```

### KN7000 — the EW slots are DATA-ONLY "SOUND RAM". No board code runs.

The firmware validates an **`"Expansion Board KN7000 SOUND RAM"`** header (ASCII table at
`0x485B8518`) at each window — handlers at `0x48449EF4` (win `0x57000000`), `0x4844A04B`
(`0x56000000`), `0x4844A178` (`0x41000000`), `0x4844A2A6` (`0x41800000`). On a match it **walks a
relocatable data structure**: pointers are read from the board header, relocated by the window base
(`+a2`), and handed to fixed firmware loaders (`0x48483B12`, `0x485702AD/BA`, …). Every board pointer
is dereferenced as **data** (`movbu/movhu/mov`). The only computed control transfers are **bounded
jump-table switches into firmware** — `jmp (a0)` where `a0 = *(0x486A2D90 + idx*4)`, `idx` clamped
0..11, and **all 12 table entries are firmware addresses**. The board never receives control.

⇒ You cannot make the shipped KN7000 firmware execute code from an EW board — the "SOUND RAM"
contract has no code-entry vector.

### KN6000 / KN6500 — the HD-SX3 route DOES run board code.  ★ blocker CLOSED

These firmwares carry the HD-SX3 (hard-disk) support the KN7000 dropped. The header sits at
**`0x97800000`** and its signature is **`"XAPR\0"`** (bytes `58 41 50 52 00`, table at `0x486ACD78`).
Validation + dispatch (KN6000 addresses):

```
  0x48572A15  memcmp(0x97800000, "XAPR", 4)          -> sets present flag 0x500056FC
              then a second "XAPR" check via *(0x97800004)
  0x48572A6F  mov (0x9780000C), a0 ; 0x48572A75 calls (a0)     <- board entry vector +0x0C
  0x48572A8C  mov (0x97800008), a1 ;            calls (a1)     <- board entry vector +0x08 (a0=0x5024BE58)
  0x48572AAF  mov (0x97800010), a0 ;            calls (a0)     <- board entry vector +0x10
```

`calls (aN)` is the MN10300 subroutine-indirect-call. So the **`XAPR` header is an export table of
function pointers the firmware jumps into** once the signature matches. Present a board mapped at
`0x97800000` with `"XAPR\0"` + valid vectors at `+0x08/+0x0C/+0x10` and the host CPU executes your
code. Program flash is CPU-visible, and the firmware already has MIDI/serial/SD/floppy exfil paths —
so this is a working route to dump the KN6000/KN6500 program (and, with care, other CPU-visible
chips). Both machines' program ROMs are already dumped, so the value is the **mechanism**.

This is the "host-side extension-header validation" that was flagged four times without being found.
Note MAME already carries a `bus/technics/kn6000/hdsx3` device — the mechanism above is what a
code-carrying board would have to satisfy.

## Corrections to `HANDOFF-expansion-connectors.md` / blog Part 122

1. **`CN106` is the SD-card connector**, not the expansion/HDD bus — its 11 pins are
   `SDCS/SDSO/SDCLK/SDSI/SNS/JIGU.ON` (p104). The peripheral EXP.CS bus is the four 40-pin
   `CN202/03/05/07`. The "CN106 carries EXP.CS0..3 / HDD.INDEX" line in the old note is wrong.
2. **The wave-bus/EW-slot overlap is real, not "unknown."** The old grep found zero overlap because
   the connector-side nets are **renamed** (`BWD`→`EXBWD`, decoded enables `EXBCEX`) at the buffer
   resistors, so searching for `BWD/BWAX` near `CN…` is a guaranteed false negative.
