# HANDOFF — KN-series expansion connectors, and using them to dump ROMs

**2026-08-03.** Companion to `HANDOFF-custom-flash-and-splash.md`. Everything here is from the
KN7000 service manual (`pdftotext -layout` of `service_manual/technics_sx-kn7000_keyboard.pdf`,
6.6 MB of text) and from firmware string counts.

## The two connectors are DIFFERENT interfaces

| | connector | side | carries |
|---|---|---|---|
| **peripheral / HDD** | `CN106` (part `TJSF43711`) | main board | `EXP.CS0..CS3`, `HDD.INDEX`, A/D bus, `R/NW` `RE` `WE2` `WE3` |
| **wave expansion** | `CN301` + `CN502` | sound board | `SY-EW01..EW04` boards, marked OPTION |

Interconnection diagram line: `CN502  CN301  EW01 EW02 EW03 EW04 / CN821 CN820 12 12 OPTION x4`.
§8.12 "WAVE EXPANSION BOARD test" says to *insert the SY-EW01..EW04 board* and that a failure
implicates *"the ADDRESS/DATA BUS as well as the strobe signal lines"*.

⇒ **Wave expansion does NOT use CN106.** Separate connectors, separate boards, separate purpose.

## KN7000 DOES have the peripheral connector — with a WIDER decode than the KN6500

```
  EXP.CS0  10 2Y2   1Y2  6
  EXP.CS1  12 2Y0   1Y0  4
  EXP.CS2  14 2DA   1DA  2      <- from A(23)
  EXP.CS3  13 2DB   1DB  3      <- from A(24)
  ... TC74VHC139 dual 2-to-4 decoder, +3.3D, R32 100, R34 47
  HDD.INDEX grouped with TGS.INT1 / TGS.INT2 / FBC.INT
```

KN6500 emits **two** selects (`EXP.CS0/1`); KN7000 emits **four**. ★ `EXP.CS2/CS3` have **no known
consumer** — worth finding out what they were for.

## ...but the KN7000 FIRMWARE has no HD-SX3 support

```
              HD-SX3  EXTAPR  HDDEXT  HDDTEST  "HDD"
  kn6000         1       1       2       2       24
  kn6500         1       1       2       2       24
  kn7000         0       1       1       0        4
  kn2400         0       1       1       0        1     <- CONTROL
```

★ **The KN2400 is the control that makes this readable**: it shows the *same* lone `EXTAPR`/`HDDEXT`
hits as the KN7000 and has no expansion connector at all, so those singletons are MILK-framework
residue, **not** evidence of support. Without that comparison `EXTAPR=1` on the KN7000 reads as a
false positive.

⇒ Hardware kept and extended the bus; the HD-SX3 driver code did not carry into this firmware.
A board could seat and be selected, but nothing in this version would drive it.

## Dump routes these connectors might open

### A. Wave ROMs (IC203/204/207/208) via the EW slot — UNVERIFIED, do not act yet
The wave ROMs are the only category with **no non-invasive route** (not CPU-visible, so roadmap
Methods A/B cannot reach them). The EW slot is electrically on *a* wave bus, which would make it a
soldering-free harness point — far safer than a TSOP clip.

⚠ **NOT ESTABLISHED that the EW slot shares the bus of the INTERNAL wave ROMs.** A text-proximity
test found 993 wave-bus lines (`AWAX/AWAY/BWAX/BWAY`) and **zero** `CN301`/`CN502` references within
120 lines of any of them — but all 11 of those references are in parts lists and the interconnection
diagram, not on a signal-bearing schematic sheet. `pdftotext` loses the geometry that would answer
this. ⇒ **Read the sound-board schematic PAGE visually** (the sheet with IC203/204/207/208 chip
enables). Do not build a harness on the grep result.

If it does share: a slot device is a **slave** and cannot initiate reads, so a dump needs the tone
generator **tri-stated** (reset or output-enable off) — probably one or two wires, to the TG, not to
the ROMs. Passive snooping while playing needs no modification but only covers whatever the firmware
happens to read.

### B. Program ROM via custom code on a CN106 board — the more promising route
`CN106` carries a full CPU bus, and the HD-SX3 firmware **is MN10300 code linked at `0x97800000`**
that copies its own data segment and clears BSS — i.e. host-CPU code executing from a board on this
connector. Program flash **is** CPU-visible, and the firmware already implements MIDI sysex, serial,
floppy and SD exfiltration paths.

⛔ **Blocker: what makes the CPU jump there.** The **host-side extension-header validation** is still
not found — the KN6000/KN6500 equivalent of the KN5000's HD-AE5000 header check. The HD-SX3's
`"XAPR"` signature + 31-entry export table look exactly like what such a check consumes. Finding it
yields the signature and vector layout a board must present.

⚠ Target the **KN6000/KN6500** for this, not the KN7000 — they have the host-side support. Their
program ROMs are already dumped, so the value is the *mechanism*, which should transfer.

## Next steps

1. **Read the sound-board schematic page** for IC203/204/207/208 chip enables vs `CN301`/`CN502`.
   Grep cannot settle this; the page can.
2. **Derive the CN106 address window** from the `TC74VHC139` decode (`A(23)`, `A(24)` → `EXP.CS2/3`),
   then search the KN6000 firmware for accesses in that range.
3. **Find the host-side header validation** in the KN6000 firmware. Pure disassembly, no hardware
   risk, and it unblocks route B. This has been the outstanding item on this board since the ROM was
   declared.
4. Not yet checked: the KN7000's **CN106 pin table** (only its decoder sheet has been read), so
   "same connector family" is established but "same 70-pin assignment" is not.
