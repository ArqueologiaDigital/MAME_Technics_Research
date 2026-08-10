"""kn7000blur -- degraded-domain decoder for the KN7000 MEMORY DUMP screen.

The sharp-glyph atlas in ``kn7000dump`` refuses composite-video captures.  This
package matches in the *blurred* domain instead: exact 5x7 font templates are
pushed through a point-spread function measured from the frame itself, and a
whole 76-character row is fitted jointly so that the bleed between neighbouring
characters becomes evidence rather than noise.

Modules
-------
layout    the screen's character layout and the 18-glyph hex font
model     forward model: native bitmap -> observed pixels (resample + PSF)
geom      geometry fit (affine native->real, from the frame's own structure)
psf       PSF estimation from the address column (labelled, every frame)
rowdp     joint row decoding: Viterbi + forward-backward posteriors
decode    end-to-end single-frame decode with self-checks
score     scoring against a reference page
"""
