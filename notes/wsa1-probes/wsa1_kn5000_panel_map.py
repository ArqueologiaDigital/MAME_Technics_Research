#!/usr/bin/env python3
"""Routine-for-routine correspondence between the WSA1's SC1 module and the
KN5000's control-panel driver.

QUESTION THIS ANSWERS
  wsa1_kn5000_panel_bytediff.py shows the two share byte runs.  This one asks
  the sharper question: for each LABEL in the WSA1 SC1 module, is there a
  KN5000 CPanel_* symbol at the same place in the shared run -- i.e. do the
  two images agree ROUTINE FOR ROUTINE, or only in scattered idioms?

  Method: take every maximal common substring of >= 8 bytes between the WSA1
  module and the KN5000 v10 main-CPU ROM, keep the ones that land in the
  KN5000 panel driver (0xFC3E65-0xFC4C33), and print, for each, the WSA1
  label at or before its start and the KN5000 symbol at or before its start.
  Both label lists are READ from the trees, not typed here.

WHAT COUNTS AS PASS
  Prints "PASS" when the run at each of the two dispatch tables' `add XHL,imm32`
  differs in exactly the 4 immediate bytes and those immediates are the two
  tables' addresses -- SC1_RxOpTable/CPanel_RX_PacketHandlers and
  SC1_TxOpTable/CPanel_LED_PacketHandlers.  Exits non-zero otherwise.

USAGE
  python3 wsa1_kn5000_panel_map.py
"""
import re, sys

WSA1_S   = "/home/fsanches/compartilhado/wsa1-roms-disasm/prom_b/wsa1_prom_b.s"
WSA1_BIN = "/home/fsanches/compartilhado/wsa1-roms-disasm/original_ROMs/wsa1_prom_b.ic13"
KN5K_BIN = "/home/fsanches/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom"
KN5K_SYM = "/home/fsanches/compartilhado/kn5000-roms-disasm/symbols/maincpu_v10_symbols_reference.txt"

PROM_B_BASE, KN_BASE = 0xF00000, 0xE00000
SC1_LO, SC1_HI = 0xF5A800, 0xF5B44E
CP_LO,  CP_HI  = 0xFC3E65, 0xFC4C34      # CPanel_InitDispatchTable .. ToneGen_IncrementWrap128


def wsa1_labels():
    """label -> address, by pairing each `NAME:` line with the address in the
    comment of the first instruction line that follows it."""
    out, pend = {}, []
    for line in open(WSA1_S, errors="replace"):
        m = re.match(r"^([A-Za-z_][A-Za-z_0-9]*):\s*$", line)
        if m:
            pend.append(m.group(1)); continue
        m = re.search(r";\s*([0-9A-F]{6})\s", line)
        if m and pend:
            a = int(m.group(1), 16)
            for n in pend:
                out[n] = a
            pend = []
    return {n: a for n, a in out.items() if SC1_LO <= a < SC1_HI}


def kn5000_syms():
    out = {}
    for line in open(KN5K_SYM, errors="replace"):
        p = line.split()
        if len(p) == 2 and re.fullmatch(r"[0-9A-F]{8}", p[1]):
            a = int(p[1], 16)
            if CP_LO <= a < CP_HI:
                out.setdefault(a, []).append(p[0])
    return out


def common_runs(a, b, minlen):
    idx = {}
    for i in range(len(b) - minlen + 1):
        idx.setdefault(b[i:i + minlen], []).append(i)
    out, i = [], 0
    while i <= len(a) - minlen:
        best = (0, -1)
        for j in idx.get(a[i:i + minlen], ()):
            n = minlen
            while i + n < len(a) and j + n < len(b) and a[i + n] == b[j + n]:
                n += 1
            if n > best[0]:
                best = (n, j)
        if best[0]:
            out.append((i, best[1], best[0])); i += best[0]
        else:
            i += 1
    return out


def owner(addr, table):
    best = None
    for a in table:
        if a <= addr and (best is None or a > best):
            best = a
    return best


def main():
    pb = open(WSA1_BIN, "rb").read()
    kn = open(KN5K_BIN, "rb").read()
    sc1 = pb[SC1_LO - PROM_B_BASE:SC1_HI - PROM_B_BASE]
    wl = wsa1_labels()
    ks = kn5000_syms()
    wl_by_addr = {}
    for n, a in wl.items():
        wl_by_addr.setdefault(a, []).append(n)

    runs = [r for r in common_runs(sc1, kn, 8) if CP_LO <= KN_BASE + r[1] < CP_HI]
    runs.sort(key=lambda r: -r[2])
    print("Common runs >= 8 bytes that land inside the KN5000 panel driver "
          "(0x%06X-0x%06X): %d runs, %d bytes\n" % (CP_LO, CP_HI - 1, len(runs),
                                                    sum(r[2] for r in runs)))
    print("%-9s %-30s %-9s %-30s %s" % ("WSA1", "WSA1 label (at or before)",
                                        "KN5000", "KN5000 symbol (at or before)", "len"))
    for i, j, n in runs:
        wa, ka = SC1_LO + i, KN_BASE + j
        wo, ko = owner(wa, wl_by_addr), owner(ka, ks)
        wn = "%s%s" % ("/".join(wl_by_addr[wo]), "" if wo == wa else "+0x%X" % (wa - wo)) if wo else "?"
        kn_ = "%s%s" % ("/".join(ks[ko]), "" if ko == ka else "+0x%X" % (ka - ko)) if ko else "?"
        print("%08X  %-30s %08X  %-30s %d" % (wa, wn[:30], ka, kn_[:30], n))

    # --- the gate: the two dispatch-table immediates -------------------------
    def imm_check(wsa_site, kn_site, wsa_tbl, kn_tbl, name):
        """`extz XHL / add XHL,imm32 / ld XHL,(XHL) / jp (XHL)` is 10 bytes:
        EB 12 is already behind us, so from `EB C8 <imm32> A3 23 B3 D8`."""
        W = pb[wsa_site - PROM_B_BASE:wsa_site - PROM_B_BASE + 10]
        K = kn[kn_site - KN_BASE:kn_site - KN_BASE + 10]
        okw = W[0:2] == b"\xeb\xc8" and int.from_bytes(W[2:6], "little") == wsa_tbl
        okk = K[0:2] == b"\xeb\xc8" and int.from_bytes(K[2:6], "little") == kn_tbl
        diff = [x for x in range(10) if W[x] != K[x]]
        print("\n%s\n  WSA1  %06X: %s\n  KN5K  %06X: %s\n  bytes differing: %s"
              % (name, wsa_site, " ".join("%02x" % b for b in W),
                 kn_site, " ".join("%02x" % b for b in K), diff))
        return okw and okk and diff and set(diff) <= {2, 3, 4, 5}

    a = imm_check(0xF5B0AB, 0xFC4959, 0x00F5B0B5, 0x00FC4965,
                  "RX dispatch: SC1_RxOpTable vs CPanel_RX_PacketHandlers")
    b = imm_check(0xF5B28F, 0xFC4B79, 0x00F5B299, 0x00FC4B85,
                  "TX dispatch: SC1_TxOpTable vs CPanel_LED_PacketHandlers")
    print("\n%s: both dispatch instructions are the same 10 bytes except the "
          "4-byte table pointer." % ("PASS" if (a and b) else "FAIL"))
    sys.exit(0 if (a and b) else 1)


if __name__ == "__main__":
    main()
