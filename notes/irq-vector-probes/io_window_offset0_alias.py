#!/usr/bin/env python3
#
# Q: the KN7000 driver hangs five separate address windows off ONE pair of
#    handlers, io_r/io_w, and dispatches on `offset` -- which MAME measures from
#    each window's OWN base. So `case 0x00000`, written for the effects DSP's
#    host register index at 0x98000000, also catches offset 0 of the other four.
#    Which of those addresses does any firmware actually touch?
#
# A (measured, all five images): exactly one, and it was a live misroute.
#
#      0x20000000  IVAR0          1 site per image  -- the interrupt vector
#                                                      register, taken as a DSP
#                                                      register index
#      0x32000000                 0 sites
#      0x34000000                 0 sites
#      0x36008000                 0 sites
#      0x98000000  DSP host index 1-5 sites         -- what the case is FOR
#
#    The CPU core now decodes IVAR0-IVAR6 in its own internal map, which takes
#    precedence over the machine map, so that one is gone. The other three
#    windows are never accessed at offset 0 by any of the five firmwares, so the
#    shared handler needs no further change.
#
# Usage:  python3 io_window_offset0_alias.py
#
# ⚠ ENCODING TRAP, hit once here: `bset/bclr imm8,(abs32)` is
#   FE 0x <abs32> <imm8> -- the abs32 comes BEFORE the immediate. Reading it at
#   the wrong offset invented a 0x34000000 access in kn6000 that turned out to be
#   the bytes of `bclr 0x34,(0x000000c0)` sitting inside a data table. Any hit
#   this script reports should be disassembled before it is believed.
#
import zipfile, struct, glob, os
BASE=0x48400000
TARGETS = {0x20000000:'IVAR0 (now decoded by the CPU core)',
           0x32000000:'io_w offset 0 of the 0x32000000 window',
           0x34000000:'io_w offset 0 of the 0x34000000 window',
           0x36008000:'io_w offset 0 of the 0x36008000 window',
           0x98000000:'the effects-DSP host index -- what case 0x00000 is FOR'}
def deint(zp):
    with zipfile.ZipFile(zp) as z:
        n=z.namelist()
        ev=[x for x in n if 'program_even' in x]; od=[x for x in n if 'program_odd' in x]
        if not(ev and od): return None
        e,o=z.read(ev[0]),z.read(od[0])
    img=bytearray(len(e)+len(o)); img[0::4],img[1::4]=e[0::2],e[1::2]; img[2::4],img[3::4]=o[0::2],o[1::2]
    return bytes(img)

for zp in sorted(glob.glob(os.path.expanduser('~/compartilhado/technics_romsets/*.zip'))):
    img=deint(zp)
    if img is None: continue
    print('==', os.path.basename(zp))
    for addr, what in sorted(TARGETS.items()):
        store=[]; ptr=[]
        for off in range(len(img)-6):
            if img[off]==0xFC and struct.unpack_from('<I',img,off+2)[0]==addr:
                op=img[off+1]
                if 0xDC <= op <= 0xDF: ptr.append(BASE+off)
                elif op in (0x80,0x81,0x82,0x83,0x84,0x85,0x86,0x87,0x8B,0x8F,0xA0,0xA1,0xA2,0xA3):
                    store.append((BASE+off, op))
            elif img[off]==0xFE and struct.unpack_from("<I",img,off+2)[0]==addr:
                store.append((BASE+off, 0xFE))
        print('   %08X  %-48s  abs32 access sites: %d   pointer loads: %d'
              % (addr, what, len(store), len(ptr)))
