# kn5000-io-census — three instruments for "what is this pin?"

These exist because of a rule this project learned the hard way, twice:

> **Do not infer a signal's polarity or meaning from a single call site.**
> A pin that read like an active-high motor enable turned out to be active low,
> and what settled it was a census of *every* writer across *both* CPU images
> plus the observation that only one of the two directions was followed by a
> delay.

Every port claim in `src/mame/matsushita/kn5000.cpp` should be reproducible from
one of these. If a claim cannot be, it is a guess wearing a comment.

They read the disassembly at `~/compartilhado/kn5000-roms-disasm` and the
service-manual PDF at `~/compartilhado/kn5000-docs/service_manual/`. They write
nothing.

---

## `sfr_census.py` — every SFR access in a source tree

**Question:** *which* I/O port, timer, serial or interrupt register does this
firmware touch, from which routine, and what does it do with the value?

```
./sfr_census.py --summary ~/compartilhado/kn5000-roms-disasm/v10/maincpu
./sfr_census.py --only PD,PE,PG,PH ~/compartilhado/kn5000-roms-disasm/v10/maincpu
./sfr_census.py ~/compartilhado/kn5000-roms-disasm/v142/subcpu \
                ~/compartilhado/kn5000-roms-disasm/subcpu
```

Prints `REG  R/W  file:line  routine  instruction  ; comment`. Hits with `.byte`
directives within 12 lines are tagged `[MISFRAME?]` — in these trees that is the
signature of DATA the disassembler framed as code, and such hits must be looked
at before they are counted.

The SFR name/address table is transcribed from the disassembly's own header,
`v10/maincpu/shared/sfr_tmp94c241.s` (identical copy at
`v142/subcpu/shared/sfr_tmp94c241.s`). **PG is 0x40 and PZ is 0x68.** A claim
that names one port and cites the other's register number is wrong on its face;
that exact mix-up has already reached a published docs page.

Addresses appear in the sources in BOTH hex and decimal (`ldio 0x34, ...` and
`stdi8 (52), ...`), and the SFRs above 0xFF are only reachable through the
16-bit-direct forms. The tool handles both; plain `grep` for `0x34` does not.

⚠ Two failure modes of `grep` that this tool exists to avoid: several `.s` files
in `v10/maincpu` are latin-1 and GNU grep skips them as binary unless you pass
`-a` (that silently under-reported a port by 2x in an earlier pass); and the
mnemonic set here is this project's LLVM spelling, not Toshiba syntax, so
searching for `bit 6,(PD)` finds nothing.

## `rom_bitop_census.py` — the framing-independent control

**Question:** is the source census COMPLETE, or is some of this port's traffic
hidden inside a region framed as data?

```
./rom_bitop_census.py --all-bits PD PH PA --base 0xe00000 \
  --roms ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom \
         ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v7_program.rom
```

Scans the raw ROM for `F0 <addr> C8+b / B8+b / B0+b` = `BIT/SET/RES b,(nn)`.
No framing involved. Agreement with `sfr_census.py` is what licenses a claim.

Signal it produced, quoted in `kn5000.cpp`'s Port H comment: across the whole
2 MB v10 image there is **exactly one `SET 0,(PH)` and one `RES 0,(PH)`**
(0xF97042 / 0xF9704B), and the same in v7 — i.e. `FDC_Pulse_PH0` is the only
writer of that pin in the machine. `SET/RES 4,(PD)` and any op on `PH.3`:
**zero occurrences**, in either image.

⚠ It counts BYTE MATCHES, not instructions — the same three bytes occur inside
data — and it only covers the BIT/SET/RES encodings. `LDCF b,(nn)` (used at
`audio_control_engine.s:1869` to read PD.6) is a different opcode and does not
appear here. Use it as a control on the source census, never alone.

## `trace_schematic_net.py` — which pin is this net on?

**Question:** the service manuals are IMAGE-ONLY PDFs — `pdftotext` and `grep`
return nothing, which has produced false "undocumented" claims twice. So: follow
the ink.

```
pdftoppm -f 32 -l 32 -r 600 -png \
    ~/compartilhado/kn5000-docs/service_manual/technics_sx-kn5000.pdf p

./trace_schematic_net.py p-32.png --pins left --band 4150,4236 --range 2600,2960
./trace_schematic_net.py p-32.png --labels --band 2900,3050 --range 1900,2450
./trace_schematic_net.py p-32.png --from 3000,2029 --dir right
```

Page 32 is "CPU SECTION (A) P.C. Diagram" (IC5, the main TMP94C241). Tracing the
six nets of the floppy group from their sheet connectors into IC5 gives:

| net | IC5 pin | pin name |
|---|---|---|
| FDCTC  | 145 | PH0/TC0 |
| FDCRST | 12  | PD0 |
| FDCINT | 13  | PD1/INT4 |
| FDCDRQ | 14  | PD2/INT5 |
| —      | 15  | PD4 — **not connected** |
| FD.H/D | 16  | PD5/INT6 |
| FD.I/O | 17  | PD6/TI7/INT7 |

The last four are bindings the driver already had, from an independent source.
**They are the control**: a tracer that reproduces four known answers is worth
believing on the fifth. Never quote a one-way trace on its own — trace from both
ends and check they meet.

Sheet-connector arrows give direction: point-LEFT = an output leaving the sheet
(FDCTC, FDCRST, MTXD), point-RIGHT = an input (FDCINT, FDCDRQ, FD.H/D, FD.I/O,
MRXD, the FS/FC pedals).

---

## What the numbers in the driver comments came from

- **Port G = the pedals, active low** — `sfr_census.py --only PG v10/maincpu`:
  three reads, all in `audio/audio_control_engine.s` (:1844, :1850, :1862), and
  the idle test is `and a,0xf0 / srl a,4 / cp a,0x0f`.
- **Port H bit 0 = FDCTC, active high** — `sfr_census.py --only PH,PHCR,PHFC`
  plus `rom_bitop_census.py --all-bits PH`, plus the schematic trace above.
- **Timer 0 never runs, so the old `to0_callback` binding was dead** —
  `sfr_census.py --only T8RUN,PCFC v10/maincpu`: the only `T8RUN` writes are
  `set 1` (timer 1) at `shared/boot_hw_init.s:73` and `set/res 3` / `res 2`
  in `boot/system_handlers.s`. No `set 0`.
- **PECR is written twice and only the second one counts** —
  `sfr_census.py --only PE,PECR,PEFC v10/maincpu`: boot writes 0x20, then
  `CPanel_InitHardware` (`ui/cpanel_routines.s:95-98`) writes PEFC=0x00 and
  PECR=0x46, which is what makes PE.5 an input. Reading only the boot value
  gives the opposite answer.

---

## `phtap.lua` — witness the Terminal Count strobe in the running machine

**Question:** *the three tools above read the ROM. This one asks whether the pin
actually moves when the emulated machine runs.*

It is the evidence behind the claim that the FDC Terminal Count is main-CPU
Port H bit 0 and is strobed **once per boot** — a static census can show that
`FDC_Pulse_PH0` is the only writer, but only the running machine shows it fire.

```
mame kn5000 -skip_gameinfo -autoboot_script tools/kn5000-io-census/phtap.lua
```

Wrap any scripted launch in `timeout`, and keep video visible.

⚠ **THE TAP IS HELD IN A GLOBAL, AND THAT IS NOT A STYLE CHOICE.** A MAME memory
tap stored in a `local` is garbage-collected and **silently stops firing** —
no error, no warning. The script runs, the machine runs, and the capture comes
back empty, which reads exactly like *"the firmware never touches this
address"*. For a port census that is the precise wrong conclusion, arrived at
with no visible failure. If a tap reports nothing, verify it is rooted in a
global before recording a negative.

Prints `PH.0 strobe: N rising, M falling` at machine stop, so a run that never
reaches the strobe is distinguishable from one where the tap died: a dead tap
prints `0 rising, 0 falling` *and* so does a boot that never gets that far —
which is why the count is printed rather than a bare "seen".
