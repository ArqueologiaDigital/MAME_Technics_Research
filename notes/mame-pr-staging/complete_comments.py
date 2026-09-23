"""Re-extend comments that trimming cut off mid-sentence, using the overlay's original."""
import importlib.util, os, re, sys
spec = importlib.util.spec_from_file_location('c', '/home/fsanches/compartilhado/kn7000_mame/tools/check_truncated_comments.py')
chk = importlib.util.module_from_spec(spec); spec.loader.exec_module(chk)
OVDIR = '/home/fsanches/compartilhado/kn7000_mame/'
MAXADD = 3

def ends_sentence(body):
    b = body.rstrip()
    return b.endswith(('.', '!', '?')) or b.endswith('.)')

total_fixed = total_left = 0
for path in sys.argv[1:]:
    hits = chk.check(path)
    if not hits:
        continue
    ovp = OVDIR + path
    if not os.path.exists(ovp):
        print('%s: no overlay counterpart, skipping %d hits' % (path, len(hits))); total_left += len(hits); continue
    O = open(ovp, encoding='utf-8', errors='replace').read().split('\n')
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
    # work bottom-up so earlier line numbers stay valid
    fixed = 0
    for ln, comment, _nxt in sorted(hits, key=lambda h: -h[0]):
        key = comment.strip()
        j = next((k for k, l in enumerate(O) if l.strip() == key), None)
        if j is None:
            continue
        indent = comment[:len(comment) - len(comment.lstrip())]
        add = []
        k = j + 1
        while k < len(O) and O[k].strip().startswith('//') and len(add) < MAXADD:
            body = O[k].strip()[2:].strip()
            if chk.is_rule(body):
                break
            add.append(indent + O[k].strip())
            if ends_sentence(body):
                break
            k += 1
        if not add:
            continue
        if not ends_sentence(add[-1].strip()[2:].strip()):
            continue                      # would still dangle; leave for a human
        lines[ln - 1:ln - 1 + 1] = [lines[ln - 1]] + add
        fixed += 1
    open(path, 'w').write('\n'.join(lines))
    total_fixed += fixed
    print('%-44s completed %d of %d' % (path, fixed, len(hits)))
print('\ncompleted %d' % total_fixed)
