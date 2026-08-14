# Lua measurement rigs

Rescued 2026-08-14 from `~/compartilhado/kn7000-emulator/`, which is **not a git repository** — it
is the publish target of `tools/publish-binary.sh` and is overwritten on every publish. These 95
scripts were the only copies of themselves, and several are the named regression gate in committed
notes. Nothing else in that directory is unique; treat it as derived from now on.

Run one with:

```
cd ~/compartilhado/kn7000-emulator
./kn7000 <machine> -rompath ./roms -autoboot_script <this-dir>/<rig>.lua -skip_gameinfo
```

⚠ Two hazards these rigs encode, both learned the hard way:
- **Hold the notifier handle in a global** (`_G.m.h = emu.add_machine_frame_notifier(...)`) or the
  Lua GC silently collects it and the tap never fires.
- **`ioport_field:set_value()` toggles a `PORT_CONFNAME` field**, it does not assign, and MAME
  persists it in `cfg/*.cfg`. Use a private `-cfg_directory` for rigs — but reproduce the *user's*
  cfg when chasing a user-reported bug (see RULE 20 in the project notes).

## The load-bearing ones

| rig | what it does | the signal |
|---|---|---|
| `money.lua` | **the audio oracle.** Presses keybed note `KEYS1` mask `0x0100` at t=16 s, releases at t=17 s. Run with `-wavwrite`; the WAV's md5 is the regression baseline quoted in at least six notes. | baseline md5 `c3b67ea711ce3c00f8ae2af1e07651cb` — ⚠ this is a *regression* hash (nothing changed), **not** evidence of correctness |
| `env14.lua` | demo-song regression: press DEMO, play ~25 s | audio + transport regression |
| `kn7000_regress.lua` | save a settled home state, then press PROGRAM MENUS / DISK MENU LOAD / PIANO from it, snapshotting each | three screenshots; catches UI regressions without re-booting |
| `sio_core_verify.lua` | live verification of the SIO-into-CPU-core refactor | boot + panel still work after the move |
| `intc_core_verify.lua` | same for the INTC + TM5 timer move | tempo timer drives the demo |
| `a3.lua`, `a3b.lua` | live DSP experiments; produced the shipped DSP unit-role map and the EQUALIZER bank dump | per-unit DM bank contents |

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

## Honesty note

This index was built from each script's own header comment plus a reading of the handful that had
none. **The scripts were not re-run during the rescue**, so any one of them may have rotted against
the current driver — several target addresses and screens that later work moved. Re-run before
trusting, and fix the header while you are there: about a fifth have no description at all, and two
(`kn6_blit.lua`, `kn6_fn.lua`, `kn7_fn.lua`, `latin_verify.lua`) carry a copy-pasted header naming a
*different* script.
