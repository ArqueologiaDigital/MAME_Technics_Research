# `AVSDRV.SYS` — NEC's uPD6380 DOS driver: ACQUIRED from NEC's own server

*Side-quest for the KN5000 effects DSP (NEC uPD6383GF, undocumented ISA). Its sibling
uPD6380 is the audio DSP of the PC-98GS / PC-9801-73, and `AVSDRV.SYS` is the driver
that programs it. Follows `kn5000-dsp-abv.md` §5 and `kn5000-dsp-datasheet-hunt.md`
§R2.2/§R3.3, which named this file as the highest-value remaining lead.*

**Result in one line: `AVSDRV.SYS` version 5.10 was OBTAINED — from NEC's own legacy
download server, inside NEC's own free MS-DOS 6.2 update module `UPDOS62.EXE` — and it
VERIFIES: the image contains `MOV DX,0A462h` / `MOV DX,0A464h` with coherent IN/OUT
sequences, an `AVSDRV$$` device name matching the Technical Data Book verbatim, and
three `MOV AX,25D9h` INT-0D9h vector installations. It is NOT the "Qvision PCM"
red herring.  The payload is LZ-packed behind an `AVSLOAD$` loader stub, so the
microprogram extraction still needs the packer undone — that is the next step.**

---

## 1. Acquisition — every URL tried, with outcomes

The instruction was: NEC's own servers first, driver-only archives second, no
commercial software, no game images. The winning path was source class **1** —
NEC distributing its own module.

### 1.1 What worked (MEASURED)

`AVSDRV.SYS` is not only a board-bundle file: NEC shipped it as part of **MS-DOS 6.2
運用ディスク#4**, and NEC's **free "MS-DOS 6.2 アップデートサービス" module** replaces
it (the `LISTFILE.TBL` inside the module marks `+AVGDRV.SY_` and `+AVSDRV.SY_` with
`+`, i.e. *supplied by this update*). That module is a NEC-published patch, not the
commercial DOS product.

| step | URL | outcome |
|---|---|---|
| 1 | `https://support.nec-lavie.jp/driver/detail?module_no=42` and `=10` (the documented DOS 6.2 update module numbers) | HTTP 200 but **お探しのNECサポートプログラムは見つかりませんでした** — NEC has retired the legacy modules |
| 2 | `https://www.support.nec.co.jp/ListModuleDownload.aspx` (NEC 8番街) | live, but enterprise-server modules only; no PC-98 |
| 3 | `https://download-drv.com/support/download/3/driver/3236233729/` | a metadata-only mirror of the NEC page; no files |
| 4 | `https://dw230.com/98/dr2.php` | driver list intact, **downloads withdrawn (再配布禁止)**; no AVSDRV entry anyway |
| 5 | `http://search.casnavi.nec.co.jp/...` | host is now **NXDOMAIN** |
| 6 | Wayback CDX, `url=search.casnavi.nec.co.jp/download&matchType=prefix` → 6 061 URLs | ★ lists `…/download/pc/module/dos/dos6/updos62/UPDOS62.EXE` and `…/dos6up/dosup20{0..4}.exe` |
| 7 | `https://web.archive.org/web/20040123195142id_/http://search.casnavi.nec.co.jp/download/pc/module/dos/dos6/updos62/UPDOS62.EXE` | ★ **FETCHED**, 1 257 081 bytes, PE32 LHa self-extracting archive |

Not needed and not touched: the Policenauts archive.org item or any other game/ROM
material (explicitly out of bounds).

### 1.2 What failed, for the record (MEASURED)

* `archive.org` advancedsearch `q=avsdrv` → **0 items** (re-confirms the earlier negative).
* Wayback CDX domain-wide wildcard queries (`*/*avsdrv*`) → **403, "requires authorization"**;
  per-domain `filter=urlkey:.*avsdrv.*` on `121ware.com` → **504 gateway timeout**.
* `support.nec-lavie.jp/driver/detail` is archived, but **never with a query string**, so the
  module pages themselves are not in the Wayback Machine.
* `www.vector.co.jp/vpack/filearea/pc/hard/sound/pc98/` → 404.
* `navitoku.jp/archive/nx-station/support_pc98.html` → 403 to our fetcher.
* 5ch thread `software/1614419035` (the one that named the DOS 6.2 update route) → 403 from
  every mirror tried (`egg.5ch.net`, `egg.5ch.io`, `itest.5ch.net`, `mimizun`, Wayback 503).
  The lead survived only as a search-engine snippet; it turned out to be correct.
* `gh` CLI is unauthenticated in this environment, so GitHub code search was unavailable.
* `curl` to `*.nec*.jp` **fails under HTTP/2** (`INTERNAL_ERROR`); `--http1.1` is required.
  Worth remembering for any future NEC fetch.

### 1.3 The artefacts (MEASURED)

Kept **outside** the git repo (NEC-copyrighted binaries) at
`~/compartilhado/pc98_tdb/avsdrv/`:

| file | size | sha256 |
|---|---|---|
| `UPDOS62.EXE` | 1 257 081 | `0685641e92c8e0224cf353da1f1547c139c74827374886967d6d4322abdc7e60` |
| `AVSDRV.SY_` (SZDD, from the module) | 58 168 | `8a585e2564ac469aa4e3d7173f2886dc05f7d6361a504124dd2125f6b3e5ee98` |
| **`AVSDRV.SYS`** (expanded) | **58 668** | `6bcd2b02ac3d1998ac9cce1f515ac8dcb6f24421271d1c9c93eaefbea49ff6ae` |
| `AVGDRV.SY_` | 15 015 | `4327b960bbb6da4e768549240622bbb767d72ff7fd21e668fcdf85f1cf28b057` |
| `AVGDRV.SYS` (expanded) | 26 184 | `89bb848316ba84d431718e0b00089e2270dfa0a6c242fe5a8124622001edebe2` |

Both `.SY_` files are dated **1996-03-31** in the LHa directory.

Container chain, all cracked (MEASURED):

```
UPDOS62.EXE   PE32 + LHa SFX          ->  7z x
  AVSDRV.SY_  Microsoft SZDD ('A')    ->  tools/avsdrv_unpack.py expand
    AVSDRV.SYS  MZ + DOS device header + LZ-packed payload   <- we are here
```

`tools/avsdrv_unpack.py` implements the SZDD expander in pure Python (no `lha`,
no `msexpand` needed) and the verification scan below.

---

## 2. VERIFICATION — is this the uPD6380 driver? YES

The trap flagged in `kn5000-dsp-datasheet-hunt.md` §R3.3 was that the `AVSDRV` referenced
by the dosbox-x issue is described as a "Qvision PCM" driver, which would be a
PC-9801-**86** variant that never touches the DSP.  Test: does the binary reference
**A462h / A464h**?

`python3 tools/avsdrv_unpack.py scan AVSDRV.SYS` (MEASURED):

```
MZ, header 0x200
DOS device driver header: attr=0x8000 strategy=0x0976 interrupt=0x0981 name='AVSLOAD$'
MOV AX,25D9h (install INT 0D9h): 3 at 0x75e4, 0x96a7, 0xd747
INT 0D9h:                        2 at 0x14ce, 0x965a
A460h @ 0x00c54  ba 60 a4 ec b1 04 d2   MOV DX,0A460h ; IN AL,DX ; MOV CL,4 ...
A460h @ 0x02d50  ba 60 a4 ec 24 f0 3c   MOV DX,0A460h ; IN AL,DX ; AND AL,0F0h ; CMP AL,..
A462h @ 0x02102  ba 62 a4 ec 24 80 0c   MOV DX,0A462h ; IN AL,DX ; AND AL,80h ; OR AL,20h ; OUT DX,AL
A462h @ 0x07e4c  ba 62 a4 b0 20 ee      MOV DX,0A462h ; MOV AL,20h ; OUT DX,AL
A464h @ 0x036a9  ba 64 a4 ..       ..   MOV DX,0A464h ; ... ; OUT DX,AL
A466h @ 0x02b7f  ba 66 a4 ee 59 c3      MOV DX,0A466h ; OUT DX,AL ; POP CX ; RET
A468h @ 0x0192b  ba 68 a4 ec 24 10 3c   MOV DX,0A468h ; IN AL,DX ; AND AL,10h ; CMP AL,..
```

Four independent confirmations:

1. **`A462h` and `A464h` are both present as `MOV DX,imm16` operands** — the exact
   control and data ports the Technical Data Book assigns to the uPD6380.
2. The semantics agree with the data book's bit map. `AND AL,80h ; OR AL,20h ; OUT DX,AL`
   preserves the command/data bit and asserts **bit 5**; `MOV AL,20h ; OUT DX,AL` writes
   bit 5 alone — the documented **reset / I-RAM-modify** bit.  `IN AL,DX ; AND AL,10h`
   at `A468h` and `AND AL,0F0h` at `A460h` are status polls, as expected.
3. The device name string **`AVSDRV$$`** and version banner **`AVSDRV$$Ver 5.10Rev 1.00.`**
   appear in the image; `AVSDRV$$` is verbatim what the data book (`kn5000-dsp-abv.md` §3.2)
   says the driver installs.
4. **`MOV AX,25D9h`** (DOS `INT 21h/AH=25h`, vector number `0D9h`) occurs three times —
   the documented `INT 0D9H` entry point being hooked, once per code variant.

The companion `AVGDRV.SYS` (`AVGDRV$$` Ver 3.20, sections `CODE_GLO` / `CODE_VIDEO`,
switches `/E /C /S /R`) is the **video/graphics** half of the same AV pair and touches
none of these ports. It is not relevant to the DSP.

**Conclusion (MEASURED): this is the real uPD6380 driver, not the Qvision-PCM
red herring.** The 1996 version 5.10 evidently covers both worlds — the option strings
`/86 : avs_86.exe` and `/cs : avs_cs.exe` show two selectable hardware images — which is
probably exactly why the same filename is loosely described elsewhere as an "-86" driver.

---

## 3. What the file actually is (MEASURED)

```
+0x000  MZ header, header paragraphs = 0x20, image length 58 668 (= whole file)
+0x200  DOS character-device header:
          next      FF FF FF FF
          attribute 80 00                (character device)
          strategy  0x0976   interrupt  0x0981
          name      "AVSLOAD$"
+0x209  "AVSLOAD$Ver 1.01"
+0xae0  usage text:   $ /?? :
                       /86 : avs_86.exe
                       /cs : avs_cs.exe
                       //  : avs_86.org, avs_cs.org
+0xb5b  "avs_86.org", "avs_cs.org"
+0xe99  "GG=86t-=cst"      <- the option parser comparing the literals "86" and "cs"
```

★ So `AVSDRV.SYS` v5.10 is **not** a single driver: it is a loader device named
`AVSLOAD$` that carries **two** driver images and installs the right one —
`avs_86` (PC-9801-86 family) and `avs_cs` — and, per the usage text, can also
**write them out to disk as `avs_86.exe` / `avs_cs.exe` (or `.org`)**.

**That last point is the shortcut.** (INFERRED, high confidence.) Rather than reversing
the packer, running `AVSDRV.SYS` with the `/86` and `/cs` switches under a PC-98 emulator
— or under DOSBox-X, which needs no real hardware to run the extraction path — should
dump both images already decompressed. That is by far the cheapest route to a clean,
disassemblable driver.

### 3.1 The payload is LZ-packed (MEASURED)

Shannon entropy per 4 KiB block: `0x0000` 3.12, then **6.2 – 7.2 bits/byte for every
block from `0x1000` to the end**. Two further `MZ` signatures at `0x921a` and `0xe1fc`
have mangled header fields (`40 07 80 04` filler patterns) — they are compressed copies
of the two embedded images' headers, not real headers.

**Consequence, stated honestly:** the `MOV DX,0A462h` sequences quoted in §2 are found
inside the *compressed* stream, as literal runs the packer did not match. Twelve
consecutive bytes decoding to a semantically correct port sequence, three separate times,
plus the two ASCII device names and the `25D9h` constants, is conclusive as *identification*
— but it is **not** yet a usable disassembly. Byte offsets in §2 are offsets in the packed
image and must not be treated as code addresses.

No `LZEXE`/`PKLITE`/`diet`/`EXEPACK` signature was found; the packer looks like NEC's own
(the `AVSLOAD` stub is the depacker).

---

## 4. What we did NOT get, and why

The five downstream deliverables the brief asked for — the I-RAM upload loop, the
`AH=01H $INITFUNC` dispatch, the 19 microprogram blobs, the microprogram **word size**
(5-byte/36-bit like the uPD6383, or 4-byte/32-bit), and the cross-corpus instruction
comparison — **all sit behind the packer** and are therefore **not answered here**.
Nothing about them is asserted in this note. In particular:

* **The word size is UNKNOWN.** Any statement that the 6380 is or is not 36-bit would be
  fabrication at this stage. The compressed stream cannot be searched for 5-byte periodicity.
* Whether the microprograms are even *in* this file is still only INFERRED (from the data
  book's statement that only one function is resident at a time, and `$INITFUNC` loads it).
  58 668 bytes packed for two images is comfortably large enough to hold 19 small
  microprograms plus two drivers, but that is an argument, not a measurement.

---

## 5. NEXT STEPS, in cost order

1. **Run the loader and let it unpack itself.** `DEVICE=AVSDRV.SYS /86` and `/cs` under
   DOSBox-X (PC-98 mode) or Neko Project, then recover `avs_86.exe` / `avs_cs.exe`.
   Cheapest by far; the driver was *built* to do this. If the switches turn out to be
   dump-to-disk, this hands over two clean 16-bit binaries.
2. Failing that, reverse the `AVSLOAD$` depacker itself. It lives in the low, *uncompressed*
   region `0x200`–`0x1000`; the strategy/interrupt entry points are at `0x976` / `0x981`
   relative to the image base, i.e. file offsets `0xB76` / `0xB81`. A few hundred bytes of
   16-bit code — a bounded job.
3. Then, on the unpacked image: follow the `INT 0D9h` handler → `AH=01h` (`$INITFUNC`)
   → the `A462h`/`A464h` upload loop. Read off bytes-per-word, the preceding command
   bytes, and how the I-RAM address is set. **Compare against the KN5000's parallel host
   port** (`kn5000-dsp-header.md`, `kn5000-dsp-parameters.md`): agreement or disagreement
   is immediately valuable either way.
4. Then the 19 blobs and the cross-corpus idiom hunt (`kn5000-dsp-effect-map.md`).
5. Independently worth 10 minutes: the same Wayback-of-casnavi trick found **6 061**
   NEC-hosted module URLs. Other PC-98 sound modules in that list have not been examined,
   and NEC's `dosup20{0..4}.exe` (MS-DOS 6.2 update service, 0.8–1.2 MB each, also fetched
   and verified as LHa SFX) were **not** searched for further DSP-touching binaries —
   only `UPDOS62.EXE` was, because it was the only one whose string table contained
   `AVSDRV`.

## 6. Reproduce

```sh
# 1. NEC's own module, via the Wayback Machine (curl MUST use --http1.1 for nec*.jp)
curl -L --http1.1 -A 'Mozilla/5.0' -o UPDOS62.EXE \
  'https://web.archive.org/web/20040123195142id_/http://search.casnavi.nec.co.jp/download/pc/module/dos/dos6/updos62/UPDOS62.EXE'
7z x -oex UPDOS62.EXE                       # LHa SFX -> ex/AVSDRV.SY_
python3 tools/avsdrv_unpack.py expand ex/AVSDRV.SY_ AVSDRV.SYS
python3 tools/avsdrv_unpack.py scan AVSDRV.SYS
```
