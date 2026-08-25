#!/usr/bin/env python3
"""Every table the SX-WSA1's control-panel link is decoded from, read out of
the ROMs rather than typed, plus a self-test that fails if one moves.

QUESTION THIS ANSWERS
  "What does the WSA1 firmware do with a byte that arrives from the panel MCU,
  and what does it send back?"  Everything the emulator needs is in six tables
  and one port bit, and all seven are READ from prom_a/prom_b here:

    1. PB bit 0, read once at prom_a 0xF82882 from the RESET path, latched to
       RAM (0xC4).  THE MODEL STRAP.  1 = variant A, 2 = variant B.
    2/3. The two wire-address -> button-group maps, prom_a 0xF8A109 (variant A)
       and 0xF8A189 (variant B), 128 bytes each, indexed by
       (addr & 0x1F) | ((addr & 0xC0) >> 1).  0x20 = "no such control".
    4/5. The two LED-register -> wire-address maps, prom_a 0xF8C8AC (A) and
       0xF8C8B7 (B), used by Panel_SetLedRegister (0xF8C84A).
    6. The analogue-control dispatch table, prom_a 0xF89825, 32 entries,
       indexed by ((addr & 0xC0) >> 1) | ((addr & 7) << 2).  It is reached
       through prom_b thunk T_F405F0 both from the SC1 receive decoder's
       type-2 arm (prom_b 0xF5B14C, 0xF5B1D6) and from the on-CPU A/D scan.
    7. The two packet-dispatch tables of the codec itself: SC1_RxOpTable
       (prom_b 0xF5B0B5, 8 entries) and SC1_TxOpTable (0xF5B299, 4).

WHAT COUNTS AS PASS
  Exits 0 when every assertion in check() holds: the strap instruction is the
  exact seven bytes at 0xF82882, both button maps have the shape documented in
  notes/FINDINGS-wsa1-control-panel.md (16 vs 11 live entries, all with the
  panel-id bits 11), both LED maps hold the documented wire addresses, the
  analogue table has 12 distinct targets with the documented grouping, and the
  two codec tables have the documented 1/1/3/2 and 3/1 handler grouping.
  Exits 1 and says which one moved otherwise.

USAGE
  python3 wsa1_panel_tables.py            # print every table
  python3 wsa1_panel_tables.py --selftest # print, then assert
"""
import sys

PA = "/home/fsanches/compartilhado/wsa1-roms-disasm/original_ROMs/wsa1_prom_a.ic12"
PB = "/home/fsanches/compartilhado/wsa1-roms-disasm/original_ROMs/wsa1_prom_b.ic13"

pa = open(PA, "rb").read()
pb = open(PB, "rb").read()
rda = lambda a, n: pa[a - 0xF80000:a - 0xF80000 + n]
rdb = lambda a, n: pb[a - 0xF00000:a - 0xF00000 + n]
le32 = lambda b: int.from_bytes(b, "little")

fails = []
def check(cond, what):
    print("   %-6s %s" % ("ok" if cond else "FAIL", what))
    if not cond:
        fails.append(what)


def main():
    print("=== 1. THE MODEL STRAP: prom_a 0xF82882 ===")
    strap = rda(0xF82882, 13)
    print("   %s" % " ".join("%02x" % b for b in strap))
    print("   ld A,0x01 / bit 0,(PB=0x1F) / jr NZ,+2 / ld A,0x02 / ld (0xC4),A / ret")
    print("   -> PB.0 high => (0xC4)=1 (variant A), PB.0 low => (0xC4)=2 (variant B)")
    print("   PB.0 is an INPUT: RESET writes PBCR=0x0C at 0xF826E5 (only bits 2,3 out)")
    check(strap[:11] == bytes([0x21, 0x01, 0xF0, 0x1F, 0xC8, 0x6E, 0x02, 0x21, 0x02, 0xF0, 0xC4]),
          "strap instruction bytes at 0xF82882")
    check(rda(0xF826E5, 3) == bytes([0x08, 0x2E, 0x0C]), "RESET writes PBCR = 0x0C (PB.0 = input)")
    check(rda(0xF827D8, 3) == bytes([0x1E, 0xA7, 0x00]), "RESET calls it: calr 0xF82882 at 0xF827D8")

    print("\n=== 2/3. BUTTON MAPS: wire address -> group id ===")
    for base, name in ((0xF8A109, "variant A  ((0xC4)==1)"), (0xF8A189, "variant B  ((0xC4)!=1)")):
        t = rda(base, 128)
        live = [(i, v) for i, v in enumerate(t) if v != 0x20]
        print("   %s at 0x%06X: %d live entries" % (name, base, len(live)))
        for i, v in live:
            addr = ((i & 0x60) << 1) | (i & 0x1F)
            kind = "button segment %2d" % (addr & 0x0F) if not (addr & 0x10) else "analogue sub %d" % (addr & 7)
            print("       wire 0x%02X  %-18s -> group 0x%02X" % (addr, kind, v))
        check(all(((i & 0x60) == 0x60) for i, _ in live), "%s: every live entry has panel id 11" % name)
    check(len([v for v in rda(0xF8A109, 128) if v != 0x20]) == 16, "variant A has 16 live wire addresses")
    check(len([v for v in rda(0xF8A189, 128) if v != 0x20]) == 11, "variant B has 11 live wire addresses")

    print("\n=== 4/5. LED MAPS: register index -> wire address ===")
    a = list(rda(0xF8C8AC, 11)); b = list(rda(0xF8C8B7, 11))
    print("   variant A 0xF8C8AC: %s" % " ".join("%02X" % x for x in a))
    print("   variant B 0xF8C8B7: %s" % " ".join("%02X" % x for x in b))
    print("   Panel_RefreshLeds (0xF8C456) walks EIGHT registers: want 0x20D0..0x20D7,")
    print("   sent-shadow 0x20F0..0x20F7, and sends only the ones that differ.")
    check(a[:8] == [0xC0, 0xC1, 0xC2, 0xC4, 0xC5, 0xC9, 0xCC, 0xCD], "variant A LED wire addresses")
    check(b[:7] == [0xC1, 0xC2, 0xC9, 0xCA, 0xCB, 0xCC, 0xC3], "variant B LED wire addresses")
    check(rda(0xF8C456, 2) == bytes([0x22, 0x08]), "Panel_RefreshLeds starts `ld B,0x08`")

    print("\n=== 6. ANALOGUE DISPATCH: prom_a 0xF89825, 32 entries ===")
    ent = [le32(rda(0xF89825 + 4 * i, 4)) for i in range(32)]
    for i, v in enumerate(ent):
        note = ""
        if v == 0x00F89AB0: note = "(reject: rcf)"
        if v == 0x00F89AAD: note = "(accept unconditionally: scf)"
        print("       panel=%d sub=%d -> 0x%06X %s" % (i >> 3, i & 7, v, note))
    check(len(set(ent)) == 12, "12 distinct analogue handlers")
    check(ent.count(0x00F89AB0) == 21, "21 of the 32 slots are the reject stub 0xF89AB0")
    check(ent[31] == 0x00F89AAD, "panel 3 sub 7 (the rotary encoder) is the always-accept stub")

    print("\n=== 7. THE CODEC'S OWN DISPATCH TABLES (prom_b) ===")
    rx = [le32(rdb(0xF5B0B5 + 4 * i, 4)) for i in range(8)]
    tx = [le32(rdb(0xF5B299 + 4 * i, 4)) for i in range(4)]
    names = {0x00F5B0D5: "SC1_RxOp0_ThreeByte  (button)",
             0x00F5B12C: "SC1_RxOp2            (analogue)",
             0x00F5B226: "SC1_RxOp3_Discard    (sync/ack)",
             0x00F5B179: "SC1_RxOp6_Run        (multi-byte)",
             0x00F5B2A9: "SC1_TxOp0_TwoByte",
             0x00F5B2D9: "SC1_TxOp3_Run"}
    for i, v in enumerate(rx):
        print("       RX type %d -> 0x%06X  %s" % (i, v, names.get(v, "?")))
    for i, v in enumerate(tx):
        print("       TX type %d -> 0x%06X  %s" % (i, v, names.get(v, "?")))
    check(rx == [0x00F5B0D5, 0x00F5B0D5, 0x00F5B12C, 0x00F5B226, 0x00F5B226,
                 0x00F5B226, 0x00F5B179, 0x00F5B179], "RX table grouping 2/1/3/2")
    check(tx == [0x00F5B2A9, 0x00F5B2A9, 0x00F5B2A9, 0x00F5B2D9], "TX table grouping 3/1")

    print("\n=== 8. THE FOUR OPEN-TIME COMMANDS (SC1_ConfigurePort) ===")
    for site in (0xF5A8ED, 0xF5A900, 0xF5A913, 0xF5A92C):
        s = rdb(site, 4)
        print("       0x%06X  ld A,0x%02X / ld W,0x%02X   -> send (0x%02X,0x%02X)"
              % (site, s[1], s[3], s[1], s[3]))
    check([rdb(s, 4)[1::2] for s in (0xF5A8ED, 0xF5A900, 0xF5A913, 0xF5A92C)]
          == [bytes([0xDF, 0xD2]), bytes([0xDF, 0x1A]), bytes([0xDD, 0x03]), bytes([0xDE, 0x80])],
          "open sequence (0xDF,0xD2)(0xDF,0x1A)(0xDD,0x03)(0xDE,0x80)")

    print("\n=== 9. THE SERIAL MODE ===")
    print("   0xF5A8AF ld SC1MOD,0x00   -> SM=00 = I/O INTERFACE (synchronous) mode")
    print("   0xF5A8B5 ld SC1CR,0x01    -> IOC=1 = clock from the SCLK pin")
    print("   INT6_SC1_PeerRequest sets   SC1CR bit 0 (0xF5AC1E)  -> panel clocks in")
    print("   SC1_StartWordTx clears      SC1CR bit 0 (0xF5ABFC)  -> CPU clocks out")
    print("   BR1CR takes 0x22 / 0x24 / 0x28 (BRxCK=phiT8, divider 2 / 4 / 8)")
    check(rdb(0xF5A8AF, 3) == bytes([0x08, 0x56, 0x00]), "SC1MOD = 0x00 at 0xF5A8AF")
    check(rdb(0xF5A8B5, 3) == bytes([0x08, 0x55, 0x01]), "SC1CR = 0x01 at 0xF5A8B5")
    check(rdb(0xF5ABFC, 4) == bytes([0xC0, 0x55, 0x3C, 0xFE]), "and (SC1CR),0xFE in SC1_StartWordTx")
    check(rdb(0xF5AC1E, 4) == bytes([0xC0, 0x55, 0x3E, 0x01]), "or (SC1CR),0x01 in INT6_SC1_PeerRequest")

    if "--selftest" in sys.argv:
        print("\n%s" % ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
        sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
