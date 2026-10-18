#!/usr/bin/env python3
"""build_presentation.py -- question it answers: what is the smallest change that turns the
real CA-6FP01 "Weserbergland" KN6000 feature-presentation set into one the KN7000 firmware
accepts, so that it can be run in MAME?

Input: the clean archive copy of ca6fp01 (extract/ca6fp01: FEATURE.PRE, weserl.act,
WESERL.SQT, pic01..pic19 incl. pic12r1/pic18r2) and the built-in demo song 1 parts
(demo_song_extract.py output).  Output directory OUT gets 8.3 upper-case names:
  FEATURE.PRE  KN7000 form (FeaturePreLoad 0x4854E20C): line 1 base name, line 2 title:
               b"WESERL\\r\\nWESERBERGLAND\\r\\n" (from the sample's EXEC SRC= and NAME=)
  WESERL.ACT   b"SSW-ACT-V01\\r\\n" + the sample's weserl.act bytes unchanged (the 11-byte
               check in SswActScriptLoad 0x4858085C)
  WESERL.SQT   NOT the sample's song: the sample is a KN6000 'I KD' song, which
               FeatureDemoSqtLoad refuses (-0xC8, featurepre lane SDA).  Instead a KN7000
               'J KD' whole-sequencer file (format 0xF0) whose song 1 is the built-in
               OVERTURE demo song (record + pages inflated from ROM), because that song
               carries 18 USER picture events n = 0..17 (status 0x8A) -- see sqt_jkd.py.
  PICnn.JPG    the sample's pictures, bytes unchanged, names upper-cased as the .ACT
               spells them (IMG SRC="PIC01.JPG" ...)
usage: python3 -I build_presentation.py SAMPLEDIR DEMOSONGDIR OUT
"""
import sys, os, subprocess, shutil, hashlib
src, demo, out = sys.argv[1:4]
here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(out, exist_ok=True)
open(os.path.join(out, "FEATURE.PRE"), "wb").write(b"WESERL\r\nWESERBERGLAND\r\n")
act = open(os.path.join(src, "weserl.act"), "rb").read()
open(os.path.join(out, "WESERL.ACT"), "wb").write(b"SSW-ACT-V01\r\n" + act)
subprocess.run([sys.executable, "-I", os.path.join(here, "sqt_jkd.py"), "build",
                os.path.join(out, "WESERL.SQT"), os.path.join(demo, "demo1_record.bin"),
                os.path.join(demo, "demo1_pages.bin")], check=True)
for f in sorted(os.listdir(src)):
    if f.lower().endswith(".jpg"):
        shutil.copyfile(os.path.join(src, f), os.path.join(out, f.upper()))
for f in sorted(os.listdir(out)):
    b = open(os.path.join(out, f), "rb").read()
    print(f"{f:12s} {len(b):7d}  md5 {hashlib.md5(b).hexdigest()}")
