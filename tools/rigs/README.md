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
later work moved. Re-run before
trusting, and fix the header while you are there: about a fifth have no description at all, and two
(`kn6_blit.lua`, `kn6_fn.lua`, `kn7_fn.lua`, `latin_verify.lua`) carry a copy-pasted header naming a
*different* script.
