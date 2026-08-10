"""Frames in, newest first.

Capture goes through ffmpeg rather than a binding, for two reasons: it is
already on the machine, and it speaks v4l2, every USB capture stick, and every
file format without any of them needing a Python package.  The frames arrive as
raw rgb24 on a pipe, which is the one format that cannot be silently re-encoded
on the way in -- and re-encoding matters here: voting on H.264-medium plateaus
at 97.7 % byte accuracy where the same pipeline on uncompressed reaches 99.8 %.

The reader thread keeps only the most recent frame.  A live tool that queues
frames ends up decoding the past: if a decode takes 80 ms the operator's hand
movement is already three frames old by the time the overlay is drawn, and the
overlay is the whole point.  Dropping is correct.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import threading
import time
from typing import Optional, Tuple

import numpy as np


class FrameSource:
    """Common interface: `.read()` returns the newest frame or None."""

    size: Tuple[int, int] = (0, 0)
    name: str = "?"

    def read(self) -> Optional[np.ndarray]:
        raise NotImplementedError

    def close(self) -> None:
        pass

    @property
    def dropped(self) -> int:
        return 0


class FFmpegSource(FrameSource):
    def __init__(self, args: list, width: int, height: int, name: str):
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found on PATH -- it is how frames are captured")
        self.size = (width, height)
        self.name = name
        self._n = width * height * 3
        self._proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, bufsize=0)
        self._latest: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop = False
        self._dropped = 0
        self._seen = 0
        self._err = b""
        self._t = threading.Thread(target=self._pump, daemon=True)
        self._t.start()
        self._te = threading.Thread(target=self._drain_err, daemon=True)
        self._te.start()

    def _drain_err(self):
        try:
            for line in self._proc.stderr:
                self._err = (self._err + line)[-4000:]
        except Exception:
            pass

    def _pump(self):
        buf = bytearray()
        stdout = self._proc.stdout
        while not self._stop:
            chunk = stdout.read(self._n - len(buf)) if stdout else b""
            if not chunk:
                break
            buf += chunk
            if len(buf) == self._n:
                a = np.frombuffer(bytes(buf), np.uint8).reshape(self.size[1], self.size[0], 3)
                with self._lock:
                    if self._latest is not None:
                        self._dropped += 1
                    self._latest = a
                    self._seen += 1
                buf = bytearray()

    def read(self) -> Optional[np.ndarray]:
        with self._lock:
            f, self._latest = self._latest, None
        return f

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None

    @property
    def error(self) -> str:
        return self._err.decode("utf-8", "replace").strip()

    def close(self) -> None:
        self._stop = True
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass


class StillSource(FrameSource):
    """One image, or a directory of them, replayed on a loop.

    This is how the whole pipeline is tested and scored without a camera --
    including the self-test against the one page whose 256 bytes are known.
    """

    def __init__(self, paths, fps: float = 10.0, loop: bool = True):
        from PIL import Image
        self._Image = Image
        self.paths = list(paths)
        if not self.paths:
            raise RuntimeError("no images matched")
        self.fps = fps
        self.loop = loop
        self.i = 0
        self._t = 0.0
        first = np.asarray(Image.open(self.paths[0]).convert("RGB"))
        self.size = (first.shape[1], first.shape[0])
        self.name = "%d image(s)" % len(self.paths)
        self._cache = {0: first}

    def read(self) -> Optional[np.ndarray]:
        now = time.time()
        if now - self._t < 1.0 / max(self.fps, 0.01):
            return None
        self._t = now
        if self.i >= len(self.paths):
            if not self.loop:
                return None
            self.i = 0
        k = self.i
        self.i += 1
        if k not in self._cache:
            if len(self._cache) > 8:
                self._cache.clear()
            self._cache[k] = np.asarray(self._Image.open(self.paths[k]).convert("RGB"))
        return self._cache[k]

    @property
    def alive(self) -> bool:
        return True

    @property
    def error(self) -> str:
        return ""


def open_source(spec: str, width: int = 1280, height: int = 720,
                fps: int = 30, input_format: Optional[str] = None) -> FrameSource:
    """Open a source from a spec string.

        v4l2:/dev/video0     a camera or USB capture stick
        file:clip.mkv        a recording (decoded as fast as it is consumed)
        dir:frames/          every image in a directory, on a loop
        image:frame.png      one image, on a loop
        anything else        treated as a path: image, directory or video
    """
    kind, _, rest = spec.partition(":")
    if not rest:
        kind, rest = ("", spec)

    if kind == "sim":
        from .simulate import parse_sim_spec
        return parse_sim_spec(spec, width=width, height=height)

    if kind == "v4l2" or (kind == "" and rest.startswith("/dev/video")):
        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "v4l2",
                "-framerate", str(fps), "-video_size", "%dx%d" % (width, height)]
        if input_format:
            args += ["-input_format", input_format]
        args += ["-i", rest, "-an", "-vf", "scale=%d:%d" % (width, height),
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        return FFmpegSource(args, width, height, "v4l2 %s" % rest)

    if kind == "dir" or (kind == "" and os.path.isdir(rest)):
        pats = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.ppm")
        files = sorted(f for p in pats for f in glob.glob(os.path.join(rest, p)))
        return StillSource(files)

    if kind == "image":
        return StillSource(sorted(glob.glob(rest)) or [rest])

    ext = os.path.splitext(rest)[1].lower()
    if kind == "file" or ext in (".mkv", ".mp4", ".avi", ".mov", ".ts", ".y4m"):
        w, h = probe_size(rest, (width, height))
        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-re", "-i", rest,
                "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        return FFmpegSource(args, w, h, os.path.basename(rest))

    return StillSource(sorted(glob.glob(rest)) or [rest])


def probe_size(path: str, default: Tuple[int, int]) -> Tuple[int, int]:
    if shutil.which("ffprobe") is None:
        return default
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", path],
            capture_output=True, text=True, timeout=10).stdout.strip()
        w, h = out.split("x")[:2]
        return int(w), int(h)
    except Exception:
        return default


def list_v4l2_devices() -> list:
    """Every /dev/video* that ffmpeg can actually open, with its formats."""
    devs = sorted(glob.glob("/dev/video*"))
    out = []
    for d in devs:
        try:
            r = subprocess.run(["ffmpeg", "-hide_banner", "-f", "v4l2",
                                "-list_formats", "all", "-i", d],
                               capture_output=True, text=True, timeout=6)
            txt = (r.stderr or "") + (r.stdout or "")
            lines = [l.split("] ", 1)[-1] for l in txt.splitlines() if "Raw" in l or "Compressed" in l]
            out.append((d, lines))
        except Exception as e:
            out.append((d, ["<%s>" % e]))
    return out
