"""Drawing the answer on top of the picture.

The overlay is not decoration -- it is the instrument's feedback loop.  The
operator is holding a camera in front of a small screen and has to decide,
continuously, whether what they are doing is helping.  So everything drawn here
answers one of exactly three questions:

    Is the grid on the text?          the quad, its corner handles, the cell
                                      outlines, and the address column picked
                                      out separately because it is the one part
                                      whose correct content is known in advance
    Which bytes are done?             green locked, amber accumulating, red
                                      unknown, magenta disputed -- a page is
                                      finished when the whole block is green
    Is the picture good enough?       the margin and separation numbers, which
                                      are the two quantities that actually
                                      decide whether a cell will ever lock

Colour is used for state and nothing else, and the state comes from the store,
so what is green on screen is exactly what has been committed to disk.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from . import geom as G

try:
    import pygame
except Exception:                                            # pragma: no cover
    pygame = None

COL_BG = (18, 18, 22)
COL_PANEL = (28, 28, 34)
COL_TEXT = (215, 215, 220)
COL_DIM = (130, 130, 140)
COL_LOCKED = (60, 200, 90)
COL_PARTIAL = (235, 190, 60)
COL_UNKNOWN = (215, 70, 70)
COL_CONFLICT = (235, 90, 220)
COL_ADDR = (90, 165, 245)
COL_QUAD = (120, 220, 255)
COL_WARN = (250, 150, 60)


class Renderer:
    def __init__(self, win_w: int = 1500, win_h: int = 860, title: str = "kn7000live"):
        if pygame is None:
            raise RuntimeError("pygame is required for the live view "
                               "(the headless subcommands do not need it)")
        pygame.init()
        pygame.display.set_caption(title)
        self.screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
        self.f_small = pygame.font.Font(None, 19)
        self.f_mono = pygame.font.Font(None, 21)
        self.f_big = pygame.font.Font(None, 28)
        self._byte_cache: Dict[Tuple[str, Tuple[int, int, int]], "pygame.Surface"] = {}
        self._frame_surf = None
        self._frame_shape = None

    # -- helpers ------------------------------------------------------------ #
    def _byte_surf(self, txt: str, col) -> "pygame.Surface":
        key = (txt, col)
        s = self._byte_cache.get(key)
        if s is None:
            if len(self._byte_cache) > 4096:
                self._byte_cache.clear()
            s = self.f_mono.render(txt, True, col)
            self._byte_cache[key] = s
        return s

    def blit_frame(self, frame: np.ndarray, rect) -> Tuple[float, Tuple[int, int]]:
        """Draw the camera frame letterboxed into `rect`; return (scale, origin)."""
        h, w = frame.shape[:2]
        if self._frame_shape != (w, h):
            self._frame_surf = pygame.Surface((w, h))
            self._frame_shape = (w, h)
        pygame.surfarray.blit_array(self._frame_surf, np.transpose(frame, (1, 0, 2)))
        s = min(rect[2] / w, rect[3] / h)
        dw, dh = int(w * s), int(h * s)
        ox, oy = rect[0] + (rect[2] - dw) // 2, rect[1] + (rect[3] - dh) // 2
        self.screen.blit(pygame.transform.smoothscale(self._frame_surf, (dw, dh)), (ox, oy))
        return s, (ox, oy)

    @staticmethod
    def to_window(pts: np.ndarray, scale: float, origin: Tuple[int, int]) -> np.ndarray:
        return pts * scale + np.array(origin, float)

    @staticmethod
    def to_frame(x: float, y: float, scale: float, origin: Tuple[int, int]) -> Tuple[float, float]:
        return ((x - origin[0]) / scale, (y - origin[1]) / scale)

    # -- the grid ----------------------------------------------------------- #
    def draw_grid(self, reg: G.Registration, mask: bytes, votes: Dict[int, float],
                  conflicts: set, scale: float, origin: Tuple[int, int],
                  selected: Optional[int], show_cells: bool = True) -> None:
        H = reg.quad.H
        # cell corner coordinates for the whole 16x16 byte block, in one go
        if show_cells:
            u0 = np.array([G.BYTE_COLS[k][0] for k in range(16)], float) / reg.ncols
            u1 = np.array([G.BYTE_COLS[k][1] + 1 for k in range(16)], float) / reg.ncols
            v0 = np.arange(16, dtype=float) / G.NROW
            v1 = (np.arange(16, dtype=float) + 1) / G.NROW
            for r in range(16):
                for k in range(16):
                    i = r * 16 + k
                    if i in conflicts:
                        col = COL_CONFLICT
                    elif mask and mask[i]:
                        col = COL_LOCKED
                    elif votes.get(i, 0.0) > 0:
                        col = COL_PARTIAL
                    else:
                        col = COL_UNKNOWN
                    uu = np.array([u0[k], u1[k], u1[k], u0[k]])
                    vv = np.array([v0[r], v0[r], v1[r], v1[r]])
                    x, y = G.apply_h(H, uu, vv)
                    p = self.to_window(np.stack([x, y], 1), scale, origin)
                    pygame.draw.polygon(self.screen, col, [tuple(q) for q in p], 1)
            # the address column, whose content is self-checking
            uu = np.array([0.0, 8.0 / reg.ncols, 8.0 / reg.ncols, 0.0])
            for r in range(16):
                vv = np.array([v0[r], v0[r], v1[r], v1[r]])
                x, y = G.apply_h(H, uu, vv)
                p = self.to_window(np.stack([x, y], 1), scale, origin)
                pygame.draw.polygon(self.screen, COL_ADDR, [tuple(q) for q in p], 1)

        p = self.to_window(reg.quad.corners, scale, origin)
        pygame.draw.polygon(self.screen, COL_QUAD, [tuple(q) for q in p], 2)
        for i, q in enumerate(p):
            col = (255, 255, 255) if selected == i else COL_QUAD
            pygame.draw.circle(self.screen, col, (int(q[0]), int(q[1])), 7, 0 if selected == i else 2)
            self.screen.blit(self.f_small.render("1234"[i], True, (0, 0, 0) if selected == i else col),
                             (q[0] + 9, q[1] - 8))

    # -- the page ----------------------------------------------------------- #
    def draw_page(self, rect, base: Optional[int], data: bytes, mask: bytes,
                  votes: Dict[int, float], conflicts: set) -> None:
        x0, y0, w, h = rect
        pygame.draw.rect(self.screen, COL_PANEL, rect)
        t = "page %08X" % base if base is not None else "page ????????"
        self.screen.blit(self.f_big.render(t, True, COL_TEXT), (x0 + 8, y0 + 6))
        cw, ch = 25, 22
        oy = y0 + 38
        for r in range(16):
            self.screen.blit(self.f_small.render(
                ("%08X" % (base + 16 * r)) if base is not None else "  +%02X" % (16 * r),
                True, COL_DIM), (x0 + 6, oy + r * ch + 3))
        ox = x0 + 78
        for r in range(16):
            for k in range(16):
                i = r * 16 + k
                if i in conflicts:
                    col, txt = COL_CONFLICT, "%02X" % data[i]
                elif mask and mask[i]:
                    col, txt = COL_LOCKED, "%02X" % data[i]
                elif votes.get(i, 0.0) > 0:
                    col, txt = COL_PARTIAL, ".."
                else:
                    col, txt = COL_UNKNOWN, "--"
                self.screen.blit(self._byte_surf(txt, col), (ox + k * cw, oy + r * ch))

    # -- the numbers -------------------------------------------------------- #
    def draw_hud(self, rect, lines: List[Tuple[str, str, tuple]]) -> None:
        x0, y0, w, h = rect
        pygame.draw.rect(self.screen, COL_PANEL, rect)
        y = y0 + 6
        for label, value, col in lines:
            if label == "":
                y += 8
                continue
            self.screen.blit(self.f_small.render(label, True, COL_DIM), (x0 + 8, y))
            self.screen.blit(self.f_small.render(value, True, col), (x0 + 150, y))
            y += 20

    def bar(self, rect, frac: float, col) -> None:
        x0, y0, w, h = rect
        pygame.draw.rect(self.screen, (55, 55, 62), rect)
        pygame.draw.rect(self.screen, col, (x0, y0, int(w * max(0.0, min(1.0, frac))), h))
