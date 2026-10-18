#!/bin/bash
# step.sh DIR "cmd1;cmd2;..." -- append commands (and a final snap) to a remote.lua command file,
# wait until the rig has run them, and save a crop of the newest snapshot as DIR/now.png.
D="$1"; shift
IFS=';' read -ra C <<< "$1"
for c in "${C[@]}"; do echo "$c" >> "$D/cmd.txt"; done
echo snap >> "$D/cmd.txt"
n=$(grep -c '' "$D/cmd.txt")
until [ "$(grep -c '^\[.*\] \(OK\|ERR\)' "$D/cmd.txt.log")" -ge "$n" ]; do sleep 1; done
grep 'ERR' "$D/cmd.txt.log" | tail -1
f=$(ls "$D"/snap/*/*.png | tail -1)
python3 -I -c "
import sys
from PIL import Image
im=Image.open(sys.argv[1]); w,h=im.size
box=(340,40,1060,350) if w==1440 else ((470,75,810,330) if w==1280 else (150,50,850,320))
im.crop(box).save(sys.argv[2])" "$f" "$D/now.png"
echo "$f"
