#!/usr/bin/env python3
"""Census every TMP94C241 SFR access in a Technics disassembly tree.

Question it answers: "which I/O port, timer, serial or interrupt register does
this firmware actually read or write, from which routine, and what does it do
with the value?"  That is the evidence a MAME driver port binding needs, and it
is the only way to settle a signal's POLARITY: you cannot read polarity off one
call site, you have to see every writer and every reader together.

Usage:
    ./sfr_census.py <tree> [<tree> ...]            # all SFRs
    ./sfr_census.py --only PD,PE,PG,PH <tree>      # just these registers
    ./sfr_census.py --summary <tree>               # one line per register

Trees are directories or single .s files, e.g.

    ./sfr_census.py ~/compartilhado/kn5000-roms-disasm/v10/maincpu
    ./sfr_census.py ~/compartilhado/kn5000-roms-disasm/v142/subcpu \
                    ~/compartilhado/kn5000-roms-disasm/subcpu

Output columns:  REG  file:line  routine  instruction  ; comment  [MISFRAME?]

MISFRAME? is a warning, not a verdict: it means .byte directives appear within
12 lines, which in these trees is the signature of a DATA region the
disassembler framed as code.  Hits so flagged must not be counted as real
accesses without looking at them.

SFR name/address table transcribed from the disassembly's own header,
kn5000-roms-disasm/v10/maincpu/shared/sfr_tmp94c241.s (identical copy at
v142/subcpu/shared/sfr_tmp94c241.s).  Note PG = 0x40 and PZ = 0x68: they are
different ports and a claim that names one and cites the other's number is
wrong on its face.
"""
import os, re, sys, argparse

SFR = {
 0x00:'P0',  0x02:'P0CR', 0x03:'P0FC', 0x04:'P1',  0x06:'P1CR', 0x07:'P1FC',
 0x08:'P2',  0x0A:'P2CR', 0x0B:'P2FC', 0x0C:'P3',  0x0E:'P3CR', 0x0F:'P3FC',
 0x10:'P4',  0x12:'P4CR', 0x13:'P4FC', 0x14:'P5',  0x16:'P5CR', 0x17:'P5FC',
 0x18:'P6',  0x1A:'P6CR', 0x1B:'P6FC', 0x1C:'P7',  0x1E:'P7CR', 0x1F:'P7FC',
 0x20:'P8',  0x22:'P8CR', 0x23:'P8FC',
 0x28:'PA',  0x2B:'PAFC', 0x2C:'PB',   0x2F:'PBFC',
 0x30:'PC',  0x32:'PCCR', 0x33:'PCFC', 0x34:'PD',  0x36:'PDCR', 0x37:'PDFC',
 0x38:'PE',  0x3A:'PECR', 0x3B:'PEFC', 0x3C:'PF',  0x3E:'PFCR', 0x3F:'PFFC',
 0x40:'PG',
 0x44:'PH',  0x46:'PHCR', 0x47:'PHFC', 0x68:'PZ',  0x6A:'PZCR',
 0x80:'T8RUN',0x81:'TRDC',0x82:'T02FFCR',0x84:'T01MOD',0x85:'T23MOD',
 0x88:'TREG0',0x89:'TREG1',0x8A:'TREG2',0x8B:'TREG3',
 0x90:'TREG4L',0x91:'TREG4H',0x92:'TREG5L',0x93:'TREG5H',
 0x94:'CAP4L',0x95:'CAP4H',0x96:'CAP5L',0x97:'CAP5H',
 0x98:'T4MOD',0x99:'T4FFCR',0x9E:'T16RUN',0x9F:'T16CR',
 0xA0:'TREG6L',0xA1:'TREG6H',0xA2:'TREG7L',0xA3:'TREG7H',0xA8:'T6MOD',0xA9:'T6FFCR',
 0xB0:'TREG8L',0xB1:'TREG8H',0xB2:'TREG9L',0xB3:'TREG9H',0xB8:'T8MOD',0xB9:'T8FFCR',
 0xC0:'TREGAL',0xC1:'TREGAH',0xC2:'TREGBL',0xC3:'TREGBH',0xC8:'TAMOD',0xC9:'TAFFCR',
 0xD0:'SC0BUF',0xD1:'SC0CR',0xD2:'SC0MOD',0xD3:'BR0CR',
 0xD4:'SC1BUF',0xD5:'SC1CR',0xD6:'SC1MOD',0xD7:'BR1CR',
 0xE0:'INTE45',0xE1:'INTE67',0xE2:'INTE89',0xE3:'INTEAB',
 0xE4:'INTET01',0xE5:'INTET23',0xE6:'INTET45',0xE7:'INTET67',
 0xE8:'INTET89',0xE9:'INTETAB',0xEA:'INTES0',0xEB:'INTES1',
 0xEC:'INTETC01',0xED:'INTETC23',0xEE:'INTETC45',0xEF:'INTETC67',
 0xF0:'INTE0AD',0xF6:'IIMC',0xF7:'INTNMWDT',0xF8:'INTCLR',
 0x100:'DMA0V',0x101:'DMA1V',0x102:'DMA2V',0x103:'DMA3V',
 0x104:'DMA4V',0x105:'DMA5V',0x106:'DMA6V',0x107:'DMA7V',
 0x108:'DMAB',0x109:'DMAR',0x10A:'CLKMOD',0x110:'WDMOD',0x111:'WDCR',
 0x120:'ADREG04L',0x121:'ADREG04H',0x122:'ADREG15L',0x123:'ADREG15H',
 0x124:'ADREG26L',0x125:'ADREG26H',0x126:'ADREG37L',0x127:'ADREG37H',
 0x128:'ADMOD1',0x129:'ADMOD2',0x130:'DAREG0',0x131:'DAREG1',0x132:'DADRV',
 0x140:'B0CSL',0x141:'B0CSH',0x142:'MAMR0',0x143:'MSAR0',
 0x144:'B1CSL',0x145:'B1CSH',0x146:'MAMR1',0x147:'MSAR1',
 0x148:'B2CSL',0x149:'B2CSH',0x14A:'MAMR2',0x14B:'MSAR2',
 0x14C:'B3CSL',0x14D:'B3CSH',0x14E:'MAMR3',0x14F:'MSAR3',
 0x150:'B4CSL',0x151:'B4CSH',0x152:'MAMR4',0x153:'MSAR4',
 0x154:'B5CSL',0x155:'B5CSH',0x156:'MAMR5',0x157:'MSAR5',
 0x160:'DRAM0CRL',0x161:'DRAM0CRH',0x162:'DRAM1CRL',0x163:'DRAM1CRH',
 0x164:'DRAM0REF',0x165:'DRAM1REF',0x166:'PMEMCR',
}

# mnemonic -> index of the operand that holds the ADDRESS, and whether the
# access is a Read, a Write or a read-modify-write (B = both).
#
# The mnemonic set is this project's own assembler spelling (LLVM tblgen names
# emitted by the disassembler in kn5000-roms-disasm); it is NOT Toshiba syntax.
FORMS = {
    # 8-bit-direct addressing ("(nn)" where nn < 0x100)
    'ldio':        (0, 'W'), 'ldwio':      (0, 'W'),
    'ld_sd8b':     (1, 'R'), 'ld_sd8w':    (1, 'R'),
    'st_dd8b':     (1, 'W'), 'st_dd8w':    (1, 'W'),
    'bit_dd8':     (1, 'R'), 'ldcf_dd8':   (1, 'R'), 'stcf_dd8': (1, 'W'),
    'set_dd8':     (1, 'B'), 'res_dd8':    (1, 'B'), 'chg_dd8':  (1, 'B'),
    'and_sd8b_im': (0, 'B'), 'or_sd8b_im': (0, 'B'), 'xor_sd8b_im': (0, 'B'),
    'cp_sd8b_im':  (0, 'R'), 'add_sd8b_im':(0, 'B'), 'sub_sd8b_im': (0, 'B'),
    'lda_dd8l':    (1, 'R'), 'xorcf_dd8':  (0, 'R'),
    'inc_d8':      (1, 'B'), 'dec_d8':     (1, 'B'),
    'incm8':       (1, 'B'), 'decm8':      (1, 'B'),
    'ldb_d8':      (1, 'R'), 'stb_d8':     (0, 'W'),
    'ldw_d8':      (1, 'R'), 'stw_d8':     (0, 'W'),
    'ldmm_sd8b':   (0, 'R'),
    # 16-bit-direct addressing -- the SFRs above 0xFF (DMA vectors, chip
    # select, DRAM, A/D) are only reachable this way, and the disassembler
    # prints these addresses in DECIMAL.
    'stdi8':  (0, 'W'), 'stdi16': (0, 'W'), 'stdi32': (0, 'W'),
    'cpdi8':  (0, 'R'), 'cpdi16': (0, 'R'),
    'anddi8': (0, 'B'), 'anddi16':(0, 'B'), 'ordi8': (0, 'B'), 'ordi16': (0, 'B'),
    'adddi8': (0, 'B'), 'adddi16':(0, 'B'), 'subdi16': (0, 'B'),
    'incdi8': (1, 'B'), 'incdi16':(1, 'B'), 'decdi8': (1, 'B'), 'decdi16': (1, 'B'),
    'bitda':  (1, 'R'), 'setda':  (1, 'B'), 'resda':  (1, 'B'), 'chgda': (1, 'B'),
    'ldw_d16':(1, 'R'), 'lda_d16':(1, 'R'),
    'stda16': (0, 'W'), 'stda32': (0, 'W'),
    'ldb_da': (1, 'R'), 'ldw_da': (1, 'R'), 'ldl_da': (1, 'R'),
    'stb_da': (0, 'W'), 'stw_da': (0, 'W'), 'stl_da': (0, 'W'),
    'stib_da':(0, 'W'), 'stiw_da':(0, 'W'),
}

LABEL_RE = re.compile(r'^([A-Za-z_.$][A-Za-z0-9_.$]*):')
INSTR_RE = re.compile(r'^\s+([a-z][a-z_0-9]*)\b\s*(.*)$')


def num(tok):
    tok = tok.strip()
    while tok.startswith('(') and tok.endswith(')'):
        tok = tok[1:-1].strip()
    tok = tok.split(':')[0].strip()          # "(0x8a4c:16)" -> "0x8a4c"
    if re.fullmatch(r'0[xX][0-9A-Fa-f]+', tok):
        return int(tok, 16)
    if re.fullmatch(r'\d+', tok):
        return int(tok)
    return None


def walk(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p, os.path.basename(p)
            continue
        for dp, _, fns in os.walk(p):
            for f in sorted(fns):
                if f.endswith('.s'):
                    full = os.path.join(dp, f)
                    yield full, os.path.relpath(full, p)


def scan(paths):
    hits = []
    for full, rel in walk(paths):
        lines = open(full, encoding='utf-8', errors='replace').read().split('\n')
        label, cur = [None] * len(lines), None
        for i, l in enumerate(lines):
            m = LABEL_RE.match(l)
            if m:
                cur = m.group(1)
            label[i] = cur
        for i, l in enumerate(lines):
            code = l.split(';')[0]
            comment = l.split(';', 1)[1].strip() if ';' in l else ''
            m = INSTR_RE.match(code)
            if not m:
                continue
            mn, ops = m.group(1), m.group(2)
            if mn not in FORMS:
                continue
            idx, rw = FORMS[mn]
            parts = [o.strip() for o in re.split(r',(?![^()]*\))', ops)]
            if idx >= len(parts):
                continue
            a = num(parts[idx])
            if a is None or a not in SFR:
                continue
            lo, hi = max(0, i - 12), min(len(lines), i + 13)
            misframe = any(re.match(r'^\s+\.byte', c) for c in lines[lo:hi])
            hits.append(dict(reg=SFR[a], addr=a, rw=rw, file=rel, line=i + 1,
                             label=label[i], text=l.strip(), comment=comment,
                             misframe=misframe))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('trees', nargs='+')
    ap.add_argument('--only', help='comma-separated register names')
    ap.add_argument('--summary', action='store_true')
    ap.add_argument('--include-misframed', action='store_true',
                    help='by default suspected data-framed-as-code hits are still '
                         'printed but tagged; this makes no difference to output, '
                         'it exists so the flag is impossible to misread')
    a = ap.parse_args()
    hits = scan(a.trees)
    if a.only:
        want = {s.strip().upper() for s in a.only.split(',')}
        hits = [h for h in hits if h['reg'] in want]
    if a.summary:
        from collections import defaultdict
        agg = defaultdict(lambda: [0, 0, 0])   # clean R, clean W/B, misframed
        for h in hits:
            k = agg[(h['addr'], h['reg'])]
            if h['misframe']:
                k[2] += 1
            elif h['rw'] == 'R':
                k[0] += 1
            else:
                k[1] += 1
        print('%-10s %-6s %5s %5s %5s' % ('REG', 'ADDR', 'read', 'write', 'susp'))
        for (addr, reg) in sorted(agg):
            r, w, s = agg[(addr, reg)]
            print('%-10s 0x%03X %5d %5d %5d' % (reg, addr, r, w, s))
        print('\n(susp = .byte within 12 lines, i.e. probably DATA framed as code)')
        return
    for h in sorted(hits, key=lambda h: (h['addr'], h['file'], h['line'])):
        print('%-9s %s %-40s %-34s %-46s%s' % (
            h['reg'], h['rw'], '%s:%d' % (h['file'], h['line']),
            h['label'] or '-', h['text'],
            ('  ; ' + h['comment'] if h['comment'] else '') +
            ('   [MISFRAME?]' if h['misframe'] else '')))
    print('\n%d hits' % len(hits), file=sys.stderr)


if __name__ == '__main__':
    main()
