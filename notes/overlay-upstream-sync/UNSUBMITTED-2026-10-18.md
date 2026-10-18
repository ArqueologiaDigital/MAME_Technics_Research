# What the overlay carries that upstream MAME does not, 2026-10-18

This inventory compares the overlay's source files with `upstream/master` in both directions:
what the overlay has that upstream does not, and what upstream has that the overlay lacks. It
was written right after the 2026-10-18 resync (`SYNC-2026-10-18.md`).

- **Overlay:** `~/compartilhado/kn7000_mame`, written against the working tree of the resync
  (HEAD `69bf100` plus the edits since committed as `4d8f8cc`, `f2745d0`, `a0117eb`).
  **Updated after the review** (marked *2026-10-18 update*): the five lost fixes are ported,
  `sed1330.cpp` is retired, and the DMA model and software-list findings are added (A2.17, D).
- **Upstream:** `~/compartilhado/mame` `upstream/master` = `ec20df4a93b`.
  `SYNCED-AT` still read `6756074d978`.
- **Overlay files:** 56 when written; 55 after `sed1330.cpp` was retired. 18 do not exist
  upstream (`wsa1_cpanel.*` exists there as `wsa1r_cpanel.*`); 37 replace an upstream file.
- **Cross-references:**
  - "board #N" is a row of `KN7000/MAME-PR-QUEUE.md` (2026-10-17).
  - "pos. N" is a position in `KN7000/MAME-PR-PLAN-2026-09-19.md`.
  - "kn5000-NN" is `notes/upstream-patches/kn5000-NN-*.patch`.
  - Branch names refer to `~/compartilhado/mame`.

## How it was produced

Each area was read in full by one read-only pass: mn10300, tlcs900, sharc+upd6383,
kn7000+tonegens+layouts, cpanels, kn5000 family, wsa1 family. The headline claims were then
spot-checked by hand. To regenerate the raw material:

```
OV=~/compartilhado/kn7000_mame; M=~/compartilhado/mame
# 1. classify every overlay file: NEW (absent upstream) or REPL, with changed-line count
cd $OV; for f in $(git ls-files src); do [ -f $f ] || continue
  if git -C $M cat-file -e upstream/master:$f 2>/dev/null; then
    echo "REPL $(git -C $M show upstream/master:$f | diff - $f | grep -c '^[<>]') $f"
  else echo "NEW $(wc -l < $f) $f"; fi; done
# 2. one file, both directions
git -C $M show upstream/master:<path> | diff -u - $OV/<path>
# 3. the gate (only tests the newest upstream commit per file after SYNCED-AT)
$OV/notes/overlay-upstream-sync/overlay_vs_upstream.sh
# 4. what a PR branch holds, and how the overlay differs from it
git -C $M diff --stat upstream/master...<branch>
git -C $M show <branch>:<path> | diff -u - $OV/<path>
# 5. the gate's blind spot: upstream commits since 2025-06 (before SYNCED-AT too)
#    whose added lines are absent from the overlay. Superseded lines show up as noise;
#    read each hit, do not count them.
cd $OV; for f in $(git ls-files src); do [ -f $f ] || continue
  git -C $M cat-file -e upstream/master:$f 2>/dev/null || continue
  for c in $(git -C $M log --format=%h --since=2025-06-01 upstream/master -- $f); do
    git -C $M show $c -- $f | grep '^+' | grep -v '^++' | sed 's/^+//' | grep -v '^\s*$' |
      while IFS= read -r l; do grep -qF -- "$l" $f || echo "$f $c"; done | sort | uniq -c
  done; done
```

## Headline findings

1. **Upstream is ahead, not only behind.** The overlay's MN10300 core is the pre-review
   lineage, with only #16394's DMA ported across. Upstream's reviewed core implements
   instructions the overlay core skips as no-ops (B.2), and has the pin/IVAR interrupt model,
   TM4 and timed SIO (B.1). The only core feature the overlay has and upstream lacks is the AM33
   E-register `movm` handling (A1.3).
2. **Five real upstream fixes are missing from the overlay** and are not intentional:
   - SHARC `UML_SETFMOD` (B.3). The gate cannot see it, because the commit predates `SYNCED-AT`.
   - Panel queue overflow (B.11).
   - KN7000 CPC LED out-of-bounds write (B.12).
   - Two dead KN7000 buttons (B.13).
   - `sed1330` clipping (B.17).

   *2026-10-18 update:* all five are ported (`f2745d0`; sed1330 by retiring the overlay copy in
   `4d8f8cc`), and `SYNC-2026-10-18.md` was corrected.
3. **Queued submissions that already exist:**
   - A2 tone generator (board #3).
   - B effects DSP (board #4).
   - The prescaler candidate (board #5).
   - #16220 (board #1).

   The overlay has drifted from A2 and B (A1.14, A2.2-A2.4). Before either goes out, decide
   which side is the reference.
4. **Not on any branch yet, and small enough to send:**
   - `kn6000.lay` (A2.15).
   - FDD INDEX → IRQ7 (A2.9).
   - TMP94C241 8-bit UART (A1.13).
   - TMP95C061 16-bit timers (A1.8).
   - The WSA1 floppy motor (A4.2) and note-off release (A4.3).
   - KN5000 POWER and board I/O (A3.8, A3.9).
   - HD-AE5000 ATA (A1.17).

## Table A — overlay work not in upstream

### A1. CPU cores and shared devices

| #     | area                 | files                              | what it does                                                                                                | size                 | upstream status                                                                                         | next step                                                                                             |
|-------|----------------------|------------------------------------|-------------------------------------------------------------------------------------------------------------|----------------------|---------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| A1.1  | mn10300 IRQ model    | `mn10300.cpp/.h`                   | KN7000 IRQ groups: `set_maskable_vector`, `intc_*_cb`, `intc_icr_set/clear`, group 0x17 DSP self-test latch | ~320 lines           | not submitted; upstream merged the reviewed pin/IVAR design instead                                     | none upstream: port overlay `kn7000.cpp` to the MN103002A API, retire this core                       |
| A1.2  | mn10300 SIO          | `mn10300.cpp/.h`                   | 64-byte RX FIFO per channel, `sio_tx_done_cb`/`sio_rx_rdy_cb`, instant TX                                   | ~165 lines           | not submitted; upstream has timed SIO (`set_sio_bit_rate`)                                              | as A1.1                                                                                               |
| A1.3  | mn10300 AM33 regs    | `mn10300.cpp/.h`                   | E0-E7 + MCVF, saved; `movm` mask bits 0-2 store/load them (upstream ignores those bits)                     | ~55 lines            | not submitted; on `technics-mn10300-core` (c9161dbff45, stale)                                          | the one real core feature upstream lacks: small core PR                                               |
| A1.4  | mn10300 timers       | `mn10300.cpp/.h`                   | TM5 only (TM4 reads 0), logerror on every write                                                             | ~110 lines           | upstream has TM4+TM5 templates                                                                          | take upstream's                                                                                       |
| A1.5  | mn10300 semantics    | `mn10300.cpp`                      | differs: `getx` keeps flags, 16-bit `bsch`, flags of `sat16/24`, `mul`, `div`, `rol`, bit ops; `udf` imm    | ~40 lines            | upstream implements the AM33 forms                                                                      | adjudicate each against the AM33 manual (keep `getx` note: ISR context save)                          |
| A1.6  | mn10300 length table | `mn10300_insn_length.h`            | full instruction-length table so unimplemented opcodes are skipped (550,328/550,328 vs unidasm)             | 83 lines (new)       | not upstream; on `technics-mn10300-core` only                                                           | unneeded upstream (core decodes every first byte); retire with the overlay core                       |
| A1.7  | tmp95c061 FIX 1      | `tmp95c061.cpp`                    | databook prescaler taps 3/5/7/11 for every TMP95C061 (upstream 7/9/11/15, #16255)                           | 4 code + ~90 cmt     | board #5 `tlcs900-prescaler-per-device` (08638c7d908): databook default, `TLCS900H_NGP` keeps 7/9/11/15 | rebase (470 behind); fix PARKED.md, which describes the opposite default; branch also moves tmp95c063 |
| A1.8  | tmp95c061 FIX 2-3    | `tmp95c061.cpp/.h`                 | 16-bit timers counted (`tap16`/`run16`, `m_timer_16[2]`, INTTR4-7); TRUN b4/b5 stop and clear them          | ~70 code             | not submitted; upstream never counts them                                                               | own PR after board #5                                                                                 |
| A1.9  | tmp95c061 FIX 4-6    | `tmp95c061.cpp`                    | `m_check_irqs` on 8-bit match and micro-DMA TC; INT6/INT7 release HALT unless HDMA owns the vector          | ~11 code             | not submitted                                                                                           | bundle with A1.8; A/B on ngp, namcos10, taito                                                         |
| A1.10 | tmp95c061 serial     | `tmp95c061.cpp/.h`                 | byte-level SC0/SC1 API (`sc0/sc1_txd/rxd`, `sc1_mod`) used by overlay `wsa1.cpp`                            | ~195 lines           | superseded by upstream `tmp95c061_serial` (#16204)                                                      | port overlay `wsa1.cpp` to `txd<N>`/`tx_byte<N>`, then drop                                           |
| A1.11 | tmp94c241 /INT0      | `tmp94c241.cpp/.h`                 | one /INT0 request per assertion: level re-assert removed, `clear_int0_level()` added                        | ~60 lines            | `kn5000_minimal_tonegen` a23ffbdf74d; old plan pos. 17 (blocked)                                        | hold until the pos. 17 experiment is done                                                             |
| A1.12 | tmp94c241 extras     | `tmp94c241.cpp/.h`                 | `to0_callback` (unbound, dead), `dbg_*` accessors, DMACNT logging                                           | ~35 lines            | not submitted                                                                                           | drop TO0 cb; keep debug accessors overlay-only                                                        |
| A1.13 | tmp94c241 UART       | `tmp94c241_serial.cpp/.h`          | 8-bit UART mode 2, 16x oversampled TX/RX; KN5000 MIDI needs it                                              | diff 136+8           | patch kn5000-04; no branch (kn5000-30 is stale, reverted)                                               | good one-file-pair PR                                                                                 |
| A1.14 | sharc 21065L + DRC   | `sharc*.cpp/.h/.hxx`               | ADSP-21065L variant, ALUSAT, native MAC/SAT/AVG/ABS/FDEP, interp ops, `compute_fallback`                    | diff ~1000 / 5 files | board #4 B `technics-kn7000-dsp` (a1c1fe1db93), queued behind A2; overlay != B                          | B is the submission; converge overlay onto B (needs B's `kn7000.cpp` glue)                            |
| A1.15 | upd6383              | `cpu/upd6383/*` (4)                | NEC uPD6383GF draft core (no audio, disabled by default) + disassembler, 81% of corpus words decode         | 15,550 lines (new)   | not submitted; old plan pos. 14 (disassembler only, ~800 lines)                                         | disassembler-only PR after cutting comments and KN5000 tables                                         |
| A1.16 | sed1330              | `video/sed1330.h`                  | upstream's header plus default member initialisers (the `.cpp` copy was retired, B.17)                      | 36 initialisers      | not submitted                                                                                           | small PR candidate (uninitialised geometry before the host programs the chip)                         |
| A1.17 | hdae5000             | `bus/technics/kn5000/hdae5000.cpp` | real `ATA_INTERFACE` (CS0 0x130010, CS1 0x130020), ATA INTRQ to INT9, DO3 audio note                        | diff 83              | patch kn5000-19; `kn5000_pr6_hdae5000` (554e89a0542) differs                                            | reconcile with branch; small PR                                                                       |

### A2. MN10300 Technics driver (`kn7000.cpp`: KN2400/2600/6000/6500/7000), its devices and layouts

| #     | area                         | files                                                  | what it does                                                                                                          | size                  | upstream status                                                                                           | next step                                                                    |
|-------|------------------------------|--------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|-----------------------|-----------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| A2.1  | driver structure             | `kn7000.cpp`                                           | one `kn7000_state` + runtime model flags; overlay-core IRQ groups, 1 kHz `sys_tick`, panel 0x11 redelivery            | ~130 + whole file     | upstream has the reviewed `kn_state`/`kn_sd_state`/`kn6000_state` split                                   | none for upstream; rebase overlay onto upstream classes                      |
| A2.2  | tone generators              | `kn_tonegen.*`, `kn7000_tonegen.*`, `kn6000_tonegen.*` | voice engine: envelope, gate follow, 128-voice renderer, `KN7WVSY2` wave pack; KN7000 2 chips, KN6000 1 chip/64 slots | 503 + 354 + 276 lines | board #3 A2 `technics-kn7000-tonegen` (7f7d1857e20), held; one file pair, raw pitch formula, no wave pack | decide whether A2 takes A2.3 before sending                                  |
| A2.3  | TG pitch from record         | `kn7000.cpp`                                           | `tg_slot`/`tg_pitch_resolve`/`tg_type_resolve` read the library voice record; `m_tg_reg` shadow                       | ~115 lines            | not on A2                                                                                                 | fold into A2 or follow-up                                                    |
| A2.4  | effects DSP                  | `kn7000.cpp`                                           | ADSP21065L @66 MHz host-booted; `dsp_audio_tick` polls DM 0xC342-0xC377; `KN7000_DSP_BRIDGE` returns + master gain    | ~410 lines            | board #4 B, diverged (SPORT callbacks, 60 MHz, rings in `kn_tonegen`)                                     | converge onto B                                                              |
| A2.5  | synthetic sound data         | `kn7000.cpp`                                           | `wavepack` region, `kn7000_waves_synthetic.rom`, `kn7000_rhythms_synthetic.rom` @0x54E00000                           | ~75 lines             | not submittable (upstream: NO_DUMP)                                                                       | overlay-only                                                                 |
| A2.6  | custom flash IC21            | `kn7000.cpp`                                           | four Initial Data files (umdini/favini/hpgini optional + ctmini), 32-to-16-bit split                                  | ~75 lines             | #16394 has ctmini as `custom_data`; extra sets retired with `technics-kn7000-initial-data-card`           | overlay-only; align region tags with upstream                                |
| A2.7  | KN6000/6500 font placeholder | `kn7000.cpp`                                           | generated `kn6000/kn6500_table_fontph.rom` (BAD_DUMP); KN6500 table at 0x40010000                                     | ~60 lines             | not submitted (overlay 921bbdd)                                                                           | overlay-only until dumped                                                    |
| A2.8  | KN6000/6500 bring-up         | `kn7000.cpp`                                           | counter hack 0x340010a4, all vectors 0x90000000, delayed tick, `layout_kn6000`                                        | ~45 lines             | not submitted                                                                                             | re-check need once on upstream core                                          |
| A2.9  | FDD INDEX                    | `kn7000.cpp`                                           | drive INDEX to IRQ7 (group 0x1E) by a 500 us `fdd_index_poll`; disk-presence check needs it                           | ~35 lines             | not upstream; committed `a0117eb`                                                                         | small PR candidate                                                           |
| A2.17 | floppy DMA model             | `mn10300.cpp`, `kn7000.cpp`                            | DMA channel 0 moves count + 1 bytes and raises group 0x0F; FDC TC from GPIO 0x36008004 bit 4; DRQ also IRQ1 request   | ~40 lines             | diverges from #16394 on purpose (count + 2 overruns every KN6000 sector); *2026-10-18 update*             | PR to upstream with the KN6000 evidence                                      |
| A2.18 | KN6000 tempo timer           | `mn10300.cpp/.h`                                       | timer 6 (mode 0x34001084, compare A 0x340010C4, group 9): the KN6000/KN6500 sequencer clock                           | ~90 lines             | not upstream (upstream has TM4/TM5 only); *2026-10-18 update*, `9690319`                                  | PR candidate with A2.17; without it nothing sequenced advances on the KN6000 |
| A2.10 | SD/KN2x00 glue               | `kn7000.cpp`                                           | group 0x1B/0x1C card-detect and mailbox, `sd_led1` from firmware RAM; kn2600 = kn2400                                 | ~105 lines            | upstream has IRQ4/IRQ5 pins, strap 0x8007                                                                 | take upstream's (B.8, B.10)                                                  |
| A2.11 | MIDI-to-keybed, volume       | `kn7000.cpp`                                           | `kbdmidi`/`kbd_midi_rx`; MAIN VOLUME polled at 250 Hz into the bridge                                                 | ~60 lines             | not submitted; B has `set_master_gain`                                                                    | volume with B; MIDI bridge overlay-only                                      |
| A2.12 | dead code                    | `kn7000.cpp`                                           | `cpsd_queue`, no-op `note_on/off`, `KN7000_SIO_UART` type                                                             | ~25 lines             | n/a                                                                                                       | delete                                                                       |
| A2.13 | panel LED shadow             | `kn_cpanel.*`, `kn7000_cpanel.*`                       | CHORUS/MULTI LED shadow read by the DSP bridge                                                                        | ~20 lines             | B re-adds `chorus_led()` only                                                                             | with B                                                                       |
| A2.14 | panel handshake              | `kn_cpanel.*`                                          | two-edge ATN (`atn_rearm`), one shared event timer, `rx_enable()` without a line                                      | ~25 lines             | removed upstream in review round 1                                                                        | none; migrate with A1.1                                                      |
| A2.15 | KN6000 layout                | `layout/kn6000.lay`                                    | generated from the service-manual panel drawing; 5 views, ~150 bindings, LEDs unbound                                 | 1156 lines (new)      | not submitted; upstream: "no artwork for the KN6000 yet"                                                  | strong small PR (with `tools/gen_kn6000_lay.py`)                             |
| A2.16 | KN7000 layout                | `layout/kn7000.lay`                                    | presentation only: coloured LEDs, CPC mute grid written out, extra shapes, 313-line Lua                               | diff 1020             | upstream has #16250's tidied version                                                                      | overlay-only cosmetics                                                       |

`kn6000_cpanel` has nothing functional beyond upstream; take upstream's copy. The LCD capture
work (34baad4) is tooling only (`tools/lcdcap`). The driver has no capture code; the firmware
writes BMP files to the emulated SD card.

### A3. KN5000 family (TLCS-900: `kn5000.cpp` and friends, KN1500)

| #     | area                  | files                            | what it does                                                                                                  | size                   | upstream status                                                                         | next step                                     |
|-------|-----------------------|----------------------------------|---------------------------------------------------------------------------------------------------------------|------------------------|-----------------------------------------------------------------------------------------|-----------------------------------------------|
| A3.1  | inter-CPU latch       | `kn5000.cpp`                     | `perfect_quantum`, `clear_int0_level`, `abort_timeslice`, LOG_HANDSHAKE (uses A1.11/A1.12)                    | ~110 lines             | kn5000-26..28; simpler form on `kn5000_minimal_tonegen`; pos. 16/17 held                | hold with A1.11                               |
| A3.2  | KN5000 tone generator | `kn5000_tonegen.cpp/.h`          | 64-voice IC307 PCM player; heuristic loop points, filter, envelope, keybed FIFO, DSP insert                   | 5,266 lines (new)      | `kn5000_minimal_tonegen` (c3f95c18ece, sines only) / `_combined` / `_pcm`; pos. 16 held | choose the branch; port its fixes back (B.20) |
| A3.3  | TG wiring             | `kn5000.cpp`                     | IC303 at 0x100000-0x110003, `build_pitch_constants`, stereo out, IMPERFECT_SOUND                              | ~130 lines             | same branches                                                                           | with A3.2                                     |
| A3.4  | key bed               | `kn5000.cpp`                     | 61 keys, 1 ms scan, velocity to key-travel tables                                                             | ~230 lines             | kn5000-01 / `kn5000_pr6` (early form)                                                   | after A3.2                                    |
| A3.5  | MIDI                  | `kn5000.cpp`                     | `mdin`/`mdout` on rxd0/txd0; `KN5000_KBD_UART` host-keyboard bridge                                           | ~60 lines              | kn5000-05 / `kn5000_pr6`                                                                | needs A1.13 first                             |
| A3.6  | FDC                   | `kn5000.cpp`                     | uPD72067 at 0x110008/0x11000A, DACK 0x120000, `!dskchg` on Port D b6, TC from Port H b0                       | ~70 lines              | kn5000-03/06 (kn5000-16 TO0-to-TC superseded)                                           | small PR; settle B.16 first                   |
| A3.7  | IC311 DSP research    | `kn5000.cpp`, `kn5000_dsp_hle.h` | uPD6383 glue behind `KN5000_ENABLE_DSP1=0`, DSPCFG/DSPHLE ports, HLE kernels (dead by default)                | ~350 + 145 lines       | kn5000-14/22 cover the stub only                                                        | overlay research only                         |
| A3.8  | POWER switch          | `kn5000.cpp`                     | POWER pulses NMI, exit 100 ms later                                                                           | ~60 lines              | replaces `kn5000_power_off_nmi` (c544e73bea1)                                           | small PR candidate                            |
| A3.9  | board I/O + memory    | `kn5000.cpp`                     | PEDALS on Port G; Port E b0 = board fitted; IC19 as `AMD_29F800B_16BIT`; battery RAM seeded from v10 defaults | ~60 lines              | not submitted                                                                           | small PR candidates                           |
| A3.10 | ROM notes             | `kn5000.cpp`                     | IC304-306 as BAD_DUMP copies of IC307; IC14 A19/A21 transposition comment                                     | comments + 3 ROM_LOADs | IC14 note = old plan pos. 6 (`PR-DRAFT-kn5000-ic14.md`)                                 | send pos. 6; copies stay overlay              |
| A3.11 | cpanel button ports   | `kn5000_cpanel.*`, `kn5000.lay`  | `CPL/CPR_SEG*` ports owned by the device; layout tags gain `cpanel:`                                          | +390/-379              | on `kn7000-base` f1249c0dfa4; old plan pos. 18 (low value)                              | hold; must precede any overlay `.lay` PR      |
| A3.12 | data wheel            | `kn5000_cpanel.*`                | wheel polled inside the device (`encoder_delta`); dead `read_status_register`                                 | ~+110/-40              | equivalent to upstream #15919 `encoder_detent`                                          | take upstream's mechanism                     |
| A3.13 | KN1500                | `kn1500.cpp`                     | TMP95C061 skeleton, undriven SVG LCD, IC15 BAD_DUMP (defective, hangs at 0xFA047F)                            | 111 lines (new)        | not upstream; `mame-pr/` July draft is stale                                            | wait for a re-dump                            |

### A4. SX-WSA1 / WSA1R

| #    | area                | files                        | what it does                                                                                      | size            | upstream status                                    | next step                                                     |
|------|---------------------|------------------------------|---------------------------------------------------------------------------------------------------|-----------------|----------------------------------------------------|---------------------------------------------------------------|
| A4.1 | WSA1 keyboard       | `wsa1.cpp`, `wsa1_cpanel.*`  | `wsa1` clone with PB.0 strap; 61-key keybed + TOUCH + 32-event FIFO; panel variant 1              | ~350 + variant  | removed from #16204 in review (F4)                 | later PR                                                      |
| A4.2 | floppy motor        | `wsa1.cpp`                   | `cpu1_pa_w` drives `mon_w` from PA.3; overlay comment says without it the read fails (error 0x31) | ~10 lines       | not upstream: upstream binds no CPU1 `porta_write` | run a `wsa1_flop` disk on upstream; if it fails, small fix PR |
| A4.3 | note-off release    | `wsa1.cpp`                   | `tg_data_w` calls `set_release(chan)` in the 0x0A00 burst                                         | ~5 lines        | not upstream (`set_release` dead there)            | small fix PR                                                  |
| A4.4 | MIDI bridge         | `wsa1.cpp`                   | `wsa1_midi_uart_device` byte-to-bit bridge on the overlay serial API                              | ~130 lines      | superseded by `tmp95c061_serial`                   | drop with A1.10                                               |
| A4.5 | DSP host bus        | `wsa1.cpp`                   | uPD6383 strobe capture and deframe (`WSA1R_ENABLE_DSP=0`)                                         | ~120 lines      | not submitted                                      | research only                                                 |
| A4.6 | L7A1429             | `acoustic_modeling.cpp/.h`   | 1217-register file, `decoded_channel()`, opt-in waveguide synth                                   | 837 lines (new) | upstream has a ~30-line in-file skeleton           | research; register decode could replace the skeleton later    |
| A4.7 | overlay-only extras | `wsa1.cpp`, `wsa1_tonegen.*` | LIVESYNC tempo-to-SysEx (invented), TGSINE toggle, 11 LOG masks, TG register decode               | ~320 lines      | never for upstream                                 | keep overlay-only                                             |

The overlay `wsa1.cpp` is roughly 1190 lines of code in a 4369-line file, against upstream's
490 code lines in 838. The remaining diff is research commentary, and the file's own header says
the two copies deliberately diverge.

### A5. Build-system patches and the base branch

| #    | area             | files                         | what it does                                                                                          | size      | upstream status                                                               | next step                                    |
|------|------------------|-------------------------------|-------------------------------------------------------------------------------------------------------|-----------|-------------------------------------------------------------------------------|----------------------------------------------|
| A5.1 | build: DRC token | `build.sh` (cpu.lua)          | adds `"ADSP2106X"` to `DRC_CPUS` so the SHARC DRC links                                               | 1 token   | in B (d06625a1c89) and `technics-cpulua-drc-token` (947b74a69f8); old pos. 5  | send with B                                  |
| A5.2 | build: uPD6383   | `build.sh` (cpu.lua, unidasm) | forces `CPUS["UPD6383"]`, adds the `upd6383` unidasm arch                                             | ~30 lines | with A1.15                                                                    | with A1.15                                   |
| A5.3 | build: mame.lst  | `build.sh`                    | registers `kn1500` and the `wsa1` clone                                                               | 2 entries | with A3.13 / A4.1                                                             | with those                                   |
| A5.4 | build: ui.cpp    | `build.sh`                    | `-skip_gameinfo` also skips the warnings screen                                                       | 1 line    | never for upstream                                                            | overlay-only                                 |
| A5.5 | base tree        | `kn7000-base` (4 commits)     | KN6000 expansion connector + HD-SX3 (473fb321714..599f077cc6a); overlay `kn7000.cpp` does not wire it | +264      | board #1 #16220 OPEN; v5 (d497bed5caf) renamed it HD-SX6 and adds atahle 0x55 | push v5; then re-adopt into base and wire it |

## Table B — upstream features the overlay lacks

| #    | area                  | upstream has                                                                                                          | overlay has                                              | impact / next step                                             |
|------|-----------------------|-----------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|----------------------------------------------------------------|
| B.1  | mn10300 API           | `MN103002A`; IRQ0-7 pins with EXTMD; IVAR0-6; TM4+TM5; timed SIO; MDRQ/MCRH/MCRL/LIR/LAR debugger state               | older group-callback model (A1.1-A1.4)                   | structural; the overlay driver is tied to the old API          |
| B.2  | mn10300 opcodes       | 0x01-0x0F/0x30-0x3B `mov (abs16)`, FA 0x80-0x8C, FA F0/F4/F8 bit ops on `(d8,An)`, `mulqu imm`, `addc/subc` Z         | skipped as no-ops via `mn10300_insn_length`              | emulation gaps in overlay builds                               |
| B.3  | sharc DRC             | `UML_SETFMOD(ROUND_ROUND)` (fac12419a82, x64 rounding fix)                                                            | missing; the gate cannot see it (predates `SYNCED-AT`)   | **ported** `f2745d0`                                           |
| B.4  | sharc tidy-ups        | `offs_t` (5446223573f), `has_single_bit` (40d0f1125be), `UIREG`/`std::rotl` (63c2ec0ccfe)                             | older forms                                              | cosmetic (the old code already cast to `uint32_t`): left       |
| B.5  | tmp95c061 serial      | `tmp95c061_serial` bit-serial sub-device: `txd<N>`, `rxd<N>`, `tx_byte<N>`, `rx_byte<N>`, `set_pin_enabled`           | byte API (A1.10)                                         | overlay `wsa1.cpp` must move first                             |
| B.6  | kn7000 ROMs           | BIOS `sp7001`/`v16`/`v15`/`v14`; NO_DUMP for wave/rhythm/picture/SD sub-CPU; KN6000/6500 `custom_data` 01ctmini.ic18  | v16 only, different file names and region tags           | overlay cannot run SP7001/v15/v14; adopt upstream ROM records  |
| B.7  | kn7000 classes        | `kn_state`/`kn_sd_state`/`kn6000_state`, `single_tg_map`                                                              | one class (A2.1)                                         | structural                                                     |
| B.8  | kn7000 SD             | `kn_sd_state::sd_card_changed` card-present callback                                                                  | cover switch + 6 s timer                                 | port with the core migration                                   |
| B.9  | kn7000 misc           | `update_volume` on PORT_CHANGED; `sd_led1` from `sdport_w` b7-6; save state for keybed FIFO and SD state              | polling, firmware-RAM peek, unsaved                      | adopt                                                          |
| B.10 | kn2400/kn2600         | KN2600 strap 0x8007 and SD-only machine; `KN2400_TONEGEN` type                                                        | kn2600 = kn2400                                          | adopt                                                          |
| B.11 | kn_cpanel queue       | `panel_queue()` returns bool; state recorded only once queued (round 8)                                               | state recorded first; full queue drops the event         | **ported** `f2745d0`                                           |
| B.12 | kn7000_cpanel LEDs    | `output_finder<256> m_cpc_leds`                                                                                       | `output_finder<64>` indexed up to 255 behind `led < 512` | **ported** `f2745d0`                                           |
| B.13 | kn7000_cpanel buttons | ORGANIST (`CPL_SEG1` 0x02), 60s & 70s (`CPL_SEG2` 0x40); printed-label names; LED D-number table                      | both bits `IPT_UNUSED`: dead on the overlay's own layout | **ported** `f2745d0` (the two buttons; the label renames not)  |
| B.14 | kn_cpanel timers      | separate ATN/RX timers, ATN level pulse on IRQ3, `rx_enable(int)`                                                     | one shared timer                                         | tied to B.1                                                    |
| B.15 | kn5000_cpanel cmds    | 0xE2 answered with a sync packet; 0xE3 only for seg <= 0x0B                                                           | 0xE2/0xE3 treated like 0xE0                              | check and port                                                 |
| B.16 | kn5000 FDC            | `hdl_wr_callback` to TLCS900_INT6                                                                                     | commented out (INT6 handler empty)                       | decide before A3.6                                             |
| B.17 | sed1330               | per-pixel `cliprect.contains` in text (#16080); cliprect in graphics                                                  | raw pointer + `fill_n`, can overrun                      | **done**: overlay `.cpp` retired `4d8f8cc`                     |
| B.18 | wsa1 devices          | `wsa1r_cpanel.*` (renamed); in-file `UPD6383`/`L7A1429` skeletons always instantiated; 2-ch speaker; review clean-ups | `wsa1_cpanel.*`, `cpu/upd6383`, `acoustic_modeling`      | short names `upd6383`/`l7a1429` collide if both are ever built |
| B.19 | wsa1_tonegen          | corrected header text (review S5/S6), `std::numbers::pi`                                                              | stale header paragraphs, `M_PI`                          | take upstream's text                                           |
| B.20 | KN5000 TG branch      | n/a (on `kn5000_minimal_tonegen`): key-map bound `ptr_a + 4 + 0xff` in 64-bit, `STRUCT_MEMBER` saves, ASCII           | `ptr_a + 4 >= bytes`                                     | port back to the overlay                                       |
| B.21 | spi_sdcard            | CMD25 multi-block write, `card_present_callback`, CRC7 on the CSD                                                     | overlay copy retired 2026-10-18                          | done                                                           |

## Table C — "REVERTS" flags that are deliberate or cosmetic

From `overlay_vs_upstream.sh` run against `ec20df4a93b` with `SYNCED-AT` = `6756074d978`.
Each flag was checked by listing the commit's added lines that are absent from the overlay,
using the gate's own `grep -F` test.

| file                   | flagged commit       | missing       | what the missing lines are                                                                                                | verdict                                                                                      |
|------------------------|----------------------|---------------|---------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| `mn10300.cpp`          | 78a1180e64c (#16394) | 18/96         | 7 constructor initialisers grouped per line, 7 comment lines reflowed, `u32` vs `uint32_t`, `m_program.` vs `m_program->` | cosmetic: `dmac_r/w`, `dma_req_w`, `dma_transfer`, map, save, reset, `dma_tc_cb` all present |
| `mn10300.h`            | 78a1180e64c (#16394) | 8/19          | 1 banner comment, 7 `u32`/`u16` vs `uint32_t`/`uint16_t`                                                                  | cosmetic                                                                                     |
| `tmp95c061.cpp`        | eb947cba9b9 (#16480) | 3/30          | `m_timer_pre &= 0xff'ffff` (digit separator); `!BIT(data, 4/5)` in `trun_w`, where FIX 3 clears `m_timer_16[]`            | cosmetic + intentional; the lines sit in `trun_w` and the wrap mask, not the tap/HALT code   |
| `kn7000.cpp`           | 98e60b54d07 (#16416) | 1/1           | upstream `SOFTWARE_LIST(config, ...)`; overlay uses `config.replace()`: its `kn6000()` inherits `kn7000()`'s `flop_list`  | equivalent                                                                                   |
| `kn7000.lay`           | b67e5bcb0b8 (#16250) | 357/999       | upstream's tidied rewrite of the overlay layout                                                                           | intentional (A2.16)                                                                          |
| `kn_tonegen.cpp/.h`    | b67e5bcb0b8 (#16250) | 23/46, 26/47  | upstream's silent placeholder with 3 device types in one pair                                                             | intentional; A2 replaces it                                                                  |
| `kn6000_cpanel.cpp/.h` | b67e5bcb0b8 (#16250) | 203/222, 6/22 | rewrite: constructor tables, `IPT_OTHER`, merged unused bits                                                              | intentional; nothing functional                                                              |
| `kn_cpanel.cpp/.h`     | b67e5bcb0b8 (#16250) | 98/201, 48/70 | rewrite + reviewed API                                                                                                    | **mostly**; B.11 and B.14 are real                                                           |
| `kn7000_cpanel.cpp/.h` | b67e5bcb0b8 (#16250) | 238/262, 7/23 | rewrite + label renames                                                                                                   | **mostly**; B.12 and B.13 are real                                                           |
| `sharcdrc.cpp`         | not flagged          | -             | fac12419a82 predates `SYNCED-AT`, so the gate never tests it                                                              | **real revert** (B.3)                                                                        |
| `wsa1_cpanel.*`        | reported "absent"    | -             | upstream has the same device as `wsa1r_cpanel.*`                                                                          | name divergence, not a new file                                                              |

Deliberate behavioural divergences the gate does not flag:
- **TMP95C061 taps (A1.7).** The overlay leaves out #16255's 7/9/11/15 taps for every
  TMP95C061. In overlay builds, ngp, namcos10, dvd-n5xx and kkcount timers therefore run 16x
  faster than upstream's.
- **TMP94C241 /INT0 (A1.11).** The overlay removes the /INT0 level re-assertion (8789d0f0d48).

- **MN10300 DMA (A2.17).** The overlay channel moves count + 1 bytes and raises INTC group 0x0F;
  upstream's moves count + 2 and pulses TC. See `notes/kn6000-feature-presentation.md`.

Advancing `SYNCED-AT` to `ec20df4a93b` makes every flag above vanish from the gate. B.3 was
already invisible to it. *2026-10-18 update:* B.3, B.11, B.12, B.13 and B.17 were ported before
`SYNCED-AT` moved; command 5 above stays the cross-check for the next resync.

## D — upstream's floppy software lists hold images the instruments reject

*2026-10-18 update.* Every image in `kn5000_flop`, `kn6000_flop`, `kn7000_flop` and `wsa1_flop`
(34 checked) was built with pyfatfs (`research-scratch/kn7000-softlists/build_fat_floppy.py`):
OEM `MSWIN4.1`, FAT starting `F0 0F FF`, 12 sectors per FAT. The KN6000 and KN7000 media probes
(`0x4853312E`, `0x48470CE3`) accept a disk only if its FAT starts `F0 FF FF` or `F9 FF FF`, and the
KN6000 file system expects the standard 9-sector FATs. Measured: KN7000 `ca7001` as listed is
rejected (−7) and accepted with only the FAT start changed; KN6000 `ca6fp01` loads and runs only when
its files are laid out on a standard image. The lists need rebuilding (new hashes, same payloads):
an upstream PR. KN5000 and WSA1 firmware were not tested against the layout.

## Not verified here

- **A4.2.** That `wsa1_flop` disks fail to load on an upstream build. The overlay's comment
  says so, but nobody ran it.
- **A1.5.** Which side's flag semantics match the AM33 manual.
- **B.2.** Whether the KN7000 firmware reaches the opcodes the overlay core skips.
- **A1.9.** The interrupt-latency effect of FIX 4-6 on the non-Technics TMP95C061 drivers.
