"""Frame sources: video file, directory of stills, and (for later) a live V4L2 device.

Dependencies: numpy + Pillow for the directory source; the ``ffmpeg``/``ffprobe``
binaries for the video and V4L2 sources.  OpenCV is deliberately NOT required -- it is
not installed on this machine, and piping rawvideo out of ffmpeg is both portable and
exactly how a capture card will be read anyway.

Every source yields ``(frame_index, rgb_uint8_HxWx3)`` and is a plain iterator, so the
pipeline is streaming: memory use does not grow with video length.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Iterator, Optional, Sequence, Tuple

import numpy as np

FrameTuple = Tuple[int, np.ndarray]

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".ppm", ".tif", ".tiff")


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


@dataclass
class SourceMeta:
    kind: str
    name: str
    width: int = 0
    height: int = 0
    fps: float = 0.0
    n_frames: Optional[int] = None


class FrameSource:
    meta: SourceMeta

    def __iter__(self) -> Iterator[FrameTuple]:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class DirectoryFrameSource(FrameSource):
    """A directory (or explicit list) of still images, in natural sort order."""

    def __init__(self, path: str, limit: Optional[int] = None, stride: int = 1):
        from PIL import Image  # local import so the video path needs no Pillow

        self._Image = Image
        if os.path.isdir(path):
            names = [n for n in os.listdir(path) if n.lower().endswith(IMAGE_EXTS)]
            names.sort(key=_natural_key)
            self.files = [os.path.join(path, n) for n in names]
        else:
            self.files = [path]
        self.files = self.files[::stride]
        if limit:
            self.files = self.files[:limit]
        w = h = 0
        if self.files:
            with Image.open(self.files[0]) as im:
                w, h = im.size
        self.meta = SourceMeta("directory", path, w, h, 0.0, len(self.files))

    def __iter__(self) -> Iterator[FrameTuple]:
        for i, f in enumerate(self.files):
            with self._Image.open(f) as im:
                yield i, np.asarray(im.convert("RGB"), dtype=np.uint8)


def _ffprobe(path: str) -> dict:
    if not shutil.which("ffprobe"):
        return {}
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
             "-of", "json", path],
            capture_output=True, text=True, timeout=60, check=False,
        ).stdout
        js = json.loads(out or "{}")
        return (js.get("streams") or [{}])[0]
    except Exception:
        return {}


class VideoFrameSource(FrameSource):
    """Decode a video file to RGB frames through an ffmpeg pipe."""

    def __init__(self, path: str, limit: Optional[int] = None, stride: int = 1,
                 size: Optional[Tuple[int, int]] = None):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found on PATH; needed to read video files")
        st = _ffprobe(path)
        w = size[0] if size else int(st.get("width") or 0)
        h = size[1] if size else int(st.get("height") or 0)
        if not (w and h):
            raise RuntimeError(f"cannot determine frame size of {path}; pass size=(w,h)")
        fps = 0.0
        rate = st.get("avg_frame_rate") or st.get("r_frame_rate") or "0/0"
        try:
            num, den = rate.split("/")
            fps = float(num) / float(den) if float(den) else 0.0
        except Exception:
            fps = 0.0
        n = None
        try:
            n = int(st.get("nb_frames")) if st.get("nb_frames") else None
        except Exception:
            n = None
        self.path, self.w, self.h = path, w, h
        self.limit, self.stride = limit, max(1, stride)
        self.meta = SourceMeta("video", path, w, h, fps, n)
        self._proc: Optional[subprocess.Popen] = None

    def __iter__(self) -> Iterator[FrameTuple]:
        cmd = ["ffmpeg", "-v", "error", "-i", self.path,
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                      bufsize=self.w * self.h * 3)
        nbytes = self.w * self.h * 3
        i = 0
        emitted = 0
        try:
            while True:
                buf = self._proc.stdout.read(nbytes)
                if not buf or len(buf) < nbytes:
                    break
                if i % self.stride == 0:
                    yield i, np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)
                    emitted += 1
                    if self.limit and emitted >= self.limit:
                        break
                i += 1
        finally:
            self.close()

    def close(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.stdout:
                    self._proc.stdout.close()
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                pass
            self._proc = None


class V4L2FrameSource(FrameSource):
    """Live capture from a V4L2 device (e.g. a USB composite grabber).

    NOT EXERCISED HERE -- there is no capture hardware on this machine yet.  It exists so
    that the pipeline's source abstraction is demonstrably sufficient for live work: it
    is the same rawvideo pipe as VideoFrameSource with a different ffmpeg input spec.
    """

    def __init__(self, device: str = "/dev/video0", size: Tuple[int, int] = (720, 576),
                 fps: float = 25.0, input_format: Optional[str] = None,
                 limit: Optional[int] = None):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found on PATH; needed for V4L2 capture")
        self.device, self.w, self.h, self.fps = device, size[0], size[1], fps
        self.input_format = input_format
        self.limit = limit
        self.meta = SourceMeta("v4l2", device, size[0], size[1], fps, None)
        self._proc: Optional[subprocess.Popen] = None

    def __iter__(self) -> Iterator[FrameTuple]:
        cmd = ["ffmpeg", "-v", "error", "-f", "v4l2"]
        if self.input_format:
            cmd += ["-input_format", self.input_format]
        cmd += ["-framerate", str(self.fps), "-video_size", f"{self.w}x{self.h}",
                "-i", self.device, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                      bufsize=self.w * self.h * 3)
        nbytes = self.w * self.h * 3
        i = 0
        try:
            while True:
                buf = self._proc.stdout.read(nbytes)
                if not buf or len(buf) < nbytes:
                    break
                yield i, np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)
                i += 1
                if self.limit and i >= self.limit:
                    break
        finally:
            self.close()

    close = VideoFrameSource.close


def open_source(spec: str, limit: Optional[int] = None, stride: int = 1,
                size: Optional[Tuple[int, int]] = None) -> FrameSource:
    """Open whatever ``spec`` names: a directory, an image, a video file, or /dev/videoN."""
    if spec.startswith("/dev/video"):
        return V4L2FrameSource(spec, size=size or (720, 576), limit=limit)
    if os.path.isdir(spec):
        return DirectoryFrameSource(spec, limit=limit, stride=stride)
    if spec.lower().endswith(IMAGE_EXTS):
        return DirectoryFrameSource(spec, limit=limit, stride=stride)
    return VideoFrameSource(spec, limit=limit, stride=stride, size=size)
