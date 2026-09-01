#!/usr/bin/env python3
"""Byte census behind the micro-DMA channel 3 audit (SX-WSA1, 2026-08-27).

Answers three questions about prom_a/prom_b/prom_c, WITHOUT running anything:

 Q1  Who touches the INTTC3 selector (0x6007DA)?  The runtime probe
     wsa1_udma3_audit.lua counts INTTC3 entries by tapping READS of that word.
     That is only a valid counter if `ldw_da bc,(0x6007da)` at 0xF8E555 is the
     ONLY reader in either image.

 Q2  Who writes DMA3V (SFR 0x7F) and DMA2V (SFR 0x7E)?  The earlier probe
     wsa1_link_stage.lua tapped 0x7E-0x7F as one word and called the total
     "dma3v_writes"; this lists the two register's sites apart so the run can be
     attributed.

 Q3  How close together are INTTC2's last byte (0xF8E54E) and INTTC3's first
     (0xF8E54F)?  tlcs900_device::RDOP() prefetches four bytes
     (tlcs900.cpp:81-99, `m_prefetch[i] = RDMEM(m_pc.d + i)` /
     `RDMEM(m_pc.d + 3)`), so a read tap placed on a routine's ENTRY also fires
     while the CPU executes the three bytes before it.

Run:  python3 wsa1_udma3_xref.py
Exit non-zero if any count drifts from what the notes claim.
"""
import sys, pathlib

ROMS = pathlib.Path.home() / "compartilhado/kn5000-roms-disasm/wsa1/original_ROMs"
IMAGES = [("prom_a", "wsa1_prom_a.ic12", 0xF80000),
          ("prom_b", "wsa1_prom_b.ic13", 0xF00000),
          ("prom_c", "wsa1_prom_c.ic28", 0xF80000)]   # prom_c is CPU 2's, same window

# ---- opcode-prefix table for the 24-bit direct-address forms -----------------
# TLCS-900/H: <prefix> <lo> <mid> <hi> <op...>, prefix names the operand SIZE:
#   0xC2 = 8-bit (MB24)   0xD2 = 16-bit (MW24)   0xE2 = 32-bit (ML24)
#   0xF2 = "memory, no register operand" (MD24) -- bit ops and immediate stores
PREFIX = {0xC2: "MB24/8-bit", 0xD2: "MW24/16-bit", 0xE2: "ML24/32-bit", 0xF2: "MD24"}
# second opcode byte, for the forms this census meets
OP = {0x00: "st imm8 (WRITE)", 0x20: "ld r,(mem) (READ)", 0x21: "ld rr,(mem) (READ)",
      0x23: "ld r,(mem) (READ)", 0x31: "lda (READ of the ADDRESS only)",
      0x46: "ld (mem),r (WRITE)", 0x50: "ld (mem),rr (WRITE)",
      0x61: "inc (mem) (RMW)", 0x3F: "cp (mem),imm8 (READ)",
      0xF8: "cp (mem),rr (READ)"}

def hits(blob, pat):
    out, i = [], blob.find(pat)
    while i >= 0:
        out.append(i)
        i = blob.find(pat, i + 1)
    return out

fail = []

print("=" * 78)
print("Q1  every reference to 0x6007DA (the INTTC3 selector)")
print("=" * 78)
readers = []
for name, fn, base in IMAGES:
    blob = (ROMS / fn).read_bytes()
    for off in hits(blob, bytes((0xDA, 0x07, 0x60))):
        if off == 0:
            continue
        pre, op = blob[off - 1], blob[off + 3]
        if pre not in PREFIX:
            continue                     # not an operand in this form; skip
        addr = base + off - 1
        kind = OP.get(op, f"op 0x{op:02X} (unclassified)")
        print(f"  {name} 0x{addr:06X}  {PREFIX[pre]:12s}  {kind}")
        if "READ" in kind and "ADDRESS only" not in kind:
            readers.append((name, addr))
print(f"  -> {len(readers)} reader(s): " + ", ".join(f"{n} 0x{a:06X}" for n, a in readers))
if readers != [("prom_a", 0xF8E555)]:
    fail.append("0x6007DA has readers other than prom_a 0xF8E555 -- the "
                "selector read tap is NOT a clean INTTC3 entry counter")

print()
print("=" * 78)
print("Q2  `ldio DMAnV,imm8` sites  (08 7C..7F imm)")
print("=" * 78)
dma = {}
for name, fn, base in IMAGES:
    blob = (ROMS / fn).read_bytes()
    for reg, label in ((0x7C, "DMA0V"), (0x7D, "DMA1V"), (0x7E, "DMA2V"), (0x7F, "DMA3V")):
        for off in hits(blob, bytes((0x08, reg))):
            val = blob[off + 2]
            addr = base + off
            dma.setdefault((name, label), []).append((addr, val))
for key in sorted(dma):
    for addr, val in dma[key]:
        print(f"  {key[0]} 0x{addr:06X}  ldio {key[1]},0x{val:02X}")
print()
print("  ⚠ THE LIST ABOVE IS OPCODE-ANCHORED, NOT INSTRUCTION-ANCHORED: `08 7F xx`")
print("  is a common byte pair inside tables and 8-bit code, and most of the prom_a")
print("  hits above 0xF93000 are data.  Only sites inside CONVERTED assembly are")
print("  real instructions.  For the link that is 0xF8E000-0xF8E6A1 in prom_a and")
print("  0xF99900-0xF9A037 in prom_c, and there the set is exact:")
LINK_A = [a for a, v in dma.get(("prom_a", "DMA3V"), []) if 0xF8E000 <= a <= 0xF8E6A1]
LINK_A2 = [a for a, v in dma.get(("prom_a", "DMA2V"), []) if 0xF8E000 <= a <= 0xF8E6A1]
print("    prom_a link block, DMA3V: " + " ".join(f"0x{a:06X}" for a in LINK_A))
print("    prom_a link block, DMA2V: " + " ".join(f"0x{a:06X}" for a in LINK_A2))
EXP3 = [0xF8E24F, 0xF8E4CA, 0xF8E4E9, 0xF8E51F, 0xF8E5BD, 0xF8E65A, 0xF8E683]
EXP2 = [0xF8E0E0, 0xF8E166, 0xF8E1E4, 0xF8E2E7, 0xF8E30A,
        0xF8E398, 0xF8E3BB, 0xF8E446, 0xF8E469]
if LINK_A != EXP3:
    fail.append("the DMA3V sites in prom_a's link block drifted")
if LINK_A2 != EXP2:
    fail.append("the DMA2V sites in prom_a's link block drifted")
print(f"  -> {len(LINK_A)} DMA3V arms (4 of them 0x0A, 3 of them 0x00 = abort) and")
print(f"     {len(LINK_A2)} DMA2V arms, all `ldio DMA2V,0x12`, in the link block.")
print("  THIS IS WHY wsa1_link_stage.lua's `dma3v_writes` was wrong: its tap covered")
print("  0x7E-0x7F, so the NINE DMA2V transmit sites counted as DMA3V arms.")

print()
print("=" * 78)
print("Q3  the INTTC2 / INTTC3 boundary and RDOP's 4-byte prefetch window")
print("=" * 78)
blob = (ROMS / "wsa1_prom_a.ic12").read_bytes()
for a in (0xF8E52C, 0xF8E54E, 0xF8E54F, 0xF8E47E, 0xF8E47F):
    print(f"  0xF8E{a & 0xFFF:03X} = 0x{blob[a - 0xF80000]:02X}")
print("  INTTC2_uDMA2Done ends with `reti` (0x07) at 0xF8E54E;")
print("  INTTC3_LinkDmaDone starts with `push XBC` (0x39) at 0xF8E54F.")
print("  RDOP() reads m_pc+3, so executing INTTC2's bytes 0xF8E54B..0xF8E54E")
print("  makes byte reads of 0xF8E54E..0xF8E551.  A read tap on 0xF8E54E-0xF8E54F")
print("  therefore counts INTTC2 RETURNS as if they were INTTC3 ENTRIES.")
if blob[0xF8E54E - 0xF80000] != 0x07 or blob[0xF8E54F - 0xF80000] != 0x39:
    fail.append("the INTTC2/INTTC3 boundary bytes are not 07 39")

print()
if fail:
    for f in fail:
        print("FAIL: " + f)
    sys.exit(1)
print("all census checks pass")
