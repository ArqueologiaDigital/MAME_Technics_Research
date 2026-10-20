# ic23_file.py IC23_NVRAM_FILE [--corrupt OFFSET] -- what does a saved nvram/kn7000/ic23 hold?
# Prints: size, non-zero bytes, the stored checksum (u32 LE at 0x30174), the computed one (one's complement of the
# sum of the u32 LE words at offsets 4..0x7A0, as SumU32Words(0x84000000, 0x7A0) walks them), and whether they
# match -- the test the firmware applies at boot. With --corrupt OFFSET, first flips every bit of the byte at OFFSET (hex) in place, to simulate a stray write.
import struct, sys
p = sys.argv[1]
d = bytearray(open(p, "rb").read())
if len(sys.argv) > 3 and sys.argv[2] == "--corrupt":
    o = int(sys.argv[3], 16); d[o] ^= 0xFF; open(p, "wb").write(d)
    print("corrupted byte 0x%X -> %02X" % (o, d[o]))
s = sum(struct.unpack("<%dI" % (0x7A0 // 4), bytes(d[4:0x7A4]))) & 0xFFFFFFFF
comp = (~s) & 0xFFFFFFFF
stored = struct.unpack_from("<I", d, 0x30174)[0]
print("size=%d nonzero=%d stored=%08x computed=%08x match=%s" % (len(d), sum(1 for b in d if b), stored, comp, stored == comp))
