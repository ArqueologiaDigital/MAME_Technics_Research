# KN7000 table ROM (0x48000000) — resource archive structure

The 4 MB table ROM (`kn7000_table.rom`, mapped at `0x48000000`; IC/mask ROM, byte-interleaved
even/odd like the program ROM) is a **directory-based resource archive**, not code. Decoded by
de-interleaving the even/odd images and walking the header.

## Directory
Starts at offset 0: a table of **little-endian u32 chunk offsets** (relative to `0x48000000`),
monotonically increasing. The first data chunk begins at `0x48000200`; the directory occupies the
low ~0x150 bytes. Walking it yields ~85 offsets. (A few entries point at small marker/sub-headers
inside a chunk rather than a top-level chunk — e.g. the ASCII markers `"84\n"`/`"27\n"`/`"ZZZ\n"`
that separate the JPEG runs — so treat the directory as "offsets of interest", with the real chunk
kinds identified by their leading magic.)

## Chunk kinds (by leading magic / content)
| offset | magic / content | size | meaning |
|--------|-----------------|------|---------|
| `0x48000200` | nested u32 offsets | 0x34658 | **sub-directory** (further indexed resources) |
| `0x48034858` | `ZZZJ` | 0x14b0 | data block (ZZZ-family marker) |
| `0x48035d08` | **`TCMP`** | 0xa96c | **RAM code overlay** — copied to RAM `0x50180000` at boot (via `LibMemCopy`) and executed as MN10300 code. This is the `RamCodeOverlayImage` the KN2400 boot RE traced. |
| `0x48040674` | **`TPAD`** | 0x1d18 | performance-**pad** data (index/params) |
| `0x4804238c` | `"Technics Pads   "` | 0x142f0 | the named **Technics Pads** resource (accompaniment pad patterns) |
| `0x4805667c` / `0x4806ea98` | binary | — | data / sub-tables |
| `0x48139ef0` … | **JFIF JPEG** streams | — | UI/graphics images (see below) |
| `0x483e828c` | `"Technics Rhythms"` | 0x1248 | the named **Technics Rhythms** resource (style/rhythm index; cf. the program-ROM `TechnicsRhythmsResource`) |
| `0x483e94d4` | `0xFF…` | 0x16b2c | end padding |

## Embedded graphics — 117 standard JPEGs
Scanning for `ff d8 ff e0 … ff d9` finds **117 JPEG streams**; **115 decode as standard JFIF** with a
normal decoder (the 2 failures are truncated/marker artifacts). Dimensions histogram: 52×`160x120`
(icons/thumbnails), 13×`240x160`, **12×`640x240`** (full-screen), 12×`160x80`, 7×`320x120`, plus
assorted sizes. The `640x240` images are full-screen **reference/help screens** matching the LCD
resolution — e.g. a RHYTHM home screen (`8 Beat Rock`, tempo ♩=120, DSP/effects/pads/memory panels)
and the **ORGAN STYLIST style-list** (`Swing Tonewheels` / `Classic B3 Jazz` … — the same names as
`StyleGenreTable`, confirming the [rhythm catalog](/kn7000-rhythm-catalog/) extraction).

**Important:** these are *standard* JPEGs. The long-standing note that "the boot-splash JPEG decodes
to garbage" is therefore a **firmware/emulation JPEG-decoder bug**, NOT a non-standard format — the
source data is a valid JFIF stream.

## Reproduce
De-interleave `kn7000_table_{even,odd}.rom` (`out[0::4]=e[0::2]; out[1::4]=e[1::2]; out[2::4]=o[0::2];
out[3::4]=o[1::2]`) → 4 MB image. Walk the u32 directory at offset 0 for chunk offsets. Extract JPEGs
by scanning SOI→EOI; each decodes with PIL/any JFIF decoder.
