# Question: is the service ROM test that sums 2 MB at 0x97800000 (0x4849FD9E, called from MainRomTestFunc;
# expected value 0x21D8) the test of IC19, the picture ROM, read through the uncached 0x9xxxxxxx view of
# 0x57800000? It sums little-endian 16-bit words, so a match also confirms the dump's byte order.
# Usage: python3 -I ic19_rom_test_sum.py <c3cbmd000098.ic19>      prints the 16-bit sum; 0x21d8 = match
import struct, sys
d = open(sys.argv[1], 'rb').read()
print(hex(sum(struct.unpack('<%dH' % (len(d) // 2), d)) & 0xffff))
