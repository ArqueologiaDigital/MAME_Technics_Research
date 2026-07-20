#!/usr/bin/env python3
"""Re-inline tools/slider_lib.lua into src/mame/layout/kn5000.lay.

MAME layout <script> blocks cannot include external files, so the shared slider/knob
library has to be copied into every layout that uses it. The KN7000 and KN6000 layouts
are fully generated (tools/gen_lay.py, tools/gen_kn6000_lay.py) and inline it as part of
generation; the KN5000 layout is hand-maintained, so this script refreshes just its
library section in place. Run it after editing tools/slider_lib.lua.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LAY = os.path.join(ROOT, "src", "mame", "layout", "kn5000.lay")
LIB = os.path.join(HERE, "slider_lib.lua")

BEGIN = "-- Slider and knob library begins."
END = "-- Slider and knob library ends."


def main():
    lay = open(LAY).read()
    lib = open(LIB).read()

    if BEGIN not in lib or END not in lib:
        sys.exit("slider_lib.lua is missing its begin/end markers")
    if BEGIN not in lay or END not in lay:
        sys.exit("kn5000.lay is missing the inlined library markers")

    start = lay.index(BEGIN)
    end = lay.index(END) + len(END)
    lib_start = lib.index(BEGIN)
    lib_end = lib.index(END) + len(END)

    updated = lay[:start] + lib[lib_start:lib_end] + lay[end:]
    if updated == lay:
        print("kn5000.lay: slider library already up to date")
        return
    open(LAY, "w").write(updated)
    print("kn5000.lay: slider library refreshed from tools/slider_lib.lua")


if __name__ == "__main__":
    main()
