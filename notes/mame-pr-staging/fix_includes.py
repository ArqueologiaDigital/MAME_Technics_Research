"""Put the driver's include block in MAME's documented order.

QUESTION IT ANSWERS
  "Does this file follow the include-group order the rest of src/mame uses?"

  It did not: the local device headers sat in the middle of the bus/cpu/machine
  group, that group was unsorted, and <atomic> came after the .lh. The order
  below -- emu.h, local headers, the src/devices group sorted, then
  screen/speaker, then stdlib, then the layout -- is what the same author's
  already-merged kn5000.cpp uses.

  The trailing // comments go too. The fleet rate for commented include lines is
  0.55%, kn5000.cpp has none, and "why" belongs in the PR description -- the
  point already raised against this author twice. The two that carried a real
  fact (the ADSP-21065L identification and the uPD765-family part number) are in
  the driver's hardware-inventory header comment.

  This is a TRANSFORM rather than a text pair, because the block's contents
  differ per commit in the stack: the floppy commit adds upd765.h, the SD commit
  spi_sdcard.h, the MIDI commit the three midi headers. Sorting whatever is
  present is the only thing that replays correctly across all five.

RUN   python3 fix_includes.py          (from the PR worktree root)
PASS  prints the new block; the file must still compile.
"""
import re

TARGET = 'src/mame/matsushita/kn7000.cpp'

GROUPS = (
    ('local',  lambda inc: not inc.startswith(('bus/', 'cpu/', 'imagedev/', 'machine/', 'sound/', 'video/'))
                           and inc not in ('screen.h', 'speaker.h') and not inc.endswith('.lh')),
    ('device', lambda inc: inc.startswith(('bus/', 'cpu/', 'imagedev/', 'machine/', 'sound/', 'video/'))),
    ('core',   lambda inc: inc in ('screen.h', 'speaker.h')),
)


def TRANSFORM(s):
    """Reorder the include block; leave everything else untouched."""
    m = re.search(r'(#include "emu\.h"\n)(.*?)(\n\n(?:namespace|//|/\*|class|\w))', s, re.S)
    if not m:
        return s
    body = m.group(2)
    quoted = re.findall(r'^#include "([^"]+)"', body, re.M)
    angled = re.findall(r'^#include <([^>]+)>', body, re.M)
    if not quoted:
        return s
    lh = [i for i in quoted if i.endswith('.lh')]
    buckets = {name: sorted(i for i in quoted if pred(i) and not i.endswith('.lh'))
               for name, pred in GROUPS}
    out = ['']
    for name, _ in GROUPS:
        if buckets[name]:
            out += ['#include "%s"' % i for i in buckets[name]] + ['']
    if angled:
        out += ['#include <%s>' % i for i in sorted(angled)] + ['']
    if lh:
        out += ['#include "%s"' % i for i in lh] + ['']
    return s[:m.start(2)] + '\n'.join(out).rstrip('\n') + s[m.end(2):]


if __name__ == '__main__':
    src = open(TARGET, encoding='utf-8').read()
    out = TRANSFORM(src)
    open(TARGET, 'w').write(out)
    print(re.search(r'#include "emu\.h"\n.*?\n\n(?=namespace|//|/\*|class|\w)', out, re.S).group()[:700])
