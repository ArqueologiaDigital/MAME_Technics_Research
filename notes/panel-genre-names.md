# KN7000 RHYTHM GENRE names (ev2005 arg 0xN5F, N = genre id 0x0-0xF)

## Result — genre id -> name

| genre id | ev2005 arg | name (display)      | ROM literal        | source |
|----------|-----------|---------------------|--------------------|--------|
| 0x0      | 0x005F    | 8&16 BEAT           | `8&16 BEAT`        | GenreStyleTable[0]  @0x48735EE4 |
| 0x1      | 0x015F    | ROCK & POP          | `ROCK & POP`       | GenreStyleTable[1]  @0x48735EFC |
| 0x2      | 0x025F    | BALLAD              | `BALLAD`           | GenreStyleTable[2]  @0x48735F14 |
| 0x3      | 0x035F    | JAZZ & SWING        | `JAZZ & SWING`     | GenreStyleTable[3]  @0x48735F2C |
| 0x4      | 0x045F    | BALLROOM            | `BALLROOM`         | GenreStyleTable[4]  @0x48735F44 |
| 0x5      | 0x055F    | MOVIE & SHOW        | `MOVIE & SHOW`     | GenreStyleTable[5]  @0x48735F5C |
| 0x6      | 0x065F    | ENTERTAINER         | `ENTERTAINER`      | GenreStyleTable[6]  @0x48735F74 |
| 0x7      | 0x075F    | ORGANIST            | `ORGANIST`         | GenreStyleTable[7]  @0x48735F8C |
| 0x8      | 0x085F    | 60s & 70s           | `60s & 70s`        | GenreStyleTable[8]  @0x48735FA4 |
| 0x9      | 0x095F    | MODERN DANCE        | `MODERN DANCE`     | GenreStyleTable[9]  @0x48735FBC |
| 0xA      | 0x0A5F    | SOUL & R&B          | `SOUL & R&B`       | GenreStyleTable[10] @0x48735FD4 |
| 0xB      | 0x0B5F    | COUNTRY & WESTERN   | `COUNTRY&WESTERN`  | GenreStyleTable[11] @0x48735FEC |
| 0xC      | 0x0C5F    | MARCH & WALTZ       | `MARCH & WALTZ`    | GenreStyleTable[12] @0x48736004 |
| 0xD      | 0x0D5F    | LATIN & WORLD       | `LATIN & WORLD`    | GenreStyleTable[13] @0x4873601C |
| 0xE      | 0x0E5F    | CUSTOM              | `CUSTOM`           | GenreStyleTable[14] @0x48736034 |
| 0xF      | 0x0F5F    | MEMORY              | `MEMORY`           | GenreStyleTable[15] @0x4873604C |

## How the mapping is derived

The 16 RHYTHM GROUP genre-select buttons all fire firmware event **ev2005** with
argument **0xN5F**, where the high nibble `N = (arg >> 8) & 0xF` is the genre id.
From `seg_event_map.txt` (board-decode, PINNED):

- SEG00 b2..b7 -> args 0x005F,0x015F,0x025F,0x035F,0x045F,0x055F  = genres 0..5
- SEG01 b2..b7 -> args 0x065F,0x075F,0x085F,0x095F,0x0A5F,0x0B5F  = genres 6..11
- SEG02 b2..b5 -> args 0x0C5F,0x0D5F,0x0E5F,0x0F5F               = genres 12..15

`N` indexes directly into the firmware **GenreStyleTable @0x48735EE4** (program flash
`full.bin`, file offset 0x335EE4 = 0x48735EE4 - 0x48400000).

## The ROM table (source of the names)

GenreStyleTable is 16 fixed-width **24-byte** records, tightly packed. Each record:

```
offset  size  field
+0x00   16    char name[16]   (ASCII, space-centered, e.g. "   ROCK & POP   ")
+0x10    1    0x00            (name pad / terminator)
+0x11    1    uint8  count    (number of styles in the genre; see below)
+0x12    2    0x0000         (pad)
+0x14    4    uint32 ptr      (LE pointer into 0x485B89xx = per-genre style list)
```

record[N] address = 0x48735EE4 + 24*N (file offset 0x335EE4 + 24*N).

Verified by direct extraction of the 16 name fields (raw ASCII, whitespace preserved):

```
[ 0] "   8&16 BEAT    "   count=0x0A  ptr=0x485B899C
[ 1] "   ROCK & POP   "   count=0x10  ptr=0x485B89C4
[ 2] "     BALLAD     "   count=0x10  ptr=0x485B8A04
[ 3] "  JAZZ & SWING  "   count=0x14  ptr=0x485B8A44
[ 4] "    BALLROOM    "   count=0x10  ptr=0x485B8A94
[ 5] "  MOVIE & SHOW  "   count=0x14  ptr=0x485B8AD4
[ 6] "  ENTERTAINER   "   count=0x0E  ptr=0x485B8B24
[ 7] "    ORGANIST    "   count=0x0A  ptr=0x485B8B5C
[ 8] "   60s & 70s    "   count=0x0D  ptr=0x485B8B84
[ 9] "  MODERN DANCE  "   count=0x0E  ptr=0x485B8BB8
[10] "   SOUL & R&B   "   count=0x13  ptr=0x485B8BF0
[11] "COUNTRY&WESTERN "   count=0x0E  ptr=0x485B8C3C
[12] " MARCH & WALTZ  "   count=0x0C  ptr=0x485B8C74
[13] " LATIN & WORLD  "   count=0x1A  ptr=0x485B8CA4
[14] "     CUSTOM     "   count=0x14  ptr=0x485B8D0C
[15] "     MEMORY     "   count=0x03  ptr=0x485B8D5C
```

(The `count` byte is a strong-but-secondary observation: it equals the number of styles
each genre lists on screen — e.g. LATIN & WORLD = 0x1A = 26, MEMORY = 3. Not needed for
naming; recorded for completeness.)

## Cross-checks (all consistent)

1. **panel-rhythm-group.md** (VERIFIED ground truth, real-machine + snapshot) lists the
   same 16 names in the same order 0..15, and explicitly states "Genre order =
   GenreStyleTable @0x48735EE4". Exact match. (That note's title-line abbreviation
   "SWING" for genre 3 is the ROM's full "JAZZ & SWING".)
2. **Empirical SEG00/01/02 b2-b7 bit map** (snapshot + user testing) -> genre ids 0..15,
   which map 1:1 to the ev2005 arg high nibble in seg_event_map.txt. Exact match.

## Notes on literal vs. display spelling

- Genre 0x0 ROM literal is `8&16 BEAT` (no spaces around `&`); displayed the same.
- Genre 0xB ROM literal is `COUNTRY&WESTERN` (no spaces around `&`, to fit 16 cols);
  the conventional display / this project's label writes it `COUNTRY & WESTERN`.
- All other names carry surrounding spaces only for centering in the 16-char field.
