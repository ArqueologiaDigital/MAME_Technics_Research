#!/usr/bin/env python3
"""Audit save-state coverage across the Technics MAME devices.

WHY: MAME requires working save states, and an unregistered mutable member is invisible until
someone loads a state and the machine is subtly wrong. That already happened here — nine
effect-send gains in kn_tonegen were omitted because they are `std::atomic<float>` and
`save_item()` cannot register an atomic, so a state saved with reverb engaged restored with the
boot-default mix. Nothing looked wrong until you listened.

    python3 tools/audit_savestate.py              # summary per device
    python3 tools/audit_savestate.py --verbose    # list every unregistered member
    python3 tools/audit_savestate.py --exempt     # also show what was auto-exempted, and why

It compares `m_*` members declared in each header against `save_item(NAME(m_*))` /
`save_pointer(NAME(m_*))` in the matching .cpp.

⚠ WHAT THIS IS NOT: a correctness proof. It is a *lead generator*. It cannot tell mutable state
from a constant, and it auto-exempts by TYPE, which is a heuristic — a `std::vector` really can
be mutable runtime state even though the exemption list assumes ROM-derived tables. Treat every
line it prints as a question, not a defect, and read the code before changing anything.

Auto-exempt types, and the reason each is safe to skip:
  required_device / optional_device / required_shared_ptr / memory_share / memory_region
  required_ioport / optional_ioport / output_finder / devcb_*   -- MAME-managed handles
  sound_stream *                                                -- owned by the sound manager
  emu_timer *                                                   -- saved by the timer system
  ioport_field * / ioport_port *                                -- resolved from the port list
  const <anything>                                              -- immutable after construction

⚠ SHADOWED MEMBERS READ AS UNREGISTERED. State that cannot be handed to save_item() directly
(std::atomic, std::queue, std::map) is conventionally copied into a plain shadow around a save,
via device_pre_save()/device_post_load(). This script cannot follow that indirection, so such
members still appear in the gap list. Devices carrying those hooks are annotated [hooks]; check
them by hand before treating a line as outstanding. kn_tonegen's nine `m_gain_*` are exactly
this case -- they are saved, through `m_gain_save`.
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "src" / "mame" / "matsushita"

EXEMPT_TYPES = (
    "required_device", "optional_device", "required_shared_ptr", "optional_shared_ptr",
    "required_memory_region", "optional_memory_region", "required_ioport", "optional_ioport",
    "required_region_ptr", "optional_region_ptr", "memory_share", "memory_region",
    "output_finder", "devcb_read", "devcb_write", "sound_stream", "emu_timer",
    "address_space", "memory_bank", "device_t", "ioport_field", "ioport_port",
)

# A member declaration: optional const/static/mutable, a type, then m_name, then [] or = or ;
DECL = re.compile(
    r"^\s*(?P<qual>(?:static\s+|const\s+|mutable\s+|constexpr\s+)*)"
    r"(?P<type>[A-Za-z_][\w:<>,\s\*&\[\]]*?)\s*"
    r"\b(?P<name>m_[a-z0-9_]+)\s*(?:\[[^\]]*\])*\s*(?:=|;|\{)"
)


def declared(path):
    out = {}
    for line in path.read_text(errors="replace").splitlines():
        s = line.split("//")[0]
        m = DECL.match(s)
        if m and m.group("name") not in out:
            out[m.group("name")] = (m.group("qual") + m.group("type")).strip()
    return out


def registered(path):
    if not path.is_file():
        return set()
    txt = path.read_text(errors="replace")
    return set(re.findall(r"save_(?:item|pointer)\(\s*NAME\(\s*(m_[a-z0-9_]+)", txt))


def exempt_reason(typ):
    for t in EXEMPT_TYPES:
        if t in typ:
            return f"MAME-managed ({t})"
    if typ.startswith("const ") or typ.startswith("constexpr ") or typ.startswith("static const"):
        return "const"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--exempt", action="store_true")
    ap.add_argument("--dir", type=pathlib.Path, default=ROOT)
    args = ap.parse_args()

    headers = sorted(args.dir.glob("*.h"))
    if not headers:
        print(f"no headers under {args.dir}", file=sys.stderr)
        return 2

    total_gap = 0
    rows = []
    for h in headers:
        cpp = h.with_suffix(".cpp")
        decls = declared(h)
        if not decls:
            continue
        reg = registered(cpp) | registered(h)
        hooks = cpp.is_file() and "device_pre_save" in cpp.read_text(errors="replace")
        gaps, exempts = [], []
        for name, typ in sorted(decls.items()):
            if name in reg:
                continue
            why = exempt_reason(typ)
            (exempts if why else gaps).append((name, typ, why))
        total_gap += len(gaps)
        rows.append((h.name, len(decls), len(reg), gaps, exempts, hooks))

    print(f"{'device header':38s} {'decl':>5s} {'saved':>6s} {'unregistered':>13s}")
    print("-" * 66)
    for name, ndecl, nreg, gaps, exempts, hooks in rows:
        flag = ("  [hooks: some may be shadowed]" if hooks else "  <-- look") if gaps else ""
        print(f"{name:38s} {ndecl:5d} {nreg:6d} {len(gaps):13d}{flag}")
        if args.verbose and gaps:
            for n, t, _ in gaps:
                print(f"      {n:24s} {t}")
        if args.exempt and exempts:
            for n, t, why in exempts:
                print(f"      (exempt) {n:16s} {t}   -- {why}")

    print("-" * 66)
    print(f"{total_gap} member(s) declared but not registered, across {len(rows)} device header(s).")
    print("Each is a QUESTION, not a defect: read the code before changing anything. A member")
    print("that never changes after device_start does not need saving.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
