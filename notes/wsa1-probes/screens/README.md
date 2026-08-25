# SX-WSA1R boot screens — the "does it still boot?" control

Two frames from one run of the build committed alongside them, captured by
`wsa1_panel_link.lua` (which snapshots every 15 emulated seconds):

```
cd ~/compartilhado/kn7000_mame_build
DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 200 -window \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_panel_link.lua
```

| file | when | what it shows |
|---|---|---|
| `wsa1r_t60_blank.png`                  | t = 60 s  | still blank — the panel is being drawn |
| `wsa1r_t195_all_initial_setting.png`   | t = 195 s | `ALL INITIAL SETTING!`, unchanged since t = 75 s |

The run takes 14 shots at t = 15, 30 … 195 s. The first four are blank (857 byte
PNGs) and the last ten are the message (1,214 byte PNGs), so the message appears
between t = 60 and t = 75 and then stops changing — a live system sitting on a
message, not a hang. That is the control the control-panel work had to pass:
wiring `wsa1_cpanel` must not cost the machine its boot.

⚠ The colours are a DRIVER CHOICE, not a measurement — see `palette_init()` in
`wsa1.cpp`. Only the glyphs are evidence.
