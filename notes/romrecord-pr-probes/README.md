# ROM-record PR verification probes

The evidence behind the pre-submission review of the Technics ROM-record PR
(`~/compartilhado/mame-pr`, branch `technics-rom-record`). They exist so the central claim —
*every declared hash matches real data* — can be re-checked by anyone, including us, rather than
taken on trust from a review.

| script | the question it answers |
|---|---|
| `hash.py` | CRC32 / SHA1 / size of any files given as arguments. The workhorse. |
| `regions.py` | Parse `ROM_START` / `ROM_REGION` / `ROM_LOAD` out of the PR's `kn7000.cpp`, so declared sizes can be compared against what is actually loaded. |
| `deint.py` | Do the KN7000 per-chip even/odd halves derive correctly from our stored payload, and with which padding byte? |
| `weave.py` | The inverse for the KN2400: interleave our even/odd halves and hash the result. |
| `sect.py` | Compare the nine custom-flash images sector by sector — which 64 KB sectors are shared and which differ. |

## Result, 2026-08-18

**All declared hashes match real content: 0 of 20 unique entries lack matching data** in
`technics_roms`. Three reviewers recomputed independently and agreed; the check was then
reproduced a fourth time from scratch.

⚠ **But not by filename.** The PR declares MAME per-chip names — `kn7000_program_even.ic17`,
`kn6000_program_odd.ic11`, `kn2400_program_even.ic13` and so on — while our collection stores the
same bytes as payloads (`kn7000_program_even.rom`). Ten of the twenty-one entries therefore name
nothing that exists on disk *under that name*. Verification has to match on **content**, not on
filename, and anyone trying to actually run the PR's driver will need the files renamed into a
romset first. A naive by-name check reports 11 of 21 and looks like a failure; it is not one.

## How to re-verify the whole set

```
cd ~/compartilhado/kn7000_mame
python3 - <<'PY'
import re, zlib, hashlib, glob
src = open('/home/fsanches/compartilhado/mame-pr/src/mame/matsushita/kn7000.cpp').read().replace('\\\n','\n')
ents = dict((n,(c.lower(),s.lower())) for n,c,s in re.findall(
    r'ROM[X]?_LOAD\w*\(\s*"([^"]+)"[^)]*?CRC\(([0-9a-fA-F]+)\)\s*SHA1\(([0-9a-fA-F]+)\)', src))
have = {}
for p in glob.glob('/home/fsanches/compartilhado/technics_roms/roms/**/*', recursive=True):
    try: d = open(p, 'rb').read()
    except Exception: continue
    if d: have[f"{zlib.crc32(d)&0xffffffff:08x}"] = p
print(sum(1 for c, s in ents.values() if c not in have), "of", len(ents), "declared hashes have NO matching content")
PY
```

Related: the review also found two things that do *not* work and are recorded in the PR discussion
— the flash device tag (`customflash`) not matching the ROM region tag (`custom_data`), so the
images are read by nothing; and the HD-SX3 work RAM being mapped entirely outside its own window.
