#!/usr/bin/env python3
"""avsdrv_depack.py -- depacker for the AVSLOAD$ stub inside NEC's AVSDRV.SYS.

Reversed from the 16-bit x86 stub itself (file offsets; CS:0 == file 0x200):

  0x11fa  depack(src_start:far, src_end:far, dst:far)   <- the main loop
  0x12b2  emit(count)        ring[R..R+count) -> dst (or INT21/AH=40h to file)
  0x1344  copy_match(pos,n)  ring[pos+i] -> ring[R+i], byte at a time
  0x138d  read_literals(R,n) src -> ring[R+i]
  0x13f3  wrap(x)            (x + 0x410) mod 0x410     <- RING SIZE = 1040 bytes
  0x130d  at_end()           carry set when DS:SI passed src_end

Format (MEASURED, then PROVEN BY CONSTRUCTION):
  * ring buffer of 1040 (0x410) bytes at CS:0x20, zero-initialised (rep stos ax,0)
  * cursor R starts at 0 and advances by the number of bytes produced per token
  * token selection is the LOW BIT of the next byte:
      bit0 == 0 : LITERAL RUN.  read 1 byte b; n = (b & 0xFE) >> 1  (0..127)
                  the next n bytes of src are copied into ring[R..]
      bit0 == 1 : MATCH.        read 1 word t (little endian)
                  n   = (t & 0x001E) >> 1        4 bits, 0..15
                  off = (t & 0xFFE0) >> 5       11 bits, 0..2047
                  copy ring[(R-off+i) mod 1040] -> ring[(R+i) mod 1040], i<n
  * after either case the n bytes at ring[R..R+n) are emitted, R = (R+n) mod 1040
  No end-of-stream marker: the loop stops on src pointer >= src_end.
"""
import sys, struct, hashlib

RING = 0x410

def depack(src, start, end):
    ring = bytearray(RING)
    out = bytearray()
    R = 0
    p = start
    while p < end:
        b = src[p]
        if b & 1:
            t = struct.unpack_from('<H', src, p)[0]; p += 2
            n = (t & 0x1E) >> 1
            off = (t & 0xFFE0) >> 5
            pos = (R - off) % RING
            for i in range(n):
                ring[(R + i) % RING] = ring[(pos + i) % RING]
        else:
            p += 1
            n = (b & 0xFE) >> 1
            for i in range(n):
                ring[(R + i) % RING] = src[p + i]
            p += n
        for i in range(n):
            out.append(ring[(R + i) % RING])
        R = (R + n) % RING
    return bytes(out)

# linear addresses (CS:0-relative); file offset = linear + 0x200
CHUNKS = {
    'avs_86': [('hdr', 0x9019, 0x936F), ('body', 0x120A, 0x9019)],
    'avs_cs': [('hdr', 0xDFFB, 0xE32C), ('body', 0x936F, 0xDFFB)],
}

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'AVSDRV.SYS'
    outdir = sys.argv[2] if len(sys.argv) > 2 else '.'
    d = open(path, 'rb').read()
    for name, parts in CHUNKS.items():
        blob = b''
        for tag, s, e in parts:
            u = depack(d, s + 0x200, e + 0x200)
            print('%s.%s: packed 0x%X..0x%X (%d) -> %d bytes' %
                  (name, tag, s + 0x200, e + 0x200, e - s, len(u)))
            blob += u
        fn = '%s/%s.org' % (outdir, name)
        open(fn, 'wb').write(blob)
        print('  %s  %d bytes  sha256 %s' % (fn, len(blob), hashlib.sha256(blob).hexdigest()))
        print('  first 32: %s' % blob[:32].hex(' '))

if __name__ == '__main__':
    main()

# ---------------------------------------------------------------------------
# uPD6380 microprogram extraction from the unpacked avs_86.exe
#
# INT 0D9h AH=00h "$INITFUNC" -> handler at file 0x1d4a validates AH < 0x13
# (19 functions) and calls the loader at 0x1dbb.  Records are found through
# a 19-entry word table; the code segment holding it is based 0x18C0 bytes
# into the load module (MEASURED by brute force: only that base makes all 19
# entries yield plausible records).
#
#   rec+0x04/+0x06 : far-ish offset + BYTE length of the MICROPROGRAM (I-RAM)
#   rec+0x08/+0x0A : offset + BYTE length of the COEFFICIENT/data image
#   rec+0x0C       : number of parameters
#   rec+0x0E..0x11 : parameter slot indices
#   rec+0x12 ...   : parameter descriptors, stride 9, +2 = default,
#                    +6 = byte address in coefficient RAM (divided by 3 to
#                    get the word address -> 3-byte words again)
#
# Upload loop (file 0x1e43):   words = bytecount / 3   <-- WORD SIZE = 3 BYTES
