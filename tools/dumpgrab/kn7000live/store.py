"""What has been read, once and for all: the persistent evidence store.

A sweep of the KN7000's flash is 16,384 pages of 256 bytes, spread over as many
sessions as it takes.  The store is what makes that additive: it is keyed by
absolute CPU address, it survives restarts, and a byte that has once been read
cleanly is never read again.

The commitment rule is deliberately conservative, because the failure this tool
must not have is a plausible-looking wrong byte.  A value is *locked* only when

  * several independent frames agree on it,
  * the agreement is near-unanimous among the frames that had an opinion, and
  * each of those opinions cleared the template-match margin on its own.

Frames are counted, not just observations, because thirty consecutive readings
of one badly-focused frame are one piece of evidence, not thirty.

Once locked, a cell stops being cut, matched and voted on -- that is what lets
a nearly-finished page run at full frame rate and concentrate on the few cells
that are still illegible.  A locked cell is not, however, beyond question: an
audit re-reads locked cells at a slow round-robin, and a locked value that
accumulates real evidence for a *different* value is recorded as a conflict
rather than silently overwritten.  Conflicts are surfaced, counted, and left
for a human, because silently preferring either the old or the new answer is
how a dump acquires bytes nobody can account for.

On disk:

    store/meta.json       what this store is, and the rules it was written under
    store/journal.jsonl   append-only: every lock and every conflict, in order
    store/snapshot.npz    the same thing rolled up, for fast loading
    store/bank.npz        the trained glyph templates (see recog.GlyphBank)
    store/calib.json      the last registration, so a session resumes aimed

The journal is the record of truth and the snapshot is a cache: `rebuild()`
reconstructs one from the other, so an interrupted write costs nothing.
"""
from __future__ import annotations

import json
import os
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

# The address windows this instrument actually has, used to reject a misread
# address before it can file bytes in a place that does not exist.
WINDOWS = [
    (0x48000000, 0x48400000, "table flash (IC16/IC17 low half)"),
    (0x48400000, 0x48800000, "program flash (IC16/IC17 high half)"),
    (0x84000000, 0x85000000, "battery-backed SRAM IC23 (ram44 window)"),
]


@dataclass
class _Votes:
    tally: Dict[int, float] = field(default_factory=dict)
    frames: Dict[int, set] = field(default_factory=dict)

    def add(self, value: int, weight: float, frame_id: int) -> None:
        self.tally[value] = self.tally.get(value, 0.0) + weight
        self.frames.setdefault(value, set()).add(frame_id)

    def best(self) -> Tuple[Optional[int], float, float, int]:
        if not self.tally:
            return None, 0.0, 0.0, 0
        v = max(self.tally, key=lambda k: self.tally[k])
        tot = sum(self.tally.values())
        return v, self.tally[v], (self.tally[v] / tot if tot else 0.0), len(self.frames[v])


class DumpStore:
    def __init__(self, path: str,
                 lock_weight: float = 2.0,
                 lock_frames: int = 4,
                 lock_share: float = 0.85,
                 max_live_pages: int = 96):
        self.path = path
        self.lock_weight = lock_weight
        self.lock_frames = lock_frames
        self.lock_share = lock_share
        self.max_live_pages = max_live_pages

        self.data: Dict[int, bytearray] = {}
        self.mask: Dict[int, bytearray] = {}
        self._votes: "OrderedDict[int, Dict[int, _Votes]]" = OrderedDict()
        self.conflicts: List[dict] = []
        self._journal = None
        self._dirty = 0
        self._last_snapshot = 0.0

        os.makedirs(path, exist_ok=True)
        meta = os.path.join(path, "meta.json")
        if not os.path.exists(meta):
            with open(meta, "w") as fh:
                json.dump({"tool": "kn7000live", "format": 1,
                           "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "rules": {"lock_weight": lock_weight,
                                     "lock_frames": lock_frames,
                                     "lock_share": lock_share},
                           "note": "NOT a chip dump: bytes transcribed from the "
                                   "instrument's own MEMORY DUMP screen."}, fh, indent=1)
        self.load()

    # -- persistence -------------------------------------------------------- #
    def load(self) -> None:
        snap = os.path.join(self.path, "snapshot.npz")
        if os.path.exists(snap):
            z = np.load(snap)
            for a, d, m in zip(z["addrs"], z["data"], z["mask"]):
                self.data[int(a)] = bytearray(d.tobytes())
                self.mask[int(a)] = bytearray(m.tobytes())
        self._replay_journal(after=self._snapshot_pos())

    def _snapshot_pos(self) -> int:
        p = os.path.join(self.path, "snapshot.pos")
        try:
            with open(p) as fh:
                return int(fh.read().strip())
        except Exception:
            return 0

    def _replay_journal(self, after: int = 0) -> int:
        jp = os.path.join(self.path, "journal.jsonl")
        if not os.path.exists(jp):
            return 0
        n = 0
        with open(jp) as fh:
            fh.seek(after)
            for line in fh:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("t") != "lock":
                    if rec.get("t") == "conflict":
                        self.conflicts.append(rec)
                    continue
                addr = int(rec["a"], 16)
                blob = bytes.fromhex(rec["d"])
                for i, b in enumerate(blob):
                    self._set(addr + i, b)
                n += 1
        return n

    def rebuild(self) -> int:
        """Discard the snapshot and replay the whole journal."""
        self.data.clear(); self.mask.clear(); self.conflicts.clear()
        return self._replay_journal(after=0)

    def _open_journal(self):
        if self._journal is None:
            self._journal = open(os.path.join(self.path, "journal.jsonl"), "a")
        return self._journal

    def snapshot(self, force: bool = False) -> bool:
        now = time.time()
        if not force and (self._dirty == 0 or now - self._last_snapshot < 10.0):
            return False
        addrs = sorted(self.data)
        if addrs:
            np.savez_compressed(
                os.path.join(self.path, "snapshot.tmp.npz"),
                addrs=np.array(addrs, np.uint32),
                data=np.stack([np.frombuffer(bytes(self.data[a]), np.uint8) for a in addrs]),
                mask=np.stack([np.frombuffer(bytes(self.mask[a]), np.uint8) for a in addrs]))
            os.replace(os.path.join(self.path, "snapshot.tmp.npz"),
                       os.path.join(self.path, "snapshot.npz"))
        if self._journal is not None:
            self._journal.flush()
            os.fsync(self._journal.fileno())
        jp = os.path.join(self.path, "journal.jsonl")
        pos = os.path.getsize(jp) if os.path.exists(jp) else 0
        with open(os.path.join(self.path, "snapshot.pos"), "w") as fh:
            fh.write(str(pos))
        self._dirty = 0
        self._last_snapshot = now
        return True

    def close(self) -> None:
        self.snapshot(force=True)
        if self._journal is not None:
            self._journal.close()
            self._journal = None

    # -- access ------------------------------------------------------------- #
    @staticmethod
    def page_of(addr: int) -> int:
        return addr & 0xFFFFFF00

    def _set(self, addr: int, value: int) -> None:
        p = self.page_of(addr)
        if p not in self.data:
            self.data[p] = bytearray(256)
            self.mask[p] = bytearray(256)
        self.data[p][addr & 0xFF] = value
        self.mask[p][addr & 0xFF] = 1

    def is_locked(self, addr: int) -> bool:
        m = self.mask.get(self.page_of(addr))
        return bool(m and m[addr & 0xFF])

    def get(self, addr: int) -> Optional[int]:
        p = self.page_of(addr)
        if p in self.mask and self.mask[p][addr & 0xFF]:
            return self.data[p][addr & 0xFF]
        return None

    def page_state(self, base: int) -> Tuple[bytearray, bytearray]:
        return (self.data.get(base, bytearray(256)), self.mask.get(base, bytearray(256)))

    def unlocked_indices(self, base: int) -> List[int]:
        m = self.mask.get(base)
        if m is None:
            return list(range(256))
        return [i for i in range(256) if not m[i]]

    def n_locked(self, base: int) -> int:
        m = self.mask.get(base)
        return int(sum(m)) if m else 0

    # -- evidence ----------------------------------------------------------- #
    def _page_votes(self, base: int) -> Dict[int, _Votes]:
        v = self._votes.get(base)
        if v is None:
            v = {}
            self._votes[base] = v
            while len(self._votes) > self.max_live_pages:
                self._votes.popitem(last=False)
        else:
            self._votes.move_to_end(base)
        return v

    def observe(self, addr: int, value: int, weight: float, frame_id: int) -> Optional[str]:
        """Record one opinion.  Returns "lock", "conflict" or None."""
        base = self.page_of(addr)
        cur = self.get(addr)
        pv = self._page_votes(base)
        key = addr & 0xFF
        vt = pv.get(key)
        if vt is None:
            vt = _Votes()
            pv[key] = vt
        vt.add(value, weight, frame_id)
        best, w, share, nframes = vt.best()
        if best is None:
            return None
        if w < self.lock_weight or nframes < self.lock_frames or share < self.lock_share:
            return None
        if cur is None:
            self._set(addr, best)
            pv.pop(key, None)
            self._dirty += 1
            return "lock"
        if best != cur:
            rec = {"t": "conflict", "ts": round(time.time(), 3), "a": "%08X" % addr,
                   "was": "%02X" % cur, "now": "%02X" % best,
                   "w": round(w, 2), "frames": nframes}
            self.conflicts.append(rec)
            fh = self._open_journal()
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            pv.pop(key, None)
            return "conflict"
        pv.pop(key, None)
        return None

    def commit_row(self, addr: int, values: List[int]) -> None:
        """Journal a run of freshly locked bytes (called after observe locks them)."""
        rec = {"t": "lock", "ts": round(time.time(), 3), "a": "%08X" % addr,
               "d": bytes(values).hex()}
        fh = self._open_journal()
        fh.write(json.dumps(rec) + "\n")
        fh.flush()

    def forget_page(self, base: int) -> int:
        """Drop everything known about one page -- for a page read under a bad
        registration.  Journalled so the history stays honest."""
        n = self.n_locked(base)
        self.data.pop(base, None)
        self.mask.pop(base, None)
        self._votes.pop(base, None)
        fh = self._open_journal()
        fh.write(json.dumps({"t": "forget", "ts": round(time.time(), 3),
                             "a": "%08X" % base, "n": n}) + "\n")
        fh.flush()
        self._dirty += 1
        return n

    # -- reporting ---------------------------------------------------------- #
    def coverage(self) -> List[Tuple[str, int, int]]:
        out = []
        for lo, hi, name in WINDOWS:
            got = sum(self.n_locked(p) for p in self.data if lo <= p < hi)
            out.append((name, got, hi - lo))
        other = sum(self.n_locked(p) for p in self.data
                    if not any(lo <= p < hi for lo, hi, _ in WINDOWS))
        if other:
            out.append(("outside the known windows", other, 0))
        return out

    def export(self, lo: int, hi: int, out_bin: str, fill: int = 0xFF) -> Tuple[int, int]:
        """Write the window as a binary with `fill` for unknown, plus a .mask."""
        n = hi - lo
        buf = bytearray([fill]) * n
        msk = bytearray(n)
        got = 0
        for p, m in self.mask.items():
            if not (lo <= p < hi):
                continue
            d = self.data[p]
            for i in range(256):
                if m[i]:
                    buf[p - lo + i] = d[i]
                    msk[p - lo + i] = 1
                    got += 1
        with open(out_bin, "wb") as fh:
            fh.write(buf)
        with open(out_bin + ".mask", "wb") as fh:
            fh.write(msk)
        return got, n
