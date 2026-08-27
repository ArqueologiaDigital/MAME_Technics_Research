/* nsvg_hash -- rasterise an SVG with MAME's OWN nanosvg and hash the pixels.
 *
 * QUESTION IT ANSWERS: "do these two layout <element>s render identically?"
 * The MAME layout engine draws an <image><data> SVG through nanosvg, and only
 * through nanosvg -- librsvg/Inkscape agreement proves nothing about what the
 * user will see.  This reproduces src/emu/rendlay.cpp draw_svg() exactly:
 *
 *     m_svg = nsvgParse(data, "px", 72);                    // rendlay.cpp:2083
 *     xscale   = bounds.width()  / m_svg->width;            // rendlay.cpp:1767
 *     yscale   = bounds.height() / m_svg->height;
 *     drawscale = max(xscale, yscale);
 *     tempbitmap(int(m_svg->width * drawscale), int(m_svg->height * drawscale));
 *     nsvgRasterize(rast, svg, 0, 0, drawscale, pix, w, h, rowbytes);
 *
 * USAGE:   ./nsvg_hash <file.svg> [bounds_w bounds_h] [-dump out.raw]
 *          with no bounds, uses the SVG's own width/height (drawscale = 1).
 *          ./nsvg_hash -cmp <a.svg> <b.svg> <bounds_w> <bounds_h>
 *          A/B two SVGs at the same bounds and report HOW FAR APART they are.
 * OUTPUT:  "<fnv1a64-hex> <raster_w>x<raster_h> svgw=<w> svgh=<h>"
 *          -cmp: "ndiff=<pixels> of <total> maxdelta=<0..255> meandelta=<f>"
 *
 * WHY -cmp EXISTS: a hash is all-or-nothing, and two shapes lifted from the
 * same drawing differ by Inkscape duplication noise -- a gradient stop landing
 * a thousandth of a unit apart.  Deciding whether two controls may share one
 * element needs the MAGNITUDE of the disagreement, not just its existence.
 *
 * BUILD:   see build_nsvg_hash.sh beside this file.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NANOSVG_ALL_COLOR_KEYWORDS
#define NANOSVG_IMPLEMENTATION
#include "nanosvg.h"
#define NANOSVGRAST_IMPLEMENTATION
#include "nanosvgrast.h"

static unsigned long long fnv1a64(const unsigned char *p, size_t n)
{
	unsigned long long h = 1469598103934665603ULL;
	for (size_t i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ULL; }
	return h;
}

/* rasterise one file the way rendlay.cpp draw_svg() does; caller frees *out */
static int render(const char *path, double bw, double bh,
				  unsigned char **out, int *ow, int *oh)
{
	FILE *f = fopen(path, "rb");
	if (!f) { fprintf(stderr, "cannot open %s\n", path); return 2; }
	fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET);
	char *buf = (char *)malloc(len + 1);
	if (fread(buf, 1, len, f) != (size_t)len) { fprintf(stderr, "short read\n"); return 2; }
	buf[len] = 0;
	fclose(f);

	NSVGimage *img = nsvgParse(buf, "px", 72);
	if (!img) { fprintf(stderr, "parse failed: %s\n", path); free(buf); return 1; }
	if (img->width <= 0 || img->height <= 0) { fprintf(stderr, "empty: %s\n", path); return 1; }

	if (bw < 0) bw = img->width;
	if (bh < 0) bh = img->height;
	float xscale = (float)(bw / img->width);
	float yscale = (float)(bh / img->height);
	float drawscale = xscale > yscale ? xscale : yscale;
	int w = (int)(img->width * drawscale);
	int h = (int)(img->height * drawscale);
	if (w <= 0 || h <= 0) { fprintf(stderr, "degenerate raster\n"); return 1; }

	unsigned char *pix = (unsigned char *)calloc((size_t)w * h, 4);
	NSVGrasterizer *rast = nsvgCreateRasterizer();
	nsvgRasterize(rast, img, 0, 0, drawscale, pix, w, h, w * 4);
	nsvgDeleteRasterizer(rast);
	nsvgDelete(img);
	free(buf);
	*out = pix; *ow = w; *oh = h;
	return 0;
}

static int cmp_mode(int argc, char **argv)
{
	if (argc < 6) { fprintf(stderr, "usage: %s -cmp a.svg b.svg bw bh\n", argv[0]); return 2; }
	double bw = atof(argv[4]), bh = atof(argv[5]);
	unsigned char *pa, *pb; int aw, ah, bwid, bhei;
	int r = render(argv[2], bw, bh, &pa, &aw, &ah); if (r) return r;
	r = render(argv[3], bw, bh, &pb, &bwid, &bhei); if (r) return r;
	if (aw != bwid || ah != bhei) {
		printf("RASTER SIZE DIFFERS %dx%d vs %dx%d\n", aw, ah, bwid, bhei);
		return 1;
	}
	size_t n = (size_t)aw * ah;
	size_t ndiff = 0; int maxd = 0; double sum = 0;
	for (size_t i = 0; i < n; i++) {
		int worst = 0;
		for (int c = 0; c < 4; c++) {
			int d = (int)pa[i * 4 + c] - (int)pb[i * 4 + c];
			if (d < 0) d = -d;
			if (d > worst) worst = d;
		}
		if (worst) { ndiff++; sum += worst; if (worst > maxd) maxd = worst; }
	}
	printf("ndiff=%zu of %zu maxdelta=%d meandelta=%.4f\n",
		   ndiff, n, maxd, ndiff ? sum / (double)n : 0.0);
	free(pa); free(pb);
	return 0;
}

int main(int argc, char **argv)
{
	if (argc < 2) { fprintf(stderr, "usage: %s file.svg [bw bh] [-dump out.raw]\n", argv[0]); return 2; }
	if (!strcmp(argv[1], "-cmp")) return cmp_mode(argc, argv);

	const char *path = argv[1];
	double bw = -1, bh = -1;
	const char *dump = NULL;
	for (int i = 2; i < argc; i++) {
		if (!strcmp(argv[i], "-dump") && i + 1 < argc) { dump = argv[++i]; }
		else if (bw < 0) bw = atof(argv[i]);
		else if (bh < 0) bh = atof(argv[i]);
	}

	FILE *f = fopen(path, "rb");
	if (!f) { fprintf(stderr, "cannot open %s\n", path); return 2; }
	fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET);
	char *buf = (char *)malloc(len + 1);
	if (fread(buf, 1, len, f) != (size_t)len) { fprintf(stderr, "short read\n"); return 2; }
	buf[len] = 0;
	fclose(f);

	/* nsvgParse MUTATES its input, exactly as MAME lets it. */
	NSVGimage *img = nsvgParse(buf, "px", 72);
	if (!img) { fprintf(stderr, "parse failed: %s\n", path); return 1; }
	if (img->width <= 0 || img->height <= 0) { fprintf(stderr, "empty image: %s\n", path); return 1; }

	if (bw < 0) bw = img->width;
	if (bh < 0) bh = img->height;

	float xscale = (float)(bw / img->width);
	float yscale = (float)(bh / img->height);
	float drawscale = xscale > yscale ? xscale : yscale;

	int w = (int)(img->width * drawscale);
	int h = (int)(img->height * drawscale);
	if (w <= 0 || h <= 0) { fprintf(stderr, "degenerate raster\n"); return 1; }

	unsigned char *pix = (unsigned char *)calloc((size_t)w * h, 4);
	NSVGrasterizer *rast = nsvgCreateRasterizer();
	nsvgRasterize(rast, img, 0, 0, drawscale, pix, w, h, w * 4);

	printf("%016llx %dx%d svgw=%.6f svgh=%.6f\n",
		   fnv1a64(pix, (size_t)w * h * 4), w, h, img->width, img->height);

	if (dump) {
		FILE *o = fopen(dump, "wb");
		if (!o) { fprintf(stderr, "cannot write %s\n", dump); return 2; }
		fwrite(pix, 1, (size_t)w * h * 4, o);
		fclose(o);
	}

	nsvgDeleteRasterizer(rast);
	nsvgDelete(img);
	free(pix);
	free(buf);
	return 0;
}
