# KN5000 keybed: input names one octave off the instrument's (2026-10-22)

Felipe bound keys to the inputs C3 and F4 and the firmware's SPLIT POINT screen named them C2 and F3. The
driver named MIDI 60 "C4"; the KN5000 itself names it C3 (Technics' convention). The ports and the notes sent
were right; only the names were wrong. The inputs are now C1..C6 (MIDI 36..96), as the firmware names them.
MAME keeps assignments by port and bit, so existing `cfg` files still bind the same physical keys.

## The measurement

Hold SPLIT POINT (the screen opens after about 1 s), press one key, read the name the screen shows.

| input pressed (old name) | MIDI | the SPLIT POINT screen | input name now |
|--------------------------|------|------------------------|----------------|
| C#2                      | 37   | D♭1                    | C#1            |
| C3                       | 48   | C2                     | C2             |
| C4                       | 60   | C3                     | C3             |
| F4                       | 65   | F3                     | F3             |
| F5                       | 77   | F4                     | F4             |
| G#5                      | 80   | A♭4                    | G#4            |
| A5                       | 81   | A4                     | A4             |
| A#5                      | 82   | B♭4                    | A#4            |
| C6                       | 84   | C5                     | C5             |
| C7                       | 96   | C6                     | C6             |

The binary with the new names (md5 `345965464b9431f7f9c307420a85b388`) shows each input's own name for C1,
C2, C3, F4, G#4 (A♭4), A4, A#4 (B♭4), C5 and C6. `tools/gate.sh --model kn5000`: 5 passed, demo oracle
`3f29427f` unchanged.

## Reproducing

With technics-anotherworld's `kn5000cnv/probes` (`seq.lua` has the SPLIT button, `keys.lua` presses inputs by
name, `multi.lua` runs both):

```sh
H=~/compartilhado/technics-anotherworld/kn5000cnv/probes; R=~/compartilhado/tmp/kn5000-split
mkdir -p $R/nv $R/cfg $R/snap; cp -r ~/compartilhado/kn7000-emulator/nvram/kn5000 $R/nv/
cd ~/compartilhado/kn7000-emulator && PROBES="$H/seq.lua $H/keys.lua" KEYS="26:C1*0.3;27:C3*0.3;28:F4*0.3" \
    SEQ="24:SPLIT*5;26.6:snap;27.6:snap;28.6:snap;29:quit" DISPLAY=:0 ./kn7000 kn5000 -rompath ./roms \
    -pluginspath ./plugins -skip_gameinfo -window -nothrottle -sound none -nvram_directory $R/nv \
    -cfg_directory $R/cfg -snapshot_directory $R/snap -snapname '%i' -autoboot_script $H/multi.lua
```

The four audit probes that press KN5000 keys by name (`notes/audit/data-output/concur.lua`, `panprobe.lua`,
`panprobe2.lua`, `notes/audit/data/kn5000-outcap.lua`) now use the new names for the same keys; their output
labels are unchanged.
