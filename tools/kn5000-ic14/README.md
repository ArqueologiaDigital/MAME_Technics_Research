# KN5000 IC14 — single ROM file equivalence check

## Background

IC14 (QSIGX3C23011, 32 Mbit mask ROM) was read with address lines **A19 and A21
transposed**. Service manual p.32 shows those lines running straight on the board, so the
transposition is an artifact of the *read*, not the hardware — which makes the corrected
image the chip's content and the raw file the defective one.

Until 2026-08-24 the driver carried the raw read plus eight `ROM_CONTINUE` lines that
un-permuted it at load. It now carries a **single `ROM_LOAD`**, byte-identical to
upstream MAME's record (`CRC(aa4917ce) SHA1(fef7f192…)`), with the correction applied on
disk once. The raw read is kept as
`roms/kn5000/kn5000_rhythm_data_rom.ic14.as-read-a19a21-swapped`.

## `ic14_regionsum.lua`

**Question it answers:** is the region the single `ROM_LOAD` puts in memory byte-identical
to what the eight-block `ROM_CONTINUE` used to put there?

Fingerprints the `:rhythm_data` region as loaded: a plain byte sum plus a
**position-weighted** sum with weights `(addr % 251) + 1`. The weight modulus is coprime
with the 512 KB block size, so any wrong block ordering changes `wsum` — this is what
makes the test capable of failing.

Run:

    cd ~/compartilhado/kn7000-emulator
    ./kn7000 kn5000 -rompath ./roms -skip_gameinfo \
        -autoboot_script ic14_regionsum.lua -autoboot_delay 1

**Pass = the printed `sum`/`wsum` equal those computed offline** for both the old
`ROM_CONTINUE` permutation of the raw read and the new file. Result 2026-08-24, all three
agreeing:

    size=0x400000  sum=414664783  wsum=694455533

Offline half: `KN7000/tools/rom-record-review/ic14_descramble_check.py` (pass = `MATCH: True`).

## A test that did NOT work, recorded so it is not repeated

Counting occurrences of the cell header `80 FF FF FF FF 87` in the region **cannot
discriminate**: the defect is a block permutation, which leaves the count unchanged except
at block boundaries. It reports 28,400 either way. A criterion that cannot fail is not a
test — the fingerprint above replaced it.
