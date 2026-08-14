# IC307 page-2 investigation — raw probe scripts

**Status: UN-TRIAGED working files, staged for custody, not curated.**

35 Python probes written by four analysis agents during the 2026-08-14 investigation into what
IC307's page 2 is (1050 of the chip's 1495 chunks; 500 of its 543 `detect_period` fallbacks;
almost nothing references it). They lived only in session scratch, which is volatile, so they
are committed here to survive — but the investigation had **not reported** when they were
staged, so nothing here has been reviewed, re-run, or promoted.

Treat this directory as evidence in escrow:

- **Do not cite a number from these files** without re-running the script and checking what it
  actually measures. Several are iterations of each other (`pertest.py` / `pertest2.py`,
  `p2_wrap.py` / `wrap.py`, `ic307_page2_final.py` / `ic307_page2_verdict.py`) and the later
  one is not necessarily the better one.
- **When the investigation's verdict lands**, promote the two or three that carry it into
  `kn7000_mame/tools/` with a proper header — question answered, exact command, expected
  signal — and delete the rest from here. This directory should not outlive the investigation.

## Why they are here at all

One of these agents already earned the whole exercise: it copied `tools/kn5000_class_usage.py`,
noticed that the `(class:entry)` field separates references with a comma **or a semicolon**, and
fixed the regex. My version split on comma alone, silently dropped the only two semicolon rows,
and reported class 6 (IC307 page 2) as having **no named reference at all**. It has nine — all
`Organ Click`, at entries `0x028, 0x030 … 0x068`, stride 8. That claim had already reached a
commit message before the correction landed (`ac11f7c`).

The fix is now in `tools/kn5000_class_usage.py`; the agent's copy was dropped from this
directory as superseded.
