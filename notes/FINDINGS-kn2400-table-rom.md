# KN2400/KN2600 — what the undumped table ROM is actually asked for

*2026-08-15. Rig: `tools/rigs/kn24_tableshape.lua`, run as
`TAP_UNTIL=30 ./tools/rig.sh kn24_tableshape kn2400 -s 32`. Deterministic — two runs gave
identical totals, widths and block counts.*

## Background

The KN2400 and KN2600 render almost nothing: `gate.sh` floors them at `distinct=4`, against
12–20 for every other model, and that floor is recorded as *a known defect, not a healthy
baseline*. The visible symptom (screenshot, 2026-08-14) is specific — **icons draw correctly**
(the grand-piano glyphs in the part cells are clean) while **every run of text renders as a
solid black bar**. So the blitter and compositor work; each glyph comes back fully set.

The driver declares `0x48000000-0x483FFFFF` as `ROMREGION_ERASEFF` because no such chip is
dumped for this family, and all-`0xFF` glyph data draws as a filled cell — exactly the symptom.
`kn24_fontsrc.lua` confirmed the region *is* read: 164,300 reads starting t=0.84 s. (An earlier
note in `kn2400-boot.md` said the firmware reads nothing from that range; that tap covered
**boot only**, and was superseded.)

This note answers the next question — *what shape of data does it expect?* — because that is
the part that survives: nobody can dump this ROM today, but the access pattern is a **test a
candidate dump can be checked against** when one appears.

## Measured

| | |
|---|---|
| total reads | **164,300** |
| when | **t=0 … t=6 only.** `0:60562  1:452  2:94942  5:42  6:8302`, then **nothing** for the remaining 24 s |
| share landing in the first `0x40` bytes | **67.6 %** |
| access widths | 1-byte **67,969** · 2-byte **37,160** · 4-byte **59,171** |
| distinct 256 B blocks touched | **113** (≈29 KB of a 4 MB region) |
| block discovery order | strictly ascending: `+0x0 +0x100 +0x200 +0x300 … +0xB00` |

Hottest individual addresses, all 4-byte aligned inside the first `0x40`:

```
+0x014  23392      +0x01C   8616
+0x020  19484      +0x024   4354
+0x018  11004      +0x010   4264
+0x00C  10906      +0x040   3834
+0x000   9720      +0x004   3765
```

## What this supports

1. **There is a descriptor in the first `0x40` bytes** — roughly sixteen 32-bit fields, consulted
   constantly (two thirds of all traffic) while the firmware walks entries. The mixed 1/2/4-byte
   widths fit a structure of dword pointers/lengths alongside byte-wide payload.
2. **The load is bounded and happens at boot.** It stops at t=6 and never resumes.
3. **Therefore text drawing does not fetch from this ROM.** At t=25 the play screen is up and
   drawing black bars, and in that whole window there is not one read of the region. Whatever
   the firmware wanted, it took once, early, into RAM — and the bars are drawn from that copy.

That third point is new, and it changes where to look.

## What this does NOT support

⚠ **The addresses walked beyond the header are artefacts.** The descriptor reads back as all
`0xFF`, so every pointer and length the firmware derives from it is garbage — the 113 blocks and
the tidy ascending order are what an all-`0xFF` descriptor produces, not evidence about the real
chip's layout. Only ~29 KB of a 4 MB region is touched, and that number is a property of the
missing data, not of the ROM.

The solid findings are the ones that do not depend on the contents: *there is a header at offset
0, it is about `0x40` bytes of dword fields, it is read before anything else, and the whole
transaction is over by t=6.*

## Two things this makes possible without a dump

* **A verification test.** A candidate dump must carry a plausible descriptor in its first
  `0x40` bytes, and mounting it must *change this access pattern* — traffic should extend well
  past 29 KB and stop looking like a walk over `0xFF`. Re-running this rig against a candidate
  is a cheap, honest first check before anything is declared good.
* **A RAM-side investigation that can start now.** Since drawing works from a boot-time RAM
  copy, the destination buffer can be found and inspected on the current build — no hardware
  needed. Find where the t=0…6 reads are written to, and the glyph path can be characterised
  end to end even while the source ROM is missing.

## Reproduce

```
./tools/rig.sh kn24_tableshape kn2400 -s 32          # this note
./tools/rig.sh kn24_fontsrc    kn2400 -s 32          # the whether-at-all check it builds on
```

Both print a verdict line. `kn24_tableshape`'s first verdict logic classified on "was a block
touched in more than one second", which put 112 of 113 blocks in a "repeated" bucket and
reported a useless *mixed*; it now classifies on whether traffic **ceases** and how concentrated
it is. Recorded because the rig's own criterion had to be fixed before its answer meant anything.
