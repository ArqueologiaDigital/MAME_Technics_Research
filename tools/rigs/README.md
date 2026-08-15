# Lua measurement rigs

Rescued 2026-08-14 from `~/compartilhado/kn7000-emulator/`, which is **not a git repository** — it
is the publish target of `tools/publish-binary.sh` and is overwritten on every publish. These 95
scripts were the only copies of themselves, and several are the named regression gate in committed
notes. Nothing else in that directory is unique; treat it as derived from now on.

Run one with **`tools/rig.sh`**, from the repo root:

```
./tools/rig.sh kn5000_p9_stall              # machine inferred, 30 s, fresh cfg/nvram
./tools/rig.sh money kn7000 -s 22 -w /tmp/o.wav
P9_PRESS_AT=20 ./tools/rig.sh kn5000_p9_writer -s 150
```

It resolves the rig to an **absolute** path (see below), applies the project's launch rules
(`-window` never `-video none`, `timeout`-wrapped, throwaway `cfg`/`nvram` unless you ask for
Felipe's real ones with `--user-cfg`), and prints the exact command it ran so a number a rig
produces can be quoted next to its recipe.

⚠ **Do not hand-write `-autoboot_script tools/rigs/<rig>.lua`.** `run.sh` lives in the emulator
directory and `cd`s to itself, so a repo-relative path resolves against a directory with no
`tools/` in it. Measured 2026-08-15: MAME does not limp on without the rig — it exits `rc=3`
with `Fatal error: Error loading autoboot script`. Fourteen rig headers documented exactly
that unrunnable command until it was fixed; `rig.sh` makes the mistake unavailable.

⚠ Two hazards these rigs encode, both learned the hard way:
- **Hold the notifier handle in a global** (`_G.m.h = emu.add_machine_frame_notifier(...)`) or the
  Lua GC silently collects it and the tap never fires.
- **`ioport_field:set_value()` toggles a `PORT_CONFNAME` field**, it does not assign, and MAME
  persists it in `cfg/*.cfg`. Use a private `-cfg_directory` for rigs — but reproduce the *user's*
  cfg when chasing a user-reported bug (see RULE 20 in the project notes).

## The load-bearing ones

| rig | what it does | the signal |
|---|---|---|
| `money.lua` | **the audio oracle.** Presses keybed note `KEYS1` mask `0x0100` at t=16 s, releases at t=17 s. Run with `-wavwrite`; the WAV's md5 is the regression gate. **Re-baselined 2026-08-14 — see below.** | md5 `780de131e33a4a0c99d092b57a074247` |
| `env14.lua` | demo-song regression: press DEMO, play ~25 s | audio + transport regression |
| `kn7000_regress.lua` | save a settled home state, then press PROGRAM MENUS / DISK MENU LOAD / PIANO from it, snapshotting each | three screenshots; catches UI regressions without re-booting |
| `sio_core_verify.lua` | live verification of the SIO-into-CPU-core refactor | boot + panel still work after the move |
| `intc_core_verify.lua` | same for the INTC + TM5 timer move | tempo timer drives the demo |
| `a3.lua`, `a3b.lua` | live DSP experiments; produced the shipped DSP unit-role map and the EQUALIZER bank dump | per-unit DM bank contents |

### The money.lua baseline, pinned 2026-08-14

The exact recipe, which was previously recorded in only one note:

```
cd ~/compartilhado/kn7000-emulator
cp -f sdcard_from_real_kn7000.img /tmp/sd_pristine.img && chmod u+w /tmp/sd_pristine.img
./run.sh kn7000 -window -nothrottle -seconds_to_run 22 \
    -autoboot_script <this-dir>/money.lua \
    -wavwrite out.wav -cfg_directory <fresh dir> -harddisk /tmp/sd_pristine.img
md5sum out.wav
```

| | |
|---|---|
| **current md5** | `780de131e33a4a0c99d092b57a074247` (6,336,050 B; 1,056,001 frames, 3 ch, 48 kHz) |
| binary | `kn7000-emulator/kn7000`, 74,035,784 B, 2026-08-11 20:17 |
| determinism | **verified** — two identical runs produced the identical hash |

⚠ **Both previously recorded baselines are stale, and they disagree with each other**:
`44b09b9d0eaae59d9a65e5b4f4e72ec0` (`notes/sharc-upstream-patch-series.md:223`) and
`c3b67ea711ce3c00f8ae2af1e07651cb` (quoted in `AUTONOMOUS-STATUS.md`, `kn2400-boot.md`,
`kn6000-tonegen-spec.md`). Neither reproduces today. Since the rig is bit-deterministic, the driver
changed under them and nobody noticed — which is precisely what an unrun gate does.

**This gate can fail** — measured on the current capture, so it is not a criterion that cannot fail:

| window | rms | peak |
|---|---|---|
| t=10–15.5 s, no stimulus | **0.0** | **0** |
| t=16–18 s, note held | **165.7** | 972 |
| t=18–21 s, after release | 0.7 | 9 (the reverb tail) |

The no-stimulus window is exactly zero and the note is three orders above it. Still: this is a
**regression** hash. It says nothing changed, never that anything is *correct*.

## The KN5000 demo-audio oracle (gate arm, added 2026-08-15)

The gate's other audio check (`money.lua`) runs on the **KN7000**, and its KN5000 liveness check
sits at the home screen with **no notes playing** — so the gate passed 16/16 on a KN5000
tone-generator change it structurally could not see. This arm closes that.

```
./run.sh kn5000 -window -nothrottle -seconds_to_run 90 \
    -wavwrite out.wav -cfg_directory <fresh> -nvram_directory <fresh> \
    -autoboot_script notes/kn5000-demo-probes/demo_max.lua
```

| | |
|---|---|
| baseline md5 | `4c8671b68f446cd3f6c10c8784e7748f` |
| determinism | **verified** — identical across two runs of the same binary |
| level | max rms 499.8 on ch1/ch2, against 0.00 before the demo starts |

⚠ **Two preconditions, both fault-injected on 2026-08-15**, because each corresponds to a
mistake that already happened here:

1. **The stimulus must fire.** The demo needs `DEMO → LEFT 4 → LEFT 2`; pressing DEMO alone
   leaves transport at `0x00` and the machine silent. Injected by pointing `DEMO_RIG` at the
   single-press rig → `FAIL — stimulus never fired (transport never reached 0x04)`.
2. **The capture must be audible on ch1/ch2.** **Channel 0 is always silent on this machine.**
   Injected against a known-silent capture → max rms `0.0`, guard fires; the good capture reads
   `499.8`.

Those two faults together once produced a "bit-identical" A/B of two silent files that was
reported as evidence of no regression. Each is now a separate red gate.

## By family

| prefix | count | question the family answers |
|---|---|---|
| `env*` | 14 | the amplitude/envelope editor: 7-parameter sweeps, where the RLS parameter lives, whether the TG is alive at all, whether the ENVELOPE screen auditions the keybed |
| `sdnav_*`, `sdsave*`, `sdload_rt` | 15 | SD MENU navigation and the SD SAVE round trip, soft key by soft key from a verified state. `sdnav_lib.lua` is the shared trial runner — `dofile` it after defining `TRIALS` |
| `kn6_*` | 16 | the KN6000 missing-text investigation: does the text drawer run, what font pointer does it get, who writes the UI index plane |
| `kn7_*` | 9 | the KN7000 equivalents — who calls the text drawer `0x48425467`, who reads the font descriptor at `0x50122DB8` |
| `b1`, `b2*` | 9 | effect-bus unit feeds and the per-part effect-send setters; where the depth cache lives |
| `a1*`, `a3*` | 4 | DSP damp-bank fields `r4..rA` and live DSP experiments |
| `kn24_*` | 4 | KN2400 boot probing and the LCD buffer hunt |
| `ledtest_sweep*`, `btntest`, `probe*` | 5 | panel button → LED sweeps and segment probes |
| `kn5000_*`, `kn6000_*`, `kn6500_verify` | 5 | per-model panel/wheel/layout checks |
| `ballad_verify`, `latin_verify` | 2 | the "8 Beat 1" style-name fix |
| `note`, `keybed_trigger`, `one`, `nopress` | 4 | does a key press reach the firmware and emit voice writes |
| `kn5000_note_capture` | 1 | hold one KNOWN keybed note so its pitch can be measured (used to close P10) |
| `cpu_state_probe` | 1 | which registers does this CPU expose to Lua? (TLCS-900 has XNSP/XSSP and no SP) |
| `kn5000_p9_stall`, `kn5000_p9_writer` | 2 | when the demo stops, and which instruction and call chain stop it |

## ⚠ `note.lua` was broken in two independent ways (found and fixed 2026-08-15)

It produced a completely silent capture that looked exactly like a broken audio path:

1. **The notifier handle was not held in a global**, so the Lua GC collected it and the callback
   never fired — the very hazard listed at the top of this file.
2. **It referenced port `:KEYS0`, which does not exist on the KN5000.** The keybed ports here are
   `:KEY0`–`:KEY5` (`:KEY2` bit `0x001` = `C4`, MIDI 60). `KEYS0`/`KEYS1` are the KN7000's.

With both fixed, holding `C4` gives rms 562/535 on ch1/ch2 against 0.00 before the press. This is
the concrete case behind the honesty note below: a committed rig that had never been re-run did
not merely rot, it had never worked on this driver.

## Honesty note

This index was built from each script's own header comment plus a reading of the handful that had
none. **Only `money.lua` was re-run during the rescue** (above); the other 94 were not, so any one
of them may have rotted against the current driver — several target addresses and screens that
later work moved. Re-run before trusting, and fix the header while you are there.

The header defects are now **counted rather than estimated**, by `tools/gen_rig_index.py`
(2026-08-15, 109 rigs):

| defect | count | note |
|---|---|---|
| no description at all | **20** | 18 % — the earlier "about a fifth" was right |
| header names a *different* script | **0** | was 5 — all rewritten 2026-08-15, see below |
| no runnable command documented | **90** | fixed for 19 so far; the rest still need one |
| machine declared via `rig-machine:` | **16** | the other 93 are guessed from the filename or default to kn7000 |

⚠ The previous version of this note said **two** rigs carried a copy-pasted header and then
listed **four**. Both figures were wrong: it was five, and `kn6_huff.lua` was missing from the
list. Re-run `python3 tools/gen_rig_index.py` to re-measure rather than trusting this table.

**All five are now fixed** (2026-08-15). They turned out to be four siblings sharing the
`kn6_text_bp.lua` breakpoint harness, each arming a different routine, plus one rhythm-group
check — and the copied headers were hiding two real errors, not just wrong names:

| rig | it actually arms | the error the wrong header hid |
|---|---|---|
| `kn6_blit` | `0x484184e4` GRD / `0x484184fb` GWR — the blitter primitives | — |
| `kn6_fn` | `0x48418112` — the KN6000 text drawer | — |
| `kn6_huff` | `0x48405fb1` — the suspected string decompressor | was absent from the README's list entirely |
| `kn7_fn` | `0x48425467` — the **KN7000** text drawer | said `RUN WITH: kn6000`, i.e. **the wrong machine**. It is the healthy-text CONTROL for `kn6_fn` |
| `latin_verify` | `:cpanel:CPL_SEG1` `0x10` | said it pressed **BALLAD**; that is `CPL_SEG2` `0x08`. This one presses **LATIN & WORLD**, which is the whole reason it exists as a second group |

The kn6 siblings each arm their routine at two or three **bus aliases** (`0x4c01…`, `0x8c01…`)
because it was not known which mapping executes; whichever fires identifies the live one.
Both bindings above were checked against the driver's `PORT_NAME`s, which are the source of
truth for button bindings.

Two more rigs are now re-run and verified through `rig.sh` (2026-08-15), bringing the re-run
total to three of 109:

* `liveness.lua` on kn5000 → `distinct=20`, matching the value `gate.sh` records for that model.
* `cpu_state_probe.lua` on kn5000 → 41 state keys, `XNSP`/`XSSP` both readable, matching its
  own recorded measurement.

<!-- BEGIN GENERATED RIG INDEX -- edit via tools/gen_rig_index.py -->

## Every rig

Generated by `tools/gen_rig_index.py` from each rig's own header — 111 rigs. Run any of them with `./tools/rig.sh <rig>`.

The **machine** column is what `rig.sh` will pick: *declared* comes from a `-- rig-machine:` header and is trustworthy; *guessed* is inferred from the filename; *default* means nothing indicated a model and it falls back to kn7000. A guessed or defaulted rig pointed at the wrong driver still runs and still produces output — pass the machine explicitly when in doubt.

| rig | machine | ✔ | what question it answers |
|---|---|---|---|
| `a1` | kn7000 *(default)* |  | a1.lua: r4..rA damp-bank investigation (queue item A1, 2026-07-20) |
| `a1b` | kn7000 *(default)* |  | a1b.lua: pin the remaining r4..rA fields (follow-up to a1.lua). |
| `a3` | kn7000 *(default)* |  | a3.lua: LIVE DSP experiments (queue item A, 2026-07-20) |
| `a3b` | kn7000 *(default)* |  | a3b.lua: A2 completion -- EQUALIZER screen u8 DM bank dump (flat vs presets), |
| `api_probe` | kn7000 *(default)* | ✔ | what does THIS build's MAME Lua API actually offer? |
| `b1` | kn7000 *(default)* |  | B1 unit-feed rewiring verification (chorus->u9, sound-dsp->u2, multi->u1). |
| `b2ab` | kn7000 *(default)* |  | B2 verification: COLD chorus+multi toggles (NO sound-dsp interaction) |
| `b2bp` | kn7000 *(default)* |  | log args + return addr of the per-part effect-send setters: |
| `b2bp2` | kn7000 *(default)* |  | trap the per-part send setters at their REAL call entries, log |
| `b2cap` | kn7000 *(default)* |  | B2 depth-bank capture: log EVERY group-0x20 (effect-bus) TG write |
| `b2cap2` | kn7000 *(default)* |  | cold CHORUS/MULTI toggle: capture EVERYTHING (all sub+main TG writes, |
| `b2dbg` | kn7000 *(default)* |  | sanity: bp on TgVoiceRegWrite_entry (hot on any TG write) + dump ALL console lines |
| `b2dbg2` | kn7000 *(default)* |  | — |
| `b2ram` | kn7000 *(default)* |  | locate the per-part effect DEPTH cache: dump main RAM before and |
| `b2wp` | kn7000 *(default)* |  | watchpoint on the per-part depth shadow block 0x500CE340..47 to |
| `ballad_verify` | kn7000 *(default)* |  | Phase B install verification ("8 Beat 1" fix). |
| `btntest` | kn7000 *(default)* |  | Programmatic button-press test for the KN5000 panel. |
| `cpu_state_probe` | kn7000 *(default)* | ✔ | what registers does this CPU actually expose to Lua? |
| `env1` | kn7000 *(default)* |  | env1.lua: navigate to SOUND EDIT -> AMPLITUDE EDIT -> ENVELOPE page, snapshot each |
| `env10` | kn7000 *(default)* |  | env10.lua: where does the RLS param live? Full-class capture (ALL TG writes, any group) |
| `env11` | kn7000 *(default)* |  | env11.lua: (a) organ baseline r0-r2 (per-sound attack encoding), (b) RLS sweep on a |
| `env12` | kn7000 *(default)* |  | env12.lua: A/B envelope verification capture (run with -wavwrite). |
| `env13` | kn7000 *(default)* |  | env13.lua: crisp slow-attack verification -- SOLO the edited tone. |
| `env14` | kn7000 *(default)* |  | env14.lua: demo-song regression check (press DEMO, let it play ~25 s) |
| `env2` | kn7000 *(default)* |  | env2.lua: ENVELOPE screen interaction probe. |
| `env3` | kn7000 *(default)* |  | env3.lua: AMPLITUDE->ENVELOPE 7-parameter sweep. |
| `env4` | kn7000 *(default)* |  | env4.lua: keypress diagnostic. Home screen, no navigation. |
| `env5` | kn7000 *(default)* |  | env5.lua: why is the TG quiet? Probe gate 0x500ce380, FIFO polling (0x98050004 reads), |
| `env6` | kn7000 *(default)* |  | env6.lua: does a Lua set_value C4 press enter the keybed FIFO? Log distinct values |
| `env7` | kn7000 *(default)* |  | env7.lua: is the TG pipeline alive at all? Install FRESH write taps at t=25 (rule out |
| `env8` | kn7000 *(default)* |  | env8.lua: does the SOUND EDIT ENVELOPE screen audition the keybed? |
| `env9` | kn7000 *(default)* |  | env9.lua: AMPLITUDE->ENVELOPE 7-parameter sweep, corrected: |
| `intc_core_verify` | kn7000 *(default)* |  | INTC+TM5-in-CPU-core refactor live verification (Integrate stage). |
| `keybed_trigger` | kn7000 *(default)* |  | Does pressing a key-bed note make the FIRMWARE emit tone-generator voice |
| `kn24_dump` | kn2400 *(guessed)* |  | dump 0x9C800000..0x9C87FFFF (512KB) at t=40 to kn24_lcd.bin; also fine-scan extent. |
| `kn24_fontsrc` | kn2400 | ✔ | where does the KN2400 text drawer fetch its glyphs? |
| `kn24_probe` | kn2400 *(guessed)* |  | kn2400 boot probe: log PC samples + framebuffer fill, snapshot at end. |
| `kn24_probe2` | kn2400 *(guessed)* |  | kn2400 probe 2: long run, scan lcdbuf (0x9C000000..0x9CFFFFFF) + vram for content. |
| `kn24_snap` | kn2400 *(guessed)* |  | — |
| `kn24_tabledest` | kn2400 | ✔ | where in RAM does the KN2400's table-ROM read land? |
| `kn24_tableshape` | kn2400 | ✔ | what SHAPE of data does the KN2400 expect at 0x48000000? |
| `kn5000_demo_capture` | kn5000 | ✔ | boot, start the Feature Presentation demo, hold it playing. |
| `kn5000_democountdown` | kn5000 | ✔ | does the demo countdown timer ever get armed? |
| `kn5000_demotimer` | kn5000 | ✔ | why does no NEXT song start after the first one ends? |
| `kn5000_note_capture` | kn5000 | ✔ | hold one known keybed note, so its pitch can be measured. |
| `kn5000_p9_stall` | kn5000 | ✔ | when exactly does the Feature Presentation stop, and into what state? |
| `kn5000_p9_writer` | kn5000 | ✔ | WHO stops the Feature Presentation? |
| `kn5000_partsmask` | kn5000 | ✔ | what clears the sequencer part-active mask, and why not these four? |
| `kn5000_poke_test` | kn5000 *(guessed)* |  | Direct 0x8E94 injection probe (reproduce the proven injection from the findings). |
| `kn5000_stuckparts` | kn5000 | ✔ | are the 4 stuck sequencer parts the same bug as the stuck EG voices? |
| `kn5000_tgflags` | kn5000 | ✔ | is ToneGen_GlobalFlags bit 2 EVER set on the shipped configuration? |
| `kn5000_waveselect_log` | kn5000 | ✔ | which waveform chunks does the machine ACTUALLY select? |
| `kn5000_wheel_test` | kn5000 *(guessed)* |  | KN5000 tempo-wheel driver-path test. |
| `kn6000_btn_verify` | kn6000 *(guessed)* |  | KN6000 panel verification: press a few buttons whose silk name predicts a VISIBLE effect, |
| `kn6000_layout_clicktest` | kn6000 *(guessed)* |  | KN6000 layout click-through test. |
| `kn6500_verify` | kn6500 *(guessed)* |  | — |
| `kn6_blit` | kn6000 | ✔ | KN6000 missing-text investigation: WHO reads and writes the graphics plane? |
| `kn6_boxwp` | kn6000 *(guessed)* |  | KN6000: who writes the widget-box interior in the UI index plane? |
| `kn6_fbdump` | kn6000 *(guessed)* |  | — |
| `kn6_fdesc` | kn6000 *(guessed)* |  | — |
| `kn6_fn` | kn6000 | ✔ | KN6000 missing-text investigation: does the TEXT DRAWER ever run? |
| `kn6_fontchk` | kn6000 *(guessed)* |  | — |
| `kn6_g` | kn6000 *(guessed)* |  | — |
| `kn6_gate` | kn6000 *(guessed)* |  | — |
| `kn6_huff` | kn6000 | ✔ | KN6000 missing-text investigation: is the string decompressor running? |
| `kn6_plane` | kn6000 *(guessed)* |  | KN6000: dump the UI index plane (0x5020042C), the companion plane, and the CLUT. |
| `kn6_proof` | kn6000 *(guessed)* |  | DIAGNOSTIC ONLY (never shipped): prove that the KN6000's missing text is caused solely by |
| `kn6_rdwp` | kn6000 *(guessed)* |  | kn6000: read-watch the queued string "  Modern E.P." at 0x50007B60 -> who consumes it? |
| `kn6_str` | kn6000 *(guessed)* |  | kn6000: capture C34B draw-post args incl. the stack data ptr; dump pointed memory. |
| `kn6_text_bp` | kn6000 *(guessed)* |  | KN6000 text investigation: execution breakpoints on the 5 |
| `kn6_txt` | kn6000 *(guessed)* |  | KN6000: does the TEXT DRAWER run, and what font pointer does it get? |
| `kn6_wp` | kn6000 *(guessed)* |  | watchpoints on framebuffer pixels that DO receive content -> catch the blitter PC. |
| `kn7000_regress` | kn7000 *(default)* |  | — |
| `kn7_fn` | kn7000 | ✔ | the KN7000 control: its text drawer, on a machine whose text WORKS. |
| `kn7_fontdump` | kn7000 *(default)* |  | — |
| `kn7_fontrd` | kn7000 *(default)* |  | KN7000: who READS the font descriptor table at 0x50122DB8 ? -> the glyph fetch / text drawer |
| `kn7_planedump` | kn7000 *(default)* |  | — |
| `kn7_txtcall` | kn7000 *(default)* |  | KN7000: who CALLS the text drawer 0x48425467 ? |
| `kn7_txtstk` | kn7000 *(default)* |  | — |
| `kn7_wp` | kn7000 *(default)* |  | KN7000: watch a UI-plane glyph pixel to catch the text/glyph blitter PC. |
| `kn7_wp2` | kn7000 *(default)* |  | KN7000: watch a UI-plane glyph pixel to catch the text/glyph blitter PC. |
| `kn7_wp3` | kn7000 *(default)* |  | KN7000: watch a UI-plane glyph pixel to catch the text/glyph blitter PC. |
| `kn7snap` | kn7000 *(default)* |  | — |
| `late` | kn7000 *(default)* |  | — |
| `latin_verify` | kn7000 | ✔ | the SECOND rhythm group, verifying the "8 Beat 1" fix generalises. |
| `ledtest_sweep` | kn7000 *(default)* |  | LED-test button->LED sweep (REAL test). Run MAME with this as -autoboot_script, then hold F3+F4 at |
| `ledtest_sweep2` | kn7000 *(default)* |  | Find TEMPO/PROGRAM (PANEL MEMORY SET lights the whole CPR bank) + probe the SD LEDs. |
| `liveness` | kn7000 *(default)* | ✔ | did this machine actually boot and draw its UI? |
| `money` | kn7000 *(default)* |  | — |
| `nopress` | kn7000 *(default)* |  | — |
| `note` | kn7000 *(default)* |  | At t>=16s (home screen reached) press PC key "C4" and hold it, so the first-cut |
| `one` | kn7000 *(default)* |  | — |
| `probe` | kn7000 *(default)* |  | Probe every bit of the two SOUND GROUP segments. Stay on the SOUND screen so each |
| `probe_late` | kn7000 *(default)* |  | — |
| `progress` | kn7000 *(default)* |  | — |
| `sdload_rt` | kn7000 *(default)* |  | sdload_rt run E: fresh boot (default rhythm) -> SD LOAD browser -> LOAD folder01/song01 |
| `sdnav_a` | kn7000 *(default)* |  | Run A: enter SD MENU via SD CARD LOAD, test re-press idempotency, then LCDL1-5 |
| `sdnav_b1` | kn7000 *(default)* |  | Run B1: the 5 RIGHT soft keys, each from a verified SD MENU state |
| `sdnav_b1x` | kn7000 *(default)* |  | Run B1: the 5 RIGHT soft keys, each from a verified SD MENU state |
| `sdnav_b2x` | kn7000 *(default)* |  | Run B2: remaining soft keys from a verified SD MENU state |
| `sdnav_c` | kn7000 *(default)* |  | Run C: DATA dial, PAGE UP/DOWN, EXIT, DISPLAY HOLD on the SD MENU |
| `sdnav_dx` | kn7000 *(default)* |  | Run D: the six CPSD SD-board switches on the SD MENU |
| `sdnav_lib` | kn7000 *(default)* |  | Shared SD-MENU trial runner. Define TRIALS (list of {tag,mask,name}) then dofile this. |
| `sdnav_smoke` | kn7000 *(default)* |  | Smoke test: confirm SD MENU at t=30, inspect DIAL field API |
| `sdsave1` | kn7000 *(default)* |  | sdsave1: SD SAVE round-trip step 1 -- reach the SAVE browser and attempt a TECHNICS FORMAT save. |
| `sdsave2` | kn7000 *(default)* |  | sdsave2 run A: SD MENU -> LCDR2 (SAVE MENU) -> LCDR2 (TECHNICS FORMAT, row 2) -> snapshot what follows. |
| `sdsave3` | kn7000 *(default)* |  | sdsave3 run B: reach the SD SAVE browser (TECHNICS FORMAT) and press SAVE (LCDR1). |
| `sdsave4` | kn7000 *(default)* |  | sdsave4 run C: SAVE browser -> SAVE (LCDR1) -> confirm overwrite YES (LCDR3) -> watch the write. |
| `sdsave5` | kn7000 *(default)* |  | sdsave5 run D: make the panel state distinguishable (RHYTHM GROUP BALLAD), then |
| `shot` | kn7000 *(default)* |  | — |
| `sio_core_verify` | kn7000 *(default)* |  | SIO-in-CPU-core refactor live verification (Integrate stage). |

**✔** = the header documents a runnable `rig.sh` command. 21 of 111 do; the rest still need one.

<!-- END GENERATED RIG INDEX -->
