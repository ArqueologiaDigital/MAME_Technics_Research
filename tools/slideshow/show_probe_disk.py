#!/usr/bin/env python3
"""show_probe_disk.py -- a KN7000 FEATURE.PRE floppy whose slides each SHOW one GUI object by name.

Question it serves: what does the slide-show tag <SHOW OBJ="name"> do with an arbitrary object
name -- can a presentation put any of the firmware's screens (for example the Panel Simulator or
the DEBUG TOOLS objects) on the LCD? The SHOW handler (0x4857FB88) looks the name up across every
GUI view slot (0x48580EE6) and sends the object EV_PAINT (0x00050009).

The disk reuses the converted CA-6FP01 song (WESERL.SQT, 'J KD', with PIC points 0..17 that
select slides 0..17 as it plays) and its FEATURE.PRE; only the .ACT changes: slide n shows the
n-th name given on the command line, and slides past the list fall back to the first name.

usage: python3 -I show_probe_disk.py PRESENTATION_DIR OUT.img NAME [NAME ...]
  PRESENTATION_DIR holds FEATURE.PRE and WESERL.SQT (build_presentation.py output).
"""
import os
import subprocess
import sys
import tempfile


def act_text(names):
    out = ["SSW-ACT-V01", "<ACTION>", ""]
    for n in range(18):
        name = names[n] if n < len(names) else names[0]
        out += ['<ACT NO=%d>' % n, '<SHOW OBJ="%s">' % name, '</ACT>', '']
    out += ["</ACTION>", ""]
    return "\r\n".join(out).encode("latin-1")


def main():
    if len(sys.argv) < 4:
        sys.exit("usage: show_probe_disk.py PRESENTATION_DIR OUT.img NAME [NAME ...]")
    src, dst, names = sys.argv[1], sys.argv[2], sys.argv[3:]
    maker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_fat12.py")
    with tempfile.TemporaryDirectory() as tmp:          # honours TMPDIR
        act = os.path.join(tmp, "WESERL.ACT")
        open(act, "wb").write(act_text(names))
        files = ["FEATURE.PRE=" + os.path.join(src, "FEATURE.PRE"),
                 "WESERL.SQT=" + os.path.join(src, "WESERL.SQT"),
                 "WESERL.ACT=" + act]
        subprocess.run([sys.executable, "-I", maker, dst] + files, check=True)
    for i, n in enumerate(names):
        print("slide %d: SHOW %s" % (i, n))


if __name__ == "__main__":
    main()
