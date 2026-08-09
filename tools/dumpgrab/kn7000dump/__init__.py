"""kn7000dump -- read a KN7000 MEMORY DUMP screen back into bytes.

Core single-image extractor for the "dump the ROM through the composite video
output" side quest.  Given one frame of the hidden MEMORY DUMP viewer it
returns the 8-hex-digit base address, the 16x16 bytes, and a per-cell
confidence for a downstream cross-frame voter.

Public API:
    PageExtractor(...).extract(image) -> PageResult
    fit_grid(image) -> Grid
    Atlas.load(path) / PageExtractor.build_atlas(samples)
"""
from .atlas import Atlas, AtlasBuilder, CLASSES          # noqa: F401
from .extract import (COLOR_NAMES, HIGHLIGHT_DEFAULT,    # noqa: F401
                      PageExtractor, PageResult)
from .geometry import Grid, RowFit, fit_grid, ink_map    # noqa: F401
from . import layout                                     # noqa: F401

__all__ = ["PageExtractor", "PageResult", "Atlas", "AtlasBuilder", "Grid",
           "RowFit", "fit_grid", "ink_map", "layout", "CLASSES",
           "COLOR_NAMES", "HIGHLIGHT_DEFAULT"]
__version__ = "0.1"
