# KN7000 style-name build subsystem (the "8 Beat 1" trail)

## Enabler: MN10300 disassembly via unidasm
The disassembly repo ships MAME's standalone disassembler at `../mame-sony-video/unidasm`
(read-only use is fine). To disassemble a program-ROM region:

```
python3 -c "d=open('kn7000_program.rom','rb').read(); open('w.bin','wb').write(d[OFF:OFF+N])"
../mame-sony-video/unidasm w.bin -arch mn10300 -basepc 0xADDR
```
where `OFF = ADDR - 0x48400000`. This unblocks all static MN10300 RE (the debugger `-debug`
segfaults with `QTDEBUG=0`, and no `mn10300-objdump` is installed).

## The style-list name path (why every slot shows "8 Beat 1")
Confirmed at runtime (read-taps, tick 2026-07-07j): the rhythm-style list reads a **boot-built
RAM name-table**, NOT the custom flash (0 dataflash reads during display). Disassembly of that
build (tick 2026-07-07L):

Flow: `style records --parse--> TEMPLATE 0x5003A2BC --memcpy--> NAME-TABLE 0x5003A37C --> list`.

Key functions (program ROM):
- **0x48441D1B StyleRecordToTemplate** — parses ONE style record at `a2` into the template
  `0x5003A2BC + idx*0x18`. Record subtype = `(a2+4) high nibble`: 0xB0/0xC0/0xD0/0xE0 branches
  write different name/param fields (e.g. 0xB0 copies bytes to `+0/+1`, others to `+2..+4`,
  `+0x12..+0x14`). Type nibble `>=8` => skip.
- **0x48441CBF StyleTemplateToNameTable** — `memcpy(0x5003A37C, 0x5003A2BC, 0xC0)` (0xC0 = 8
  entries x 0x18) — copies the template into the displayed name-table.
- **0x48441CDB StyleTemplateBuildLoop** — nested loop over 8 x 0x18 entries; per entry sets
  `a3 = 0x5003A37C + i*0x18`, `a2 = 0x5003A2BC + i*0x18`, loads handler ptr **0x48435DD0** into
  `(0x18,sp)`, and calls **0x48440862** (per-entry record fetch — NEXT to trace).
- **0x48442072 StyleNameDefaultFill** — `memcpy(dest = (sp+0x40)+0x20 + idx*0x18, src = *(sp+0x14),
  0xf)` — copies the 15-byte DEFAULT name. `*(sp+0x14)` is the default string "  8 Beat 1  "
  (@0x4872AB42; note it is NOT loaded as an immediate anywhere — reached via this arg pointer).
  This runs ~14x at boot (208 string-byte reads / 15) => the ~14 list slots all get the default.
- **0x48435DD0 StyleIdArrayHandler** — per record builds the style-ID arrays `0x50034C48` (u32,
  idx `0x50034C40`) and `0x50035448` (u32, idx `0x50034C44`), limit `0x1FF` (511 styles). Tags
  IDs with source bits `0x70000000`. Sub-calls: 0x48435C29 (type->slot), 0x48440535 (lookup),
  **0x48435D83 StyleIdArrayStore**, 0x48446C9D (mode 0x90 special, gated by flag `0x50034C3D`).

RAM globals:
| addr | meaning |
|------|---------|
| 0x5003A37C | displayed style-name table (8+ entries x 0x18) |
| 0x5003A2BC | template the name-table is memcpy'd from (parsed from records) |
| 0x50034C40 / 0x50034C44 | u16 style-list build counters (limit 0x1FF) |
| 0x50034C48 / 0x50035448 | u32 style-ID arrays |
| 0x50034C3D | style mode flag (gates the 0x90 special path) |

## OPEN (next step)
The default fill runs => the record parse produced no real names => the **record SOURCE is empty
or wrong**. Since the names do NOT come from the custom flash, the records come from the table
ROM (TCMP) or the library ROM. Trace **0x48440862** (the per-entry fetch in the build loop) and
what pointer it hands to `StyleRecordToTemplate` — that pointer's origin is the bug.
