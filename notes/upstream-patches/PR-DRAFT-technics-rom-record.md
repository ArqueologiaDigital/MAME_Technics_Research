# PR draft — Technics SX-KN series ROM records

**Status:** READY, not yet submitted.
**Branch:** `technics-rom-record-v2` (worktree `~/compartilhado/mame-pr-romrec`), off
`upstream/master` @ `8789d0f0d48`. One commit, 2 files, +403 lines.
**Build:** `make SUBTARGET=kn7000 SOURCES=src/mame/matsushita/kn7000.cpp USE_QTDEBUG=0 -j8`
**Validated:** `./kn7000 -validate` → exit 0, no diagnostics.
**ROM sets for testing:** `~/compartilhado/technics-romsets-for-pr.zip`
(regenerate with `python3 tools/make_pr_romsets.py -o <out>.zip`). All five verify
**"best available"** — every dumped file present and hash-correct, only the declared `NO_DUMP`
entries absent.

---

## PR title

    matsushita/kn7000.cpp: add ROM records for the Technics SX-KN series

## PR description (paste this)

Preservation-only ROM records for five Panasonic/Technics MN10300/AM33 arranger keyboards:
SX-KN7000, KN6000, KN6500, KN2400 and KN2600.

No CPU device is instantiated. MAME has an MN10300 disassembler but no execution core
(`scripts/src/cpu.lua` says "disassembler only"), so each machine names its CPU in a
commented-out line, following `src/mame/bfm/bfm_sc6.cpp` — the existing precedent for a
CPU-less ROM-record driver.

**On the ROM policy.** Ten entries are real dumps, each hash independently recomputed against
the file rather than copied from a previous listing. Everything that is *not* an honest dump of
that machine's own part is declared `NO_DUMP` at its correct expected size, under its real part
number. Nothing borrowed from another model and nothing synthetic is shipped as data — including
where a sibling machine's ROM would have "worked". Wave ROMs are declared one region per bus
bank. KN2600 shares the KN2400's common devices through a macro and adds its own SD sub-CPU
flash at IC404.

**Deliberately excluded:** KN1500 (the dump is unusable — half of every 16-bit word reads
`{byte,0xff}`), SX-PR54 (retail designation unconfirmed), and HD-AE5000 (already upstream,
byte-identical).

This is the first of a short series; driver work for these machines depends on an MN10300
execution core that does not exist upstream yet, so the records come first and stand on their
own as preservation.

### AI assistance

Parts of this work were done with AI assistance: **Claude Opus 5** (Anthropic), via Claude Code.
The ROM hashes were recomputed independently and the driver builds and validates clean; I have
reviewed and understand the change.

---

## Reviewer questions to expect

* *Why a driver with no CPU?* → `bfm_sc6.cpp` precedent; the alternative is losing the dumps.
* *Why so many `NO_DUMP`s?* → they are the honest state; the parts exist and are named.
* *KN2600 as a clone of KN2400?* → they share one firmware with a runtime model selector.
