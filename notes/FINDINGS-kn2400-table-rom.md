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

## The copy loop, found and verified (same day)

The "RAM copy" above was inference when first written. It is now located, disassembled and
its output measured. Rig: `tools/rigs/kn24_tabledest.lua`.

```
4860c25e: mov   (0x500d7398), d1     ; destination base, from RAM
4860c265: mov   0x2c8, d0            ; 712 = record stride
4860c26a: mulu  d0, d2               ; d2 = record index * 712
4860c26c: add   0x10, d1             ; records start at base+0x10
4860c26e: add   d2, d1
4860c26f: mov   d1, a1
4860c271: mov   -0x164, d1           ; 356 halfwords = 712 bytes
4860c274: setlb                      ; hardware loop
4860c275: movhu (a0), d0             ; ★ read  from the table ROM
4860c277: add   2, a0
4860c279: movhu d0, (a1)             ; ★ write to RAM
4860c27b: add   2, a1
4860c27d: inc   d1
4860c27e: lne
...
4860c282: cmp   0x28, d3             ; 40 records
4860c284: blt   0x4860c258
```

Every number in that listing was then confirmed at runtime, independently:

| predicted from the disassembly | measured |
|---|---|
| destination = `[0x500D7398] + 0x10` | pointer reads `0x502A5014` → **`0x502A5024`**, and the write tap's lowest destination is **`0x502A5024`** |
| 40 records × 712 B = 28,480 B | **28,480 writes**, span `0x502A5024..0x502ABF60` |
| source is the all-`0xFF` table ROM | destination sampled after the copy: **99.86 % `0xFF`** |

That closes the chain end to end: **undumped ROM → `ROMREGION_ERASEFF` → a 28 KB RAM buffer
of 40 fixed-size records that is essentially all `0xFF`.**

A second, partly-affected buffer sits at `0x502AC108..0x502B0808` (~18 KB, **67.6 % `0xFF`**),
filled by three sibling loops at `0x4860C05D`, `0x4860C0AC` and `0x4860C130`.

⚠ **One attribution was rejected by measuring it.** The readers at `0x486FA939-0x486FA979`
matched a RAM writer 64 bytes away, which would have credited them with a 118 KB buffer at
`0x5038DCE0..0x503AAA84`. That buffer is **0.00 % `0xFF`** and 91 % zero, so it is not
table-ROM data and those reads feed something else. The content check exists precisely to
catch this; without it the write-up would have claimed 118 KB of damage that is not there.

## Tested: these buffers are NOT what draws the black bars

The obvious next inference — *the buffer is `0xFF`, the glyph cells draw solid, therefore the
buffer is the glyph source* — was tested and **does not hold**. Rig:
`tools/rigs/kn24_bufferpoke.lua`, comparing full-frame PNG snapshots between runs.

| run | frame vs control |
|---|---|
| buffer 1 `0x502A5024..0x502ABF63` (28,480 B) overwritten with `0x00` | **bit-identical** |
| buffer 2 `0x502AC108..0x502B0808` (18,177 B) overwritten with `0x00` | **bit-identical** |
| **positive control** — the framebuffer at `0x9C800000` overwritten with `0xFF` | **differs** ✓ |

The screenshot confirms the bars are genuinely on screen and would be sampled: four solid
black rectangles where text belongs, beside cleanly-drawn grand-piano icons in the part cells.
So the test had something to see, the method demonstrably reaches the display, and the answer
is negative.

### Getting the timing right was the entire experiment

The first two attempts poked at t=20 and t=7 and both returned "no change" — **and both were
worthless**. `tools/rigs/kn24_fbwrites.lua` measured why:

```
FB writes=67201 first=0.25s last=11.13s
FB per second -- 0:38400 2:9600 6:19200 11:1
```

The KN2400 composites its screen at **t=6** (19,200 bytes = exactly the full 320×240 2bpp
buffer) and never repaints after t=11.13. A poke at t=7 is already too late: the screen on
display was drawn before it, so *no* buffer could have shown an effect. The valid test holds
the buffer overwritten *across* the paint — here 45 repeated pokes spanning t=4…9 — and only
that version is evidence.

This is the same trap as the positive control passing for the wrong reason: poking the
framebuffer "worked" precisely because it skips the drawing step, and its persistence from
t=22 to t=30 is what revealed that nothing ever redraws.

### So where do the glyphs come from?

Open. What is now excluded: the two table-ROM-derived buffers, for the boot play screen as
rendered. What is not excluded: that they feed content reached only by navigating (style or
sound names on other screens), which this test never displays. The next move is to tap reads
of the framebuffer-filling routine around t=6 and see what memory it sources — the same
reader/writer correlation that found the copy loop, pointed at the compositor instead.

### A methodology note worth more than the finding

The first version of `kn24_tabledest.lua` joined readers to writers on **exact PC equality**
and reported *"OVERLAP: 0 — the reader and the writer are DIFFERENT routines"*. That is
impossible to observe by construction: a copy loop's load and store are separate instructions,
here four bytes apart (`0x4860C275` vs `0x4860C279`). The rig was answering a question nobody
asked. It now joins on a ±64-byte window, and the disassembly is what revealed the bug — the
measurement looked perfectly plausible and was wrong.

## Two things this makes possible without a dump

* **A verification test.** A candidate dump must carry a plausible descriptor in its first
  `0x40` bytes, and mounting it must *change this access pattern* — traffic should extend well
  past 29 KB and stop looking like a walk over `0xFF`. Re-running this rig against a candidate
  is a cheap, honest first check before anything is declared good.
* **A RAM-side investigation that can start now.** ✅ **Done, same day** — the copy loop and its
  destination are above. What remains is the runtime-poke test that would prove the buffers
  feed the display, and working out what a 40 × 712-byte record table actually *is*.

## Reproduce

```
./tools/rig.sh kn24_fontsrc    kn2400 -s 32          # is the region read at all?
./tools/rig.sh kn24_tableshape kn2400 -s 32          # what shape of data does it expect?
TAP_UNTIL=10 ./tools/rig.sh kn24_tabledest kn2400 -s 12   # where does it land, and is it 0xFF?
```

Disassembly of the KN2400 image (a **different** firmware from the KN7000 — one shared LKG
program, no separate table flash) needs its flat image built first, because the ROMs ship as
an even/odd 16-bit interleave and disassembling either half alone produces confident nonsense:

```
python3 tools/make_kn2400_image.py -o /tmp/kn2400_flat.bin
BIN=/tmp/kn2400_flat.bin ./tools/dis.sh 0x4860C250 80
```

Both print a verdict line. `kn24_tableshape`'s first verdict logic classified on "was a block
touched in more than one second", which put 112 of 113 blocks in a "repeated" bucket and
reported a useless *mixed*; it now classifies on whether traffic **ceases** and how concentrated
it is. Recorded because the rig's own criterion had to be fixed before its answer meant anything.
