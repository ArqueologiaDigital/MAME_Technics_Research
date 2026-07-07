# MAME PR - ROM manifest (Technics MN10300 skeleton drivers)

All images are de-interleaved into physical even/odd 16-bit flash chips (ROM_LOAD32_WORD).
They are checksum-verified reconstructions from the firmware-update disks (good dumps),
pending real chip reads. kn2600 reuses the kn2400 set. KN5000 is already upstream (kn5000.cpp).

## kn1500  (SX-KN1500) — Toshiba TLCS-900 (TMP95C061); in kn5000.cpp
Program ROMs are BAD_DUMP (unvalidated, need a redump); `kn1500_lcd.svg` is a good LCD-panel artwork asset (SCREEN_TYPE_SVG).

| ROM file | size | CRC32 | SHA1 |
|----------|------|-------|------|
| `technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15` | 2097152 | `0f78da9a` | `53d5c43d833fb005a7bd377583252b84b646253d` |
| `technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15.rest` | 2097152 | `ce60897a` | `9b54f693f693488132b93e8bfed1927d7e741ae1` |
| `kn1500_lcd.svg` (screen) | 221081 | `d779a7b9` | `0b40105175cc6e2ac05dea65f1ddb6c7c52c4662` |

## kn7000  (SX-KN7000)
Provenance: even/odd of the decompressed JK1.SLD (program, kn7-16 update) and JK2.SLD (table, kn7-14 update).

| ROM file | size | CRC32 | SHA1 |
|----------|------|-------|------|
| `kn7000_program_even.rom` | 2097152 | `529b87ce` | `f198fd9a9ea31a454acfe7be0eb935beca6771b1` |
| `kn7000_program_odd.rom` | 2097152 | `a36e6222` | `721d4469dc5f692f7a2c16c556b2e21115df19f6` |
| `kn7000_table_even.rom` | 2097152 | `005a6db2` | `2f4112ea9b039b17b5ada6952b7646adae8d9dd6` |
| `kn7000_table_odd.rom` | 2097152 | `7e1a312e` | `435b597b926ebac56d4710bcae25b635a59a9ce5` |

## kn6000  (SX-KN6000)
Provenance: even/odd of the decompressed IK1.SLD (program) and IK2.SLD (table), from the kn6-71 firmware update.

| ROM file | size | CRC32 | SHA1 |
|----------|------|-------|------|
| `kn6000_program_even.rom` | 2097152 | `56c2cfe3` | `e15a4c73440f1dcdf06457f9956c96bf20d68b16` |
| `kn6000_program_odd.rom` | 2097152 | `9d94da6c` | `d73b4c8ebf0c67b6a2eeb5571d0273fc6efbfe4c` |
| `kn6000_table_even.rom` | 2097152 | `fa5e4f93` | `0426da99b1589c0362e6321466beab21b22b81b0` |
| `kn6000_table_odd.rom` | 2097152 | `fd8e3bcd` | `e1b63d45299b67e5258d5d08a949ea8e05c1b8e6` |

## kn6500  (SX-KN6500)
Provenance: even/odd of the decompressed IKV1.SLD (program) and IKV2.SLD (table), from the kn65-13 firmware update.

| ROM file | size | CRC32 | SHA1 |
|----------|------|-------|------|
| `kn6500_program_even.rom` | 2097152 | `f42a2fcf` | `7cebf73bf623fd714ca455ed50b80da1d2186414` |
| `kn6500_program_odd.rom` | 2097152 | `ca2a733f` | `2484d3b76b62b05ded39e4194cdc74fd3c01bcbe` |
| `kn6500_table_even.rom` | 2097152 | `8c7f33a2` | `d44fb4415cd6b571e11e57d4a7642226b0bf4edf` |
| `kn6500_table_odd.rom` | 2097152 | `6953e094` | `abf4c2252d40c71c761503d657593eb6e9c0eecc` |

## kn2400  (SX-KN2400)
Provenance: even/odd of KN24PRG.DAT (== LKG1.SLD + LKG2.SLD, decompressed from the kn24-11 firmware update).

| ROM file | size | CRC32 | SHA1 |
|----------|------|-------|------|
| `kn2400_program_even.rom` | 2097152 | `b94fc8a8` | `86d5d9916afdb90f82de78064b1d76fce3a21d7b` |
| `kn2400_program_odd.rom` | 2097152 | `73781cbc` | `d90a3560561efd94322dca1a6710f2d5d3837cd2` |

## kn2600  (SX-KN2600 (clone of kn2400))
(uses parent kn2400 ROMs)

