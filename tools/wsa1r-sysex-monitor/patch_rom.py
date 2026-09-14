#!/usr/bin/env python3
"""patch_rom.py -- graft the SysEx monitor into the WSA1R's prom_a image.

    python3 patch_rom.py ORIGINAL.ic12 monitor.bin OUT.ic12

WHAT IT GUARANTEES, and it refuses to write unless every one holds:

  1. the input is the ROM we think it is          -- SHA1 against the known dump
  2. the destination really is unused padding     -- every byte 0x0E for the payload's length
  3. the hook site really holds the instruction we mean to replace
  4. the output differs from the input in EXACTLY the payload plus the 4 hook bytes

⚠ It also prints the RESTORE recipe, because the whole point of a four-byte hook is that putting
the ROM back is four bytes.  `notes/HARDWARE-CUSTOM-DSP-PROGRAMS-WSA1R.md` sect. A5.
"""
import hashlib
import sys

PROM_A_BASE = 0xF80000                      # prom_a (ic12) is mapped here
PROM_A_SHA1 = "90a2369f8e4d2fcdf26875272267624b07bc200d"
PROM_A_SIZE = 0x80000

PAD_LO, PAD_HI = 0xFBA236, 0xFBABFF         # module 0xFB9000's tail padding, all 0x0E
MON_BASE = 0xFBA236
MON_ENTRY = MON_BASE + 0x10

HOOK_ADDR = 0xFA586E                        # MIDI_RX_SysExData, first instruction
HOOK_WAS = bytes([0xF0, 0xA9, 0xC9, 0x66])  # bit 0,(0xA9) + the first byte of `jr z'


def off(addr):
    return addr - PROM_A_BASE


def jp_abs24(target):
    """`jp' with a 24-bit absolute operand -- 4 bytes, the same width as the call it replaces."""
    return bytes([0x1B, target & 0xFF, (target >> 8) & 0xFF, (target >> 16) & 0xFF])


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    src, mon, dst = sys.argv[1:4]
    d = bytearray(open(src, "rb").read())
    payload = open(mon, "rb").read()

    print("input : %s  %d bytes" % (src, len(d)))
    h = hashlib.sha1(bytes(d)).hexdigest()
    print("  sha1  %s" % h)
    if len(d) != PROM_A_SIZE:
        sys.exit("  ⛔ wrong size -- expected %d" % PROM_A_SIZE)
    if h != PROM_A_SHA1:
        sys.exit("  ⛔ NOT the known prom_a dump (expected %s).\n"
                 "     Refusing to patch: if the reader is wrong, everything after is wrong."
                 % PROM_A_SHA1)
    print("  ★ gate 1 PASSED -- this is the known prom_a")

    a, b = off(MON_BASE), off(MON_BASE) + len(payload)
    if MON_BASE + len(payload) - 1 > PAD_HI:
        sys.exit("  ⛔ payload is %d bytes; the padding holds %d"
                 % (len(payload), PAD_HI - PAD_LO + 1))
    stale = [i for i, x in enumerate(d[a:b]) if x != 0x0E]
    if stale:
        sys.exit("  ⛔ destination is NOT free: %d of %d bytes are not 0x0E (first at +0x%X)"
                 % (len(stale), len(payload), stale[0]))
    print("  ★ gate 2 PASSED -- %d bytes at 0x%06X are all 0x0E (%d spare remain)"
          % (len(payload), MON_BASE, PAD_HI - (MON_BASE + len(payload)) + 1))

    ha = off(HOOK_ADDR)
    if bytes(d[ha:ha + 4]) != HOOK_WAS:
        sys.exit("  ⛔ hook site holds %s, expected %s"
                 % (bytes(d[ha:ha + 4]).hex(), HOOK_WAS.hex()))
    print("  ★ gate 3 PASSED -- hook site 0x%06X holds %s" % (HOOK_ADDR, HOOK_WAS.hex()))

    d[a:b] = payload
    hook = jp_abs24(MON_ENTRY)
    d[ha:ha + 4] = hook

    orig = open(src, "rb").read()
    diff = [i for i in range(len(d)) if d[i] != orig[i]]
    expect = set(range(a, b)) | set(range(ha, ha + 4))
    unexpected = [i for i in diff if i not in expect]
    if unexpected:
        sys.exit("  ⛔ %d bytes changed outside the payload and the hook" % len(unexpected))
    print("  ★ gate 4 PASSED -- %d bytes differ, all inside the payload + the 4 hook bytes"
          % len(diff))

    open(dst, "wb").write(bytes(d))
    print("\noutput: %s\n  sha1  %s" % (dst, hashlib.sha1(bytes(d)).hexdigest()))
    print("\nhook  : 0x%06X  %s -> %s   (jp 0x%06X)"
          % (HOOK_ADDR, HOOK_WAS.hex(), hook.hex(), MON_ENTRY))
    print("payload: 0x%06X .. 0x%06X  (%d bytes)"
          % (MON_BASE, MON_BASE + len(payload) - 1, len(payload)))
    print("\nRESTORE (if ever needed, on the patched image):")
    print("  write %s back at file offset 0x%05X, and 0x0E over 0x%05X..0x%05X"
          % (HOOK_WAS.hex(), ha, a, b - 1))
    print("  -- or simply put the ORIGINAL chip back in its socket.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
