# KN5000 Feature Demo / panel probes (2026-08-11)

Used to bisect what the demo needs on pristine `upstream/master`, for the PR at
`notes/upstream-patches/PR-DRAFT-kn5000-ic14.md`. Port tags are resolved as `:TAG` first and
`:cpanel:TAG` second, so they work on both upstream (ports on the root device) and our overlay.

| script | what it does |
|---|---|
| `demo_probe.lua` | navigates DEMO -> LEFT 4 -> LEFT 2, samples transport `0x0420`, beat `0x0417`, watchdog `0x32ed` every 2 s |
| `demo_max.lua` | the one to use: per-frame **maxima** plus current value, and a snapshot each interval. Coarse sampling misses the documented ~0.3 s burst |
| `demo_snap.lua` | `demo_probe` plus periodic snapshots |
| `cp_press.lua` | slow unambiguous panel presses from a settled boot, snapshot after each |

Run:

    ./kn5000 kn5000 -rompath <romset> -skip_gameinfo -autoboot_delay 0 \
      -autoboot_script demo_max.lua -str 60 -snapshot_directory <dir> \
      -cfg_directory <dir> -nvram_directory <dir>

Signals: transport `0x0420` 0C = terminal STOP, 04 = running. Sub-tick `0x0417` frozen at 00 means
INTTR5 is not firing. AccPlayMode `0x22FC` reaching 03 means playback started. Count *distinct*
snapshots — a two-state alternation is a blink, not slides advancing.

⚠ `emu.register_stop` does not exist in this MAME; print tallies inline instead.
