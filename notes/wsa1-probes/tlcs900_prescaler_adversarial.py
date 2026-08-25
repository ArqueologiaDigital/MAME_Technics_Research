#!/usr/bin/env python3
"""Adversarial re-check of the "phiT1 = fc/8" prescaler report.

QUESTION IT ANSWERS: do the ROM facts the prescaler report rests on hold when
re-derived from the images by a second party, and do the report's own
sub-claims survive?

RUN:  python3 notes/wsa1-probes/tlcs900_prescaler_adversarial.py

It re-reads the three original ROM sets under
/home/fsanches/compartilhado/technics_roms/roms/ and checks, per site, the
exact bytes at the exact address.  Nothing here is copied from
tlcs900_prescaler_scale.py: the address list was rebuilt by scanning for the
`ldio <sfr>,#imm` encodings (0x08 <reg> <imm>, 0x0A <reg> <lo> <hi>) rather
than by trusting the report's table.

WHAT THE SIGNALS MEAN
  * T01MOD bits[3:2]==3  -> timer 1 is clocked from phiT256.
  * T4MOD  bits[1:0]==1  -> 16-bit timer 4 is clocked from phiT1;
             bits[3:2]==1  -> the counter is cleared by the TREG5 match.
  * TREG4 == 1           -> INTTR4 fires once per TREG5 period.
  * `cp (XHL),0x60`      -> the INTTR4 handler counts 96 ticks to the beat.
  * The tempo divide stores round(C / (64*BPM)) into TREG5.

THE ONE EQUATION.  With PPQN ticks to the beat and the counter cleared by
TREG5, INTTR4 fires at phiT1/TREG5, so
      BPM = 60*phiT1/(PPQN*TREG5)  and  TREG5 = C/(64*BPM)
  =>  C = 3840 * phiT1 / PPQN,  i.e. at PPQN=96:  phiT1 = C/40.
That pins phiT1 as an ABSOLUTE FREQUENCY.  It does NOT pin fc, and it does NOT
pin the shift on its own: the emulator is right iff
      clock() / 2**PRESCALE_T1  ==  phiT1
so the shift is only correct as a PAIR with the driver's clock() line.
"""

import re, sys

ROMS = "/home/fsanches/compartilhado/technics_roms/roms/"
IMAGES = {
    # tag: (path, base address it is mapped at)
    "prom_a": (ROMS + "wsa1/wsa1_os_v2.ic12", 0xF80000),   # SX-WSA1R CPU1, wsa1.cpp:1852
    "prom_c": (ROMS + "wsa1/wsa1_os_v2.ic28", 0xF80000),   # SX-WSA1R CPU2, wsa1.cpp:1963
    "kn1500": (ROMS + "kn1500/technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15", 0xE00000),
    "kn5000": (ROMS + "kn5000/kn5000_v10_program.rom", 0xE00000),
    "kn5000sub": (ROMS + "kn5000/kn5000_subprogram_v142.rom", 0x000000),
    "kn5000subboot": (ROMS + "kn5000/kn5000_subcpu_boot.ic30", 0x000000),
}

_cache = {}
def img(tag):
    if tag not in _cache:
        path, base = IMAGES[tag]
        _cache[tag] = (open(path, "rb").read(), base)
    return _cache[tag]

FAILS = []
def check(tag, addr, hexbytes, what):
    data, base = img(tag)
    off = addr - base
    exp = bytes.fromhex(hexbytes)
    got = data[off:off + len(exp)]
    ok = got == exp
    print(f"  [{'PASS' if ok else 'FAIL'}] {tag} {addr:#08x} {got.hex(' '):<18} {what}")
    if not ok:
        FAILS.append((tag, addr, what, got.hex(' '), exp.hex(' ')))
    return ok

def word(tag, addr):
    data, base = img(tag)
    off = addr - base
    return int.from_bytes(data[off:off + 4], "little")

print(__doc__.split("WHAT THE SIGNALS")[0].strip())
print()

# --- 1. SX-WSA1R, prom_a (TMP95C061 CPU1) --------------------------------
print("1. SX-WSA1R prom_a -- RESET timer programming")
check("prom_a", 0xF826EB, "08240d", "ldio T01MOD,0x0D  T1<-phiT256, T0<-phiT1")
check("prom_a", 0xF826F1, "08220f", "ldio TREG0,0x0F")
check("prom_a", 0xF826F4, "08231c", "ldio TREG1,0x1C = 28")
check("prom_a", 0xF82703, "083805", "ldio T4MOD,0x05   T4<-phiT1, clear on TREG5")
check("prom_a", 0xF8270C, "083001" "083100", "ldio TREG4 = 0x0001")
check("prom_a", 0xF82712, "083209" "08333d", "ldio TREG5 = 0x3D09 = 15625")
check("prom_a", 0xF8272A, "0820b7", "ldio TRUN,0xB7    prescaler + T0,T1,T2 + T4,T5")
check("prom_a", 0xF827C8, "087330", "ldio INTET10,0x30 INTT1 lvl3, INTT0 masked")
check("prom_a", 0xF827CE, "087503", "ldio INTET54,0x03 INTTR4 lvl3, INTTR5 off")
v = word("prom_a", 0xFFFF00 + 0x50)
print(f"  [{'PASS' if v == 0xF82EA2 else 'FAIL'}] prom_a vector 0x50 (INTTR4, tmp95c061.cpp:336) -> {v:#08x}")
if v != 0xF82EA2: FAILS.append(("prom_a", 0xFFFF50, "INTTR4 vector", hex(v), "0xf82ea2"))
check("prom_a", 0xF82EB1, "833f60", "cp (XHL),0x60     -> 96 PPQN")
check("prom_a", 0xFAA378, "42003b5808", "ld XDE,140,000,000  (tempo numerator C)")
check("prom_a", 0xFAA373, "324000" "da40", "ld DE,0x40 / mul XWA,DE   -> 64*BPM")
check("prom_a", 0xFAA38D, "f03252", "ld (0x32),DE      -> TREG5L/TREG5H")

# ADVERSARIAL: the report says INTET32 is never written on the WSA1.
print("\n1b. REPORT SUB-CLAIM UNDER TEST: 'INTET32 never written' (report section 5)")
data, base = img("prom_a")
hits = [(base + m.start(), data[m.start() + 2])
        for m in re.finditer(re.escape(bytes.fromhex("0874")), data)]
print(f"  prom_a `ldio INTET32,#` sites: {[(hex(a), hex(v)) for a, v in hits]}")
if hits:
    print("  [REFUTED] INTET32 IS written.  Kernel-start block:")
    check("prom_a", 0xF856EC, "f020b3", "res 3,(TRUN)      stop timer 3")
    check("prom_a", 0xF856EF, "08280e", "ldio T23MOD,0x0E  T3<-phiT256")
    check("prom_a", 0xF856F2, "082736", "ldio TREG3,0x36 = 54")
    check("prom_a", 0xF856F5, "087420", "ldio INTET32,0x20 INTT3 lvl2, INTT2 masked")
    print("  => INTT3 = fc/2048/54.  At fc=28MHz: 15.8 Hz (shift 15) -> 253.2 Hz (shift 11).")
    print("     253.2 Hz is a ~4 ms RTOS tick; a NEW corroboration the report does not have.")
else:
    FAILS.append(("prom_a", 0, "expected INTET32 writes", "none", "at least one"))

# The BR0CR branch: is 0x0C a fossil, or live two-model code?
print("\n1c. REPORT SUB-CLAIM: BR0CR=0x0C is a KN1500 fossil 'corrected at runtime to 0x0E'")
check("prom_a", 0xF82754, "08530c", "boot   ldio BR0CR,0x0C  (N=12 -> 24 MHz shape)")
check("prom_a", 0xFA58F8, "08530e", "MIDI init ldio BR0CR,0x0E (N=14 -> 28 MHz shape)")
check("prom_a", 0xFA58FB, "c2f8ffff3f24", "cp (0xFFFFF8),0x24   <- MODEL ID test")
check("prom_a", 0xFA5903, "08530c", "  ...only if ID==0x24: ldio BR0CR,0x0C")
check("prom_a", 0xFA5909, "0850fe", "ldio SC0BUF,0xFE  = MIDI ACTIVE SENSING -> SC0 IS MIDI")
data, base = img("prom_a")
mid = data[0xFFFFF8 - base]
print(f"  prom_a[0xFFFFF8] = {mid:#04x} (build tag {data[0xFFFFF0-base:0xFFFFF8-base]!r})")
print(f"  => {'takes BR0CR=0x0E, N=14' if mid != 0x24 else 'takes BR0CR=0x0C, N=12'}."
      "  It is LIVE two-model code, not a dead fossil.")

# --- 2. SX-KN1500 (TMP95C061) --------------------------------------------
print("\n2. SX-KN1500 IC15")
check("kn1500", 0xFE5F9D, "0824ed", "ldio T01MOD,0xED  T1<-phiT256 (bits7:6=11, 8-bit PWM)")
check("kn1500", 0xFE5FA9, "082318", "ldio TREG1,0x18 = 24")
check("kn1500", 0xFE5FB5, "083805", "ldio T4MOD,0x05   SAME as WSA1")
check("kn1500", 0xFE5FC4, "0a300100", "ldw (TREG4),0x0001")
check("kn1500", 0xFE5FC8, "0a32093d", "ldw (TREG5),0x3D09 = 15625  SAME literal")
check("kn1500", 0xFE6078, "087503", "ldio INTET54,0x03 SAME as WSA1")
v = word("kn1500", 0xFFFF00 + 0x50)
print(f"  [{'PASS' if v == 0xFE6515 else 'FAIL'}] kn1500 vector 0x50 (INTTR4) -> {v:#08x}")
check("kn1500", 0xFE6522, "833f60", "cp (XHL),0x60     -> 96 PPQN")
check("kn1500", 0xFA6D85, "42000e2707", "ld XDE,120,000,000")
check("kn1500", 0xFA6D9A, "f03252", "ld (0x32),DE      -> TREG5")
check("kn1500", 0xFE6001, "085629", "ldio SC1MOD,0x29  BRG-clocked")
check("kn1500", 0xFE6007, "c0573ccf", "and (BR1CR),0xCF  -> tap 0")

# --- 3. SX-KN5000 (TMP94C241) -- the row the report calls decisive --------
print("\n3. SX-KN5000 v10 main -- the row the report says 'closes the circularity'")
print("   (the report showed only the constant; these five sites are MINE)")
check("kn5000", 0xEF042D, "08841d", "ldio T01MOD,0x1D  T1<-phiT256")
check("kn5000", 0xEF0439, "088910", "ldio TREG1,0x10 = 16")
check("kn5000", 0xEF0442, "089805", "ldio T4MOD,0x05   IDENTICAL to WSA1/KN1500")
check("kn5000", 0xEF044B, "0a900100", "ldw (TREG4),0x0001")
check("kn5000", 0xEF044F, "0a92093d", "ldw (TREG5),0x3D09 = 15625  SAME literal again")
check("kn5000", 0xEF0E2D, "8361" "833f60", "inc 1,(XHL) / cp (XHL),0x60 -> 96 PPQN")
check("kn5000", 0xFCA34F, "4200b4c404", "ld XDE,80,000,000")
check("kn5000", 0xFCA371, "f1920052", "ld (0x0092),DE    -> TREG5L/H on the TMP94C241 map")
print("\n3b. REPORT SUB-CLAIM: 'the three routines are instruction-for-instruction the same'")
check("kn5000", 0xFCA354, "1d3908ef" "cfdc" "6e05" "4200879303",
      "call/cp L,4/jr NZ/ld XDE,60,000,000  <- EXTRA BRANCH, second constant")
print("  [REFUTED] the KN5000 routine has a second numerator, 60,000,000.")
print("  Under C = 3840*phiT1/PPQN with phiT1 = 2 MHz that is PPQN = 128, not 96.")
print("  The report never saw it and never checked the KN5000's PPQN at all.")

# --- 4. the 'TREG1 = fc in MHz' design rule -------------------------------
print("\n4. REPORT SUB-CLAIM (section 3e): 'TREG1 = fc in MHz on all three machines'")
check("kn5000sub",     0x010AB9, "088914", "sub program v142: TREG1 = 0x14 = 20")
check("kn5000subboot", 0x018305, "088910", "sub BOOT ic30   : TREG1 = 0x10 = 16")
print("  [COUNTEREXAMPLE] same processor (KN5000 sub, kn5000.cpp:1394 = 2*10 MHz = 20 MHz),")
print("  two different TREG1 values.  The 'rule' needs a second 'fossil' plea to survive,")
print("  so section 6's tiebreaker #3 should be downgraded.")

# --- 5. the one equation, evaluated --------------------------------------
print("\n5. WHAT THE FIRMWARE ACTUALLY PINS  (C = 3840*phiT1/PPQN, PPQN = 96)")
print("   machine     C            phiT1 = C/40   driver clock()          required shift")
for name, C, clk, where in [
        ("SX-WSA1R ", 140_000_000, 28_000_000, "wsa1.cpp:2169  28_MHz_XTAL"),
        ("SX-KN1500", 120_000_000, 24_000_000, "kn1500.cpp:56  24_MHz_XTAL"),
        ("SX-KN5000",  80_000_000, 16_000_000, "kn5000.cpp:1203 2*8_MHz_XTAL")]:
    phit1 = C / 40
    ratio = clk / phit1
    shift = int(ratio).bit_length() - 1 if float(ratio).is_integer() else None
    print(f"   {name}  {C:>11,}  {phit1/1e6:6.2f} MHz     {where:<24} {shift}")
print("\n   The firmware pins phiT1 ABSOLUTELY.  It does NOT pin fc and it does NOT pin the")
print("   shift: shift 3 is correct only as a PAIR with those clock() lines.  The invariant")
print("   to assert in the CPU core is  clock()/2**PRESCALE_T1 == phiT1,  not the shift.")

print(f"\n{'ALL BYTE CHECKS PASS' if not FAILS else 'FAILURES: ' + repr(FAILS)}")
sys.exit(1 if FAILS else 0)
