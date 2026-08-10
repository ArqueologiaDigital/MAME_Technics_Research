"""kn7000live -- read the KN7000 MEMORY DUMP screen from a live camera feed.

This is the interactive sibling of `kn7000dump`.  Where that one decodes a
single already-good frame, this one is pointed at the instrument's screen by a
human, in real time, and is built around three facts that a batch tool cannot
exploit:

  1. **The operator can improve the picture.**  Focus, distance, angle, glare
     and exposure are all adjustable *while the tool is running*, so the tool's
     first job is to put an honest number on how legible the frame is and show
     where it is failing.  Every measurement in the HUD exists to be optimised
     by moving the camera.

  2. **A byte only has to be read once.**  The screen is static between button
     presses, so the same cell is re-measured 30 times a second.  A byte is
     committed only when several independent frames agree; after that it is
     *locked* and never re-read, and the effort goes to the cells that are
     still illegible.  A page is finished when every cell is green.

  3. **Every row states its own address.**  Attribution is per row, not per
     frame, so changing page loses nothing, a torn repaint (the firmware's is
     not atomic) contributes both of its halves to the right places, and a
     whole-ROM sweep is just "keep pressing page-advance until the coverage
     bar stops moving".

Everything committed goes to a persistent store keyed by absolute CPU address,
so a sweep can be done over many sessions and the result accumulates.

    python3 -m kn7000live live --source v4l2:/dev/video0 --store ~/kn7000-dump

Design rule inherited from this side quest: **the tool never invents a byte.**
Anything it is not sure of stays unknown and stays visibly red.
"""
from .geom import Quad, Registration, NCOL_HEX, NROW, auto_seed          # noqa: F401
from .recog import GlyphBank, FrameReading, PageReader                   # noqa: F401
from .store import DumpStore, WINDOWS                                    # noqa: F401

__all__ = ["Quad", "Registration", "auto_seed", "NCOL_HEX", "NROW",
           "GlyphBank", "FrameReading", "PageReader", "DumpStore", "WINDOWS"]
__version__ = "1.0"
