#!/usr/bin/env python3
"""
kn5000_dsp_paramlist.py

Resolve the KN5000 DIGITAL EFFECT per-effect parameter lists.

Two roles:
  1. Static: decode the 85-entry parameter NAME table (ROM 0x0324D5, stride 17)
     and the UNIT table (ROM 0x03241A, stride 2) from the main-CPU program ROM,
     plus the 100-slot effect NAME table (ROM 0x033568, stride 18, descending).
  2. Resolver: given a live dump of the RAM name-index array (RAM[0x29AC..],
     count RAM[0x29AA], 1-based indices) captured while the effect-edit page is
     up, print the ordered [slot -> name, unit] list.

The name index stored in RAM[0x29AC+slot] is 1-BASED into the name table:
    name = names[idx-1], unit = units[idx-1].

Usage:
    # dump the static tables
    kn5000_dsp_paramlist.py <program.rom>

    # resolve a live capture (JSON produced by tools/kn5000_paramdump.lua)
    kn5000_dsp_paramlist.py <program.rom> --resolve capture.json
"""
import sys, json

NAME_OFF = 0x0324D5
NAME_STRIDE = 17
UNIT_OFF = 0x03241A
UNIT_STRIDE = 2
NAME_COUNT = 85

EFFNAME_OFF = 0x033568
EFFNAME_STRIDE = 18
EFFNAME_COUNT = 100  # slots; anchored algo 20 = CONCERT REVERB 1, descending


def load(path):
    with open(path, "rb") as f:
        return f.read()


def cstr(b, off, maxlen):
    s = b[off:off+maxlen]
    # strings are 16 chars + ':' for names; strip trailing spaces / colon / NUL
    txt = s.split(b"\x00", 1)[0]
    return txt.decode("latin-1", "replace").rstrip()


def names_table(rom):
    names = []
    for i in range(NAME_COUNT):
        raw = rom[NAME_OFF + NAME_STRIDE*i : NAME_OFF + NAME_STRIDE*i + 16]
        s = raw.decode("latin-1", "replace").rstrip()
        # trailing ':' is stored as the 17th byte (separator); name is 16 wide
        names.append(s)
    return names


def units_table(rom):
    units = []
    for i in range(NAME_COUNT):
        raw = rom[UNIT_OFF + UNIT_STRIDE*i : UNIT_OFF + UNIT_STRIDE*i + 2]
        s = raw.decode("latin-1", "replace").rstrip()
        units.append(s)
    return units


def effect_names(rom):
    # descending: name[algo] = rom[EFFNAME_OFF - EFFNAME_STRIDE*algo]
    out = []
    for algo in range(EFFNAME_COUNT):
        off = EFFNAME_OFF - EFFNAME_STRIDE*algo
        if off < 0:
            break
        raw = rom[off:off+EFFNAME_STRIDE]
        out.append(raw.decode("latin-1", "replace").rstrip())
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    rom = load(sys.argv[1])
    names = names_table(rom)
    units = units_table(rom)

    if "--resolve" in sys.argv:
        cap = json.load(open(sys.argv[sys.argv.index("--resolve")+1]))
        effs = effect_names(rom)
        for entry in cap:
            algo = entry.get("algo")
            cnt = entry["count"]
            idxs = entry["indices"][:cnt]
            ename = entry.get("name") or (effs[algo] if (algo is not None and algo < len(effs)) else "?")
            print(f"\n=== '{ename}'  page-type=0x{entry.get('type',0):02X}  slots={cnt} ===")
            for slot, idx in enumerate(idxs):
                if 1 <= idx <= NAME_COUNT:
                    nm, un = names[idx-1], units[idx-1]
                else:
                    nm, un = f"<idx {idx} OOR>", ""
                print(f"  [{slot:2d}] idx={idx:3d}  {nm:<16} {un}")
        return

    # default: dump the name/unit tables
    print("# 85-entry parameter NAME / UNIT table (ROM 0x0324D5 / 0x03241A)")
    for i in range(NAME_COUNT):
        print(f"{i+1:3d} (0x{i+1:02X})  {names[i]:<16} [{units[i]}]")


if __name__ == "__main__":
    main()
