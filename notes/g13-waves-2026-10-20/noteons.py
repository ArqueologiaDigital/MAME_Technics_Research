#!/usr/bin/env python3
"""noteons.py TRACE -- one row per voice note-on in a tg_trace.lua trace.

QUESTION: for each note the rig played, which voices did the firmware start, on which
TG, with which aux word (class 0x1C02), pitch (class 0x2400, pitch18) and the other
per-voice registers written in the same burst?

A voice's burst is every write to its (tg, channel) since its previous pitch write;
the row is emitted at the pitch write that ends the burst (the note-on)."""
import sys, collections

def parse(path):
    mark = None
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == '#':
            mark = ' '.join(p[2:])
            yield ('M', float(p[1]), mark)
        elif p[0] == 'W' and len(p) >= 5:
            t, tg, a, d = float(p[1]), int(p[2]), int(p[3], 16), int(p[4], 16)
            extra = p[5:]
            yield ('W', t, tg, a, d, extra, mark)

def noteons(path, post_window=0.002):
    """note-on rows; 'post' holds the writes to the same voice within post_window s after the pitch write"""
    regs = collections.defaultdict(dict)   # (tg,ch) -> {cls: data}
    out = []
    last = {}                              # (tg,ch) -> the row of its latest note-on
    for ev in parse(path):
        if ev[0] != 'W':
            continue
        _, t, tg, a, d, extra, mark = ev
        ch = (a >> 4) & 0x3F
        cls = a & 0xFC0F
        r = regs[(tg, ch)]
        lr = last.get((tg, ch))
        if lr is not None and t - lr['t'] <= post_window and (cls & 0xFC0E) != 0x2400:
            lr['post'].setdefault(cls, d)
        if (cls & 0xFC0E) == 0x2400:
            p18 = ((cls & 1) << 16) | d
            aux20 = [((c & 0xF) << 16) | v for c, v in r.items() if (c & 0xFC00) == 0x1C00]
            if r.get(0x0003) == 0x87FF and aux20:
                out.append(dict(t=t, tg=tg, ch=ch, p18=p18, mark=mark, regs=dict(r), post={}, aux20=aux20[-1],
                                np16=int(extra[0], 16) if extra else None))
                last[(tg, ch)] = out[-1]
            r.clear()
        else:
            r[cls] = d
    return out

if __name__ == '__main__':
    for n in noteons(sys.argv[1]):
        r = n['regs']
        aux = n['aux20']
        print('%-22s t=%9.4f tg%d ch%02x aux20=%05x page=%x entry=%02x p18=%05x np16=%s' % (
            n['mark'], n['t'], n['tg'], n['ch'], aux, (aux >> 12) & 0xFF, aux & 0xFFF, n['p18'],
            '%04x' % n['np16'] if n['np16'] is not None else '-'))
