import sys, zlib, hashlib, os
for p in sys.argv[1:]:
    try:
        d = open(p,'rb').read()
    except Exception as e:
        print(f"MISSING\t{p}\t{e}"); continue
    print(f"{zlib.crc32(d)&0xffffffff:08x}\t{hashlib.sha1(d).hexdigest()}\t{len(d)}\t{p}")
