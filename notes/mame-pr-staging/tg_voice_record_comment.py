"""Correct the voice-record comment: the sample roots ARE dumped.

QUESTION IT ANSWERS
  "Why can the driver not read the sounding pitch off the tone generator's own
   bus, instead of out of the firmware's work RAM?"

  The comment answered "because the wave ROMs that carry the per-sample roots
  have no dump". That is false, and it was published in the source, in the
  project notes and in a report before being measured. The root data is in the
  DUMPED table ROM and re-derives from kn7000_table_{even,odd} with no note
  played: a zone table of 864 sixteen-byte records at 0x48131DF0 (+9/+0xA low
  and high key, +0xB centre key, +0xC fixed pitch16, +0xF scale-tune index),
  with per-sample corrections behind zone+4. Measured in
  notes/tg-pitch-probes/, which carries the same correction.

  What actually keeps the dependency is INDIRECTION, not missing data. What
  reaches the chip is a rate relative to the selected zone's native rate --
  pitch18 = (pitch16 + 0x1800) << 2, 0x400 per semitone, 0x4280 meaning "zone
  centre at native rate" -- so recovering the sounding note from the bus means
  following the zone and element tables through pointers the firmware builds in
  work RAM. That is a larger piece of work than a register decode, and it is
  possible; the old comment asserted it was not.

  The rewritten comment also drops the shape this project has now been caught
  by three times: a claim of the form "there is no other way", about a search
  whose boundary is never stated.

RUN   python3 tg_voice_record_comment.py      (from the PR worktree root)
PASS  the comment no longer names an undumped ROM; the driver still builds.
"""

TARGET = 'src/mame/matsushita/kn7000.cpp'


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        if old not in s:
            raise SystemExit('NOT FOUND in %s: %r' % (path, old[:70]))
        s = s.replace(old, new, 1)
    open(path, 'w').write(s)


edit(TARGET, [
("""// The tone generator plays the musical pitch the firmware computes, and the
// driver reads it out of the firmware's per-slot voice record (0xB4 stride) at
// these bases. This is the one dependency that has not been replaced: the raw
// 18-bit pitch the tone generator receives is relative to a per-sample root, and
// the wave ROMs that would carry those roots have no dump. Decoding the register
// classes that name the sample would remove it; see the tone generator's notes.
""",
 """// The tone generator plays the musical pitch the firmware computes, and the
// driver reads it out of the firmware's per-slot voice record (0xB4 stride) at
// these bases. What the chip is given is a rate relative to the selected wave
// zone's native rate, 0x400 per semitone, so recovering the sounding note from
// the bus means following the zone and element tables -- which are in the dumped
// table ROM -- through pointers the firmware builds in work RAM.
"""),
])

print('tg_voice_record_comment: driver comment corrected')
