#!/usr/bin/env python3
"""Re-derive the SX-WSA1R's four SERVICE-SCREEN panel entries from ROM bytes.

QUESTION IT ANSWERS: `wsa1_cpanel.cpp` now names four CP_SEG1 bits after the
service screen each selects at power-on.  Those are the first (position ->
function) pairs any panel bit on this machine has, so they need a script, not a
reading.  This one asserts every byte the claim rests on.

    python3 notes/wsa1-probes/wsa1_rack_service_chord.py      # exits non-zero on any failure

WHAT IT CHECKS, and why each step matters:

  1. RESET reaches the test.  prom_a 0xF827F8 is `call 0xF40148`, and prom_b's
     thunk at 0xF40148 is `jp 0xF952FC`.
  2. 0xF952FC splits on the MODEL STRAP: `cp (0xC4),0x02` picks sub_F953CD (the
     rack, one panel button) and otherwise sub_F9530B (the keyboard, two keys).
  3. sub_F953CD reads RAM (0x2B31) and compares it for EQUALITY against
     2 / 4 / 8 / 0x10 / 0x20, then stores a screen id through XIX = 0x2070 and
     sets (0x2071) = 0x80.
  4. (0x2B31) really is SEG1.  The panel shadow index is
     (wire & 0x0F) | ((wire & 0x40) >> 2), and wire 0xC1 -> 0x11 -> 0x2B31.
  5. The RESET ORDER, because it changes what a user sees: this chord is the
     SECOND of four, and 0xF8294C (ROM VERSION) is tested AFTER it and never
     returns once matched.

The bit -> screen table this produces is what the PORT_NAMEs in
src/mame/matsushita/wsa1_cpanel.cpp say, and nothing else in the driver.
"""
import sys, pathlib

ROOT = pathlib.Path("/home/fsanches/compartilhado/technics_roms/roms/wsa1")
IMG  = {"prom_a": (ROOT / "wsa1_os_v2.ic12", 0xF80000),
        "prom_b": (ROOT / "wsa1_os_v2.ic13", 0xF00000)}
DATA = {k: (p.read_bytes(), base) for k, (p, base) in IMG.items()}

FAIL = 0
def chk(cond, what, extra=""):
    global FAIL
    print(("  ok   " if cond else "  FAIL ") + what + ("   " + extra if extra else ""))
    if not cond:
        FAIL += 1

def at(img, addr, n):
    d, base = DATA[img]
    return d[addr - base: addr - base + n]

print("1. RESET reaches the service test")
# `call` is opcode 0x1D + a 3-byte little-endian address; `jp` is 0x1B the same way.
c = at("prom_a", 0xF827F8, 4)
chk(c[0] == 0x1d and int.from_bytes(c[1:4], "little") == 0xF40148,
    "prom_a 0xF827F8 is `call 0xF40148`", c.hex())
thunk = at("prom_b", 0xF40148, 4)
chk(thunk[0] == 0x1b and int.from_bytes(thunk[1:4], "little") == 0xF952FC,
    "prom_b 0xF40148 is `jp 0xF952FC`", thunk.hex())

print("2. the model strap picks which chord is read")
chk(at("prom_a", 0xF952FC, 4) == bytes.fromhex("c0c43f02"),
    "0xF952FC is `cp (0xC4),0x02`")
chk(at("prom_a", 0xF95302, 3) == bytes.fromhex("1ec800"),
    "strap == 2 (RACK)     -> calr 0xF953CD, the panel-button chord")
chk(at("prom_a", 0xF95307, 3) == bytes.fromhex("1e0100"),
    "strap != 2 (KEYBOARD) -> calr 0xF9530B, the keybed chord")

print("3. sub_F953CD: the SEG1 shadow, five equality tests, four screen ids")
chk(at("prom_a", 0xF953CE, 4) == bytes.fromhex("f1702034"), "`lda XIX,0x2070` at 0xF953CE")
chk(at("prom_a", 0xF953D2, 4) == bytes.fromhex("c1312b23"), "`ld C,(0x2B31)` at 0xF953D2")

# (value, address of the `cp`, encoding) -- the first two are the short forms.
cps = [(0x02, 0xF953D8, bytes.fromhex("d9da")),
       (0x04, 0xF953DC, bytes.fromhex("d9dc")),
       (0x08, 0xF953E0, bytes.fromhex("d9cf0800")),
       (0x10, 0xF953E6, bytes.fromhex("d9cf1000")),
       (0x20, 0xF953EC, bytes.fromhex("d9cf2000"))]
for v, a, enc in cps:
    chk(at("prom_a", a, len(enc)) == enc, f"compares (0x2B31) against 0x{v:02X} at 0x{a:06X}")

screens = [(0x04, 0xD9, 0xF953F4, "PANEL CPU CHECK"),
           (0x08, 0xDA, 0xF953F9, "SINE WAVE CHECK"),
           (0x10, 0xDB, 0xF9540B, "PANEL SW&LED CHECK"),
           (0x20, 0xDC, 0xF95410, "screen cycler")]
for bit, sid, a, name in screens:
    enc = bytes([0xB4, 0x00, sid])
    chk(at("prom_a", a, 3) == enc,
        f"SEG1 value 0x{bit:02X} -> `ld (XIX),0x{sid:02X}` at 0x{a:06X}  = {name}")
for a in (0xF953FC, 0xF95413):
    chk(at("prom_a", a, 5) == bytes.fromhex("f1712000 80".replace(" ", "")),
        f"`ld (0x2071),0x80` at 0x{a:06X}")

print("4. (0x2B31) is wire 0xC1, i.e. SEG1")
wire = 0xC1
idx = (wire & 0x0F) | ((wire & 0x40) >> 2)
chk(0x2B20 + idx == 0x2B31, f"0x2B20 + ((0xC1 & 0x0F) | ((0xC1 & 0x40) >> 2)) = 0x{0x2B20+idx:04X}")
chk(at("prom_b", 0xF5B0FD, 3) == bytes.fromhex("c8cc4f"), "SC1_RxOp0 masks the wire with 0x4F at 0xF5B0FD")
chk(at("prom_b", 0xF5B10A, 3) == bytes.fromhex("c8ca30"), "and subtracts 0x30 when bit 6 is set, at 0xF5B10A")
chk(at("prom_b", 0xF5B10F, 2) == bytes.fromhex("8331"),
    "`ex (XHL),A` at 0xF5B10F -- the shadow holds the VALUE, not a change mask")

print("5. where this chord sits among the four RESET chords")
order = [(0xF827E5, 0xF828D1, "FACTORY CLEAR"),
         (0xF827F8, 0xF40148, "SERVICE (this one)"),
         (0xF8280E, 0xF8294C, "ROM VERSION"),
         (0xF82813, 0xF82A04, "third")]
# Three of the four are `calr` (0x1E + a signed 16-bit displacement from the end
# of the instruction); only the service test is a full `call` (0x1D + 24 bits).
for site, target, name in order:
    b = at("prom_a", site, 4)
    if b[0] == 0x1E:
        disp = int.from_bytes(b[1:3], "little", signed=True)
        ok, form = (site + 3 + disp == target), "calr"
    else:
        ok, form = (b[0] == 0x1D and int.from_bytes(b[1:4], "little") == target), "call"
    chk(ok, f"0x{site:06X} {form}s 0x{target:06X}  -- {name}", b.hex())
b = at("prom_a", 0xF829A3, 2)
chk(b == bytes.fromhex("68e9"),
    "0xF829A3 is an unconditional BACKWARD `jr T` -- the ROM-VERSION arm never returns")

print()
print("THE TABLE THIS PRODUCES (what wsa1_cpanel.cpp's CP_SEG1 PORT_NAMEs say):")
print("  SEG1 SW1 (0x02)  recognised, no screen")
for bit, sid, a, name in screens:
    print(f"  SEG1 SW{bit.bit_length()-1} (0x{bit:02X})  screen 0x{sid:02X}  {name}")
print()
print("FAILURES:", FAIL)
sys.exit(1 if FAIL else 0)
