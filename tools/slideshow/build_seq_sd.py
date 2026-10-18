#!/usr/bin/env python3
"""build_seq_sd.py -- question it answers: does an ordinary SEQUENCER song load from SD
(TECHNICS format, folder TFLD001, song 01001KN7) also load <song>.ACT and its pictures into
the main slide-show pool (SeqActFileLoad 0x4852C10C -> SswSongActLoad 0x4857EE8D), and do
the pictures appear at the song's PIC points when the song is played with SEQUENCER PLAY?

It writes a copy of the real KN7000 SD card image (technics_roms/media/
sdcard_from_real_kn7000.img, md5 c3bcea2346cb3bb7d803e8c48aebce78, never modified) in which
  TFLD001/01001KN7.SQT = WESERL.SQT from build_presentation.py ('J KD', song 1 = the
                         built-in OVERTURE demo song with 18 USER picture events n = 0..17)
  TFLD001/01001KN7.ACT = b"SSW-ACT-V01\\r\\n" + the CA-6FP03 handy.act (acts 1..8, IMG SRC
                         PIC01..PIC08.JPG) -- the 8-picture set is used here because the main
                         pool is 606,316 or 344,172 bytes depending on TgStrapProbe
  TFLD001/PIC01..08.JPG = the CA-6FP03 pictures, bytes unchanged
usage: python3 -I build_seq_sd.py SRC_SD_IMG OUT_SD_IMG HANDYDIR PRESENTATIONDIR SD_ADDFILE [SQT]
  SQT (optional) replaces WESERL.SQT as 01001KN7.SQT (SEQ2: songs 2..10 = the real save's
  empty records, built with sqt_jkd.py build ... real01001_part1.bin)
"""
import sys, os, shutil, subprocess, hashlib
src, out, handy, pres, addfile = sys.argv[1:6]
shutil.copyfile(src, out); os.chmod(out, 0o644)
stage = os.path.join(os.path.dirname(os.path.abspath(out)), "seq_stage_" + os.path.basename(out).split(".")[0])
os.makedirs(stage, exist_ok=True)
sqt = sys.argv[6] if len(sys.argv) > 6 else os.path.join(pres, "WESERL.SQT")
files = {"01001KN7.SQT": open(sqt, "rb").read(),
         "01001KN7.ACT": b"SSW-ACT-V01\r\n" + open(os.path.join(handy, "handy.act"), "rb").read()}
for k in range(1, 9):
    files[f"PIC{k:02d}.JPG"] = open(os.path.join(handy, f"pic{k:02d}.jpg"), "rb").read()
args = []
for name, data in files.items():
    p = os.path.join(stage, name); open(p, "wb").write(data)
    args += ["PRIVATE\\TECHNICS\\KN7000\\TFLD001\\" + name, p]
    print(f"{name:14s} {len(data):6d} md5 {hashlib.md5(data).hexdigest()}")
subprocess.run([sys.executable, "-I", addfile, out] + args, check=True, stdout=subprocess.DEVNULL)
print("built", out)
