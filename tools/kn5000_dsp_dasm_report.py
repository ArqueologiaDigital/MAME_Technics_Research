#!/usr/bin/env python3
"""kn5000_dsp_dasm_report.py -- rank the uPD6383GF words the disassembler cannot decode.

Runs the REAL MAME disassembler (via tools/kn5000_dsp_dasm_harness.cpp, or unidasm in a
full build) over every extracted microprogram image and counts what comes back as
`?word', by word and by (hi12, class4, lo12) family.  The output is the worklist in
notes/kn5000-dsp-core-draft.md.

Usage:
    python3 tools/kn5000_dsp_extract.py <subprogram rom> <scratch>/progs
    g++ ... -o <scratch>/dasmharness tools/kn5000_dsp_dasm_harness.cpp   # see that file
    python3 tools/kn5000_dsp_dasm_report.py <scratch>
"""
import glob, os, re, subprocess, collections, sys
S = sys.argv[1]
NAMES = {}
for line in open("notes/kn5000-dsp-effect-map.md"):
    m = re.match(r'^\*\*`([A-Z0-9 .+]+)` \(algo (\d+)', line)
    if m: NAMES[int(m.group(2))] = m.group(1)

# distinct images: representative = lowest algo number with that content
imgs = {}
skipped = []
for f in sorted(glob.glob(S + "/progs/algo*.bin")):
    n = int(re.search(r'(\d+)', os.path.basename(f)).group(1))
    d = open(f, "rb").read()
    # VALID = ends with the terminator landmark (class4==1, addr8 in {0E,0F});
    # 91 of 96 extracted streams do, the 5 that do not are the malformed ones
    last = int.from_bytes(d[-5:], "big") & 0xfffffffff
    if not (((last >> 20) & 0xf) == 1 and ((last >> 12) & 0xff) in (0x0e, 0x0f)):
        skipped.append(n); continue
    imgs.setdefault(d, []).append(n)

# valid = terminator-bearing, <=384 words, address in range (extractor already filters)
def words(d): return [int.from_bytes(d[i:i+5], "big") & 0xfffffffff for i in range(0, len(d)-4, 5)]

def label(algos):
    a = algos[0]
    nm = NAMES.get(a)
    return (nm if nm else "algo%02d" % a) + ("" if len(algos) == 1 else " (x%d)" % len(algos))

# run the real disassembler over every image, parse its output
out = subprocess.run([S + "/dasmharness"] + sorted(glob.glob(S + "/progs/algo*.bin")),
                     capture_output=True, text=True).stdout

undec = collections.Counter()          # occurrences over distinct images
undec_imgs = collections.defaultdict(set)
dec_count = 0
tot = 0
per_class = collections.Counter()
ann = {}
for d, algos in imgs.items():
    lab = label(algos)
    ws = words(d)
    tot += len(ws)
    for w in ws:
        pass
# reparse disassembly per file for annotations, but count only over distinct images
reps = {algos[0]: d for d, algos in imgs.items()}
cur = None
for line in out.splitlines():
    if line.startswith("==="):
        n = int(re.search(r'algo(\d+)\.bin', line).group(1))
        cur = n if n in reps else None
        continue
    if cur is None: continue
    m = re.match(r'\s*\d+\s+(\S+)\s*(.*)', line)
    if not m: continue
    mn, rest = m.group(1), m.group(2)
    if mn == "?word":
        w = int(rest.split()[0], 16)
        note = ""
        b = rest.find("[")
        if b >= 0: note = rest[b+1:rest.rfind("]")]
        ann[w] = note
        undec[w] += 1
        undec_imgs[w].add(cur)
    else:
        dec_count += 1

total_words = sum(undec.values()) + dec_count
print("valid programs: %d   malformed (no terminator), excluded: %s" % (sum(len(v) for v in imgs.values()), skipped))
print("distinct images: %d" % len(imgs))
print("words over distinct images: %d   decoded: %d (%.1f%%)   undecoded: %d (%.1f%%)"
      % (total_words, dec_count, 100.0*dec_count/total_words,
         sum(undec.values()), 100.0*sum(undec.values())/total_words))
print("distinct undecoded words: %d" % len(undec))
cum = 0
tu = sum(undec.values())
print()
print("| rank | word | fields | n | %% of undecoded | cum %% | images | annotation |")
print("|---:|---|---|---:|---:|---:|---:|---|")
for i, (w, n) in enumerate(undec.most_common(40), 1):
    cum += n
    hi, cl, ad, lo = (w>>24)&0xfff, (w>>20)&0xf, (w>>12)&0xff, w&0xfff
    print("| %d | `0x%010X` | `%03X.%X.%02X.%03X` | %d | %.1f%% | %.1f%% | %d | %s |"
          % (i, w, hi, cl, ad, lo, n, 100.0*n/tu, 100.0*cum/tu, len(undec_imgs[w]), ann.get(w,"")))
print()
# grouped by (hi12, class, lo12) family -- addr8 is an operand
fam = collections.Counter(); famimg = collections.defaultdict(set)
for w, n in undec.items():
    k = ((w>>24)&0xfff, (w>>20)&0xf, w&0xfff)
    fam[k] += n; famimg[k] |= undec_imgs[w]
print("distinct undecoded FAMILIES (hi12,class4,lo12): %d" % len(fam))
cum = 0
print("| rank | family | n | %% | cum %% | images |")
print("|---:|---|---:|---:|---:|---:|")
for i, (k, n) in enumerate(fam.most_common(30), 1):
    cum += n
    print("| %d | `%03X.%X.**.%03X` | %d | %.1f%% | %.1f%% | %d |" % (i, k[0], k[1], k[2], n, 100.0*n/tu, 100.0*cum/tu, len(famimg[k])))
