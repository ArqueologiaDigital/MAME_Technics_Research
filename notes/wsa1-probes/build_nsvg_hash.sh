#!/bin/sh
# Build nsvg_hash against MAME's bundled nanosvg -- the SAME rasteriser the
# layout engine uses.  Header-only, so no MAME build is needed.
set -e
NANOSVG=${NANOSVG:-/home/fsanches/compartilhado/mame/3rdparty/nanosvg/src}
HERE=$(dirname "$0")
# MAME patches nanosvg.h to use C++ nullptr, so it must be built as C++.
c++ -O2 -x c++ -I"$NANOSVG" -o "$HERE/nsvg_hash" "$HERE/nsvg_hash.c" -lm
echo "built $HERE/nsvg_hash (nanosvg from $NANOSVG)"
