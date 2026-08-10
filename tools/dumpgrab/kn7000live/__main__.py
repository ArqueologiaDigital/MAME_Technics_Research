"""Command line for the live MEMORY DUMP reader.

    # what can we capture from?
    python3 -m kn7000live devices

    # the live view -- this is the tool
    python3 -m kn7000live live --source v4l2:/dev/video0 --store ~/kn7000-dump

    # how far has the sweep got?
    python3 -m kn7000live report --store ~/kn7000-dump

    # take the bytes out
    python3 -m kn7000live export --store ~/kn7000-dump --window program \\
                                 --out build893_program.bin

    # measure the decoder against a page whose 256 bytes are known
    python3 -m kn7000live selftest --source image:real-NTSC-48019000.png \\
                                   --address 48019000 --frames 60
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

from . import geom as G
from . import recog as R
from .app import Engine, LiveApp
from .source import list_v4l2_devices, open_source
from .store import WINDOWS, DumpStore

WINDOW_NAMES = {"table": (0x48000000, 0x48400000),
                "program": (0x48400000, 0x48800000),
                "sram": (0x84000000, 0x85000000)}


def _load_calib(path, frame, ncols=G.NCOL_HEX):
    if path and os.path.exists(path):
        with open(path) as fh:
            return G.Registration.from_json(json.load(fh))
    return G.Registration(G.auto_seed(frame), ncols=ncols)


def _mkengine(args, frame, store):
    calib = args.calib or os.path.join(store.path, "calib.json")
    reg = _load_calib(calib, frame)
    bankp = os.path.join(store.path, "bank.npz")
    bank = R.GlyphBank.load(bankp) if os.path.exists(bankp) and not args.fresh_templates else R.GlyphBank()
    seed = int(args.seed_address, 16) if args.seed_address else None
    e = Engine(store, reg, bank, seed_base=seed,
               assume_aligned=not args.any_address,
               restrict_windows=not args.no_restrict,
               motion_gate=args.motion_gate, decay=args.decay)
    return e, calib


def _first_frame(src, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        f = src.read()
        if f is not None:
            return f
        if not getattr(src, "alive", True):
            break
        time.sleep(0.05)
    return None


# --------------------------------------------------------------------------- #
def cmd_devices(args) -> int:
    devs = list_v4l2_devices()
    if not devs:
        print("no /dev/video* devices found.")
        print("plug the camera or capture stick in; if it is there but not listed,")
        print("check that this user is in the 'video' group.")
        return 1
    for d, fmts in devs:
        print(d)
        for line in fmts:
            print("   " + line.strip())
    return 0


def cmd_live(args) -> int:
    src = open_source(args.source, args.width, args.height, args.fps, args.input_format)
    frame = _first_frame(src)
    if frame is None:
        print("no frame from %s" % args.source)
        err = getattr(src, "error", "")
        if err:
            print("ffmpeg said:\n" + err)
        return 1
    store = DumpStore(args.store, lock_weight=args.lock_weight,
                      lock_frames=args.lock_frames, lock_share=args.lock_share)
    e, calib = _mkengine(args, frame, store)
    print("%s  %dx%d   store %s (%d pages, %d bytes locked)"
          % (src.name, frame.shape[1], frame.shape[0], store.path, len(store.data),
             sum(sum(m) for m in store.mask.values())))
    app = LiveApp(e, src, calib_path=calib, win=(args.win_w, args.win_h))
    try:
        return app.run()
    finally:
        src.close()


def cmd_selftest(args) -> int:
    """Run the real decoder headless and print byte accuracy against the ROM.

    The point of this command is that every change to the decoder has to move a
    number.  It reports accuracy twice, because the calibration page is 71 %
    the single byte 0x77 and a decoder that always guessed 0x77 would score
    71 % while being useless.
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from kn7000dump.oracle import Oracle

    addr = int(args.address, 16)
    orc = Oracle(args.rom_dir) if args.rom_dir else Oracle()
    truth = None
    if not args.no_oracle:
        try:
            truth = orc.page(addr)
        except OSError as exc:
            print("no oracle available (%s) -- accuracy will not be measured" % exc)
    src = open_source(args.source, args.width, args.height, args.fps)
    frame = _first_frame(src)
    if frame is None:
        print("no frame from %s" % args.source)
        return 1
    import tempfile
    tmp = args.store or tempfile.mkdtemp(prefix="kn7000live-selftest-")
    store = DumpStore(tmp, lock_weight=args.lock_weight,
                      lock_frames=args.lock_frames, lock_share=args.lock_share)
    e, _ = _mkengine(args, frame, store)
    if args.seed_address is None and not args.any_address:
        e.seed_base = addr
    # A simulated source knows where the text really is.  Start from that, put
    # a deliberate placement error on it, and let tracking earn it back -- this
    # measures the decoder, not the corner-seeding heuristic, and it is the
    # situation right after an operator has dropped the corners roughly on.
    tq = getattr(src, "true_quad", None)
    if tq is not None and not args.calib:
        rng = np.random.default_rng(4242)
        q = G.Quad(np.asarray(tq, float) + rng.normal(0, args.sim_error, (4, 2)))
        e.reg = G.Registration(q, ncols=e.reg.ncols)

    t0 = time.time()
    engine_ms = 0.0
    for i in range(args.frames):
        f = src.read()
        if f is None:
            f = frame
        e.process(f)
        engine_ms += e.stats.ms
    dt = time.time() - t0

    base = store.page_of(addr)
    data, mask = store.page_state(base)
    nl = int(sum(mask))
    print("frames=%d  decoder %.1f ms/frame (wall %.1f)   ladder-usable=%d  voted=%d  torn=%d"
          % (args.frames, engine_ms / max(args.frames, 1), 1000 * dt / max(args.frames, 1),
             e.stats.read - e.stats.skipped_ladder, e.stats.voted, e.stats.torn))
    print("templates %d/16  separation %.3f" % (e.bank.coverage,
                                                e.bank.separation() if e.bank.ready else 0.0))
    print("locked %d/256 cells of page %08X   conflicts %d" % (nl, base, len(store.conflicts)))
    if truth is None:
        print("(no oracle -- accuracy not measurable for this address)")
        return 0
    rare = [i for i in range(256) if truth[i] != 0x77]
    okall = sum(1 for i in range(256) if mask[i] and data[i] == truth[i])
    okrare = sum(1 for i in rare if mask[i] and data[i] == truth[i])
    wrong = [i for i in range(256) if mask[i] and data[i] != truth[i]]
    print("correct among LOCKED: %d/%d (%.1f%%)   wrong: %d"
          % (okall, nl, 100.0 * okall / max(nl, 1), len(wrong)))
    print("coverage of all 256:      %.1f%%   of the %d non-0x77 cells: %.1f%%"
          % (100.0 * nl / 256, len(rare),
             100.0 * sum(1 for i in rare if mask[i]) / max(len(rare), 1)))
    print("correct over non-0x77:    %d/%d" % (okrare, sum(1 for i in rare if mask[i])))
    for i in wrong[:12]:
        print("   WRONG %08X: read %02X, truth %02X" % (base + i, data[i], truth[i]))
    store.close()
    return 0 if not wrong else 2


def cmd_report(args) -> int:
    store = DumpStore(args.store)
    print("store: %s" % store.path)
    tot = 0
    for name, got, size in store.coverage():
        tot += got
        pct = (100.0 * got / size) if size else 0.0
        print("  %-46s %10s / %-10s %6.3f%%" % (name, "{:,}".format(got),
                                                "{:,}".format(size) if size else "-", pct))
    print("  %-46s %10s" % ("total bytes locked", "{:,}".format(tot)))
    print("  %-46s %10d" % ("pages touched", len(store.data)))
    if store.conflicts:
        print("  %-46s %10d" % ("CONFLICTS (a locked byte was disputed)", len(store.conflicts)))
        for c in store.conflicts[-10:]:
            print("     %s: was %s, later read %s (weight %.1f over %d frames)"
                  % (c["a"], c["was"], c["now"], c["w"], c["frames"]))
    full = [p for p in sorted(store.data) if store.n_locked(p) == 256]
    print("  %-46s %10d" % ("pages complete (256/256)", len(full)))
    if args.pages:
        for p in sorted(store.data):
            print("    %08X  %3d/256" % (p, store.n_locked(p)))
    return 0


def cmd_export(args) -> int:
    store = DumpStore(args.store)
    if args.window in WINDOW_NAMES:
        lo, hi = WINDOW_NAMES[args.window]
    else:
        a, _, b = args.window.partition(":")
        lo, hi = int(a, 16), int(b, 16)
    got, n = store.export(lo, hi, args.out, fill=args.fill)
    print("wrote %s: %s of %s bytes known (%.3f%%); unknown filled with %02X"
          % (args.out, "{:,}".format(got), "{:,}".format(n), 100.0 * got / n, args.fill))
    print("wrote %s.mask: 1 = byte was actually read" % args.out)
    print("NOTE: this is a transcription of the instrument's own hex viewer, "
          "NOT a chip dump. Label it as such wherever it goes.")
    return 0


def cmd_rebuild(args) -> int:
    store = DumpStore(args.store)
    n = store.rebuild()
    store.snapshot(force=True)
    print("replayed %d journal records; %d pages, %d bytes"
          % (n, len(store.data), sum(sum(m) for m in store.mask.values())))
    return 0


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kn7000live", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, need_store=True):
        p.add_argument("--source", default="v4l2:/dev/video0")
        if need_store:
            p.add_argument("--store", required=True)
        else:
            p.add_argument("--store", default=None)
        p.add_argument("--calib")
        p.add_argument("--width", type=int, default=1280)
        p.add_argument("--height", type=int, default=720)
        p.add_argument("--fps", type=int, default=30)
        p.add_argument("--input-format")
        p.add_argument("--seed-address", help="the address you dialled, e.g. 48019000 -- "
                                              "makes the templates train 8x faster")
        p.add_argument("--any-address", action="store_true",
                       help="do not assume the page is 0x100-aligned (needs trained templates)")
        p.add_argument("--no-restrict", action="store_true",
                       help="accept addresses outside the instrument's known windows")
        p.add_argument("--fresh-templates", action="store_true")
        p.add_argument("--motion-gate", type=float, default=0.22)
        p.add_argument("--decay", type=float, default=0.0,
                       help="forget rate for the templates, e.g. 0.002 to follow a focus change")
        p.add_argument("--lock-weight", type=float, default=2.0)
        p.add_argument("--lock-frames", type=int, default=4)
        p.add_argument("--lock-share", type=float, default=0.85)

    p = sub.add_parser("live"); common(p)
    p.add_argument("--win-w", type=int, default=1500)
    p.add_argument("--win-h", type=int, default=860)
    p.set_defaults(func=cmd_live)

    p = sub.add_parser("devices"); p.set_defaults(func=cmd_devices)

    p = sub.add_parser("selftest"); common(p, need_store=False)
    p.add_argument("--address", required=True)
    p.add_argument("--frames", type=int, default=60)
    p.add_argument("--rom-dir")
    p.add_argument("--no-oracle", action="store_true")
    p.add_argument("--sim-error", type=float, default=6.0,
                   help="px of deliberate corner-placement error on a simulated source")
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser("report"); p.add_argument("--store", required=True)
    p.add_argument("--pages", action="store_true"); p.set_defaults(func=cmd_report)

    p = sub.add_parser("export"); p.add_argument("--store", required=True)
    p.add_argument("--window", required=True, help="table | program | sram | LO:HI in hex")
    p.add_argument("--out", required=True)
    p.add_argument("--fill", type=lambda s: int(s, 16), default=0xFF)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("rebuild"); p.add_argument("--store", required=True)
    p.set_defaults(func=cmd_rebuild)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
