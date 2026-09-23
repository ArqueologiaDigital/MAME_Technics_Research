"""The last two truncations, whichever indentation the file uses."""
PAIRS = [
    ('// 0x50000000 work RAM (the same one-bit window pair as 0x4C/0x8C and 0x44/0x84). The',
     '// 0x50000000 work RAM, the same one-bit window pair as 0x4C/0x8C and 0x44/0x84.'),
    ('// the KN5000 firmware calls "keyboard input" (KN5000 0x110000: read voice events,',
     '// what the KN5000 firmware calls "keyboard input".'),
]
p = 'src/mame/matsushita/kn7000.cpp'
lines = open(p, encoding='utf-8').read().split('\n')
n = 0
for i, l in enumerate(lines):
    for old, new in PAIRS:
        if l.strip() == old:
            indent = l[:len(l) - len(l.lstrip())]
            lines[i] = indent + new
            n += 1
open(p, 'w').write('\n'.join(lines))
print('fixed', n)

# appended: the SD card-detect one, which only exists once the SD commit lands
EXTRA = [
    ('// card-detect line (cover closed + card in = accessible; cover open => the',
     '// card-detect line: closed with a card in means accessible, open means absent.'),
]
lines = open(p, encoding='utf-8').read().split('\n')
n2 = 0
for i, l in enumerate(lines):
    for old, new in EXTRA:
        if l.strip() == old:
            indent = l[:len(l) - len(l.lstrip())]
            lines[i] = indent + new
            n2 += 1
open(p, 'w').write('\n'.join(lines))
print('extra fixed', n2)
