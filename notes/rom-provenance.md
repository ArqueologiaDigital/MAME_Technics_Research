# ROM provenance — what every shipped ROM is, and how to remake it

> ## ★ The authoritative copy now lives in its own private git repo
> ### `/home/fsanches/compartilhado/technics_roms`
>
> That repo is the **source of truth** for every Technics ROM artifact: the ROM set,
> the `.SLD` update-disk sources they regenerate from, the KN5000 chip dumps, and
> Felipe's own SD-card image. The build tree and the published `kn7000-emulator/`
> folder are both **derived copies** — `publish-binary.sh` now tops the build tree up
> from the repo before publishing, so a wiped build tree self-heals instead of
> shipping stale files.
>
> It carries an integrity manifest (`MANIFEST.tsv`, cross-referenced against the
> hashes the MAME driver declares), a `verify.sh`, and a **do-not-publish privacy
> guard** — copyrighted firmware plus personal media, so no remote is configured and
> a `pre-push` hook refuses every push. Read `technics_roms/README.md` first; it is
> the fuller version of this document.

**Status: the entire shipped ROM set is REGENERABLE, and this was verified by
rebuilding all 14 files from preserved sources and comparing md5 — every one
matched bit-for-bit (2026-07-20).** There are no non-regenerable ROM artifacts.

The single documented path is **`tools/make-roms.sh`**:

```
tools/make-roms.sh check      # verify the build tree against the expected md5s
tools/make-roms.sh generate   # rebuild every ROM from preserved sources
tools/make-roms.sh restore    # copy the set back from the published folder (fast path)
tools/make-roms.sh list       # print the manifest
```

## Why this file exists

`tools/publish-binary.sh` copies ROMs **one way** — build tree → published folder,
`cp -u`, never deleting. The build tree (`kn7000_mame_build/`) is explicitly
*disposable*: `build.sh` recreates it and it is not version-controlled. So when the
build tree lost its ROMs, publish printed a quiet per-model warning, skipped those
models, and left a stale copy in the published folder — which had silently become the
**only surviving copy** of the kn6000/kn6500 sets and of most of the kn7000 set.
Nothing was actually lost (both trees live on the persistent virtiofs share), but the
set was one `rm -rf` away from being unrecoverable, and the recipes were scattered
across half a dozen notes.

Two things changed: the build tree was restored from the published set, and
`publish-binary.sh` now **fails loudly** with an end-of-run summary instead of a quiet
mid-run warning (override with `PUBLISH_ALLOW_MISSING_ROMS=1`).

## The set

`sld` = decompress preserved `.SLD` → concatenate → even/odd 16-bit split.
`synth` = deterministic generator script, **not a dump**.
`derived` = byte copy of another file in the set.

| file | model | kind | regenerable | md5 |
|---|---|---|---|---|
| `kn7000_program.rom` (4157185) | kn7000 | sld | yes | `38079d4c334c46dca061a6339739dbbf` |
| `kn7000_program_even.rom` | kn7000 | sld | yes | `5b085ad9269750fddb5faa4d69eb5ac7` |
| `kn7000_program_odd.rom` | kn7000 | sld | yes | `102cfa7773b087271726107ade5c7183` |
| `kn7000_table.rom` (4101332) | kn7000 | sld | yes | `aaae68589e59f98bc2a521be1c851dec` |
| `kn7000_table_even.rom` | kn7000 | sld | yes | `ccdfdad619d6740f6f1754d0432d22eb` |
| `kn7000_table_odd.rom` | kn7000 | sld | yes | `cda9079ed33867454745903f91addc6d` |
| `kn7000_rhythms_synthetic.rom` | kn7000 | synth | yes | `73c9e155defedf0b60b245ba8ba67bcf` |
| `kn7000_waves_synthetic.rom` (16 MB) | kn7000 | synth | yes | `70f62157c898143bd09ef4544ba6f4f1` |
| `kn6000_program_even.rom` | kn6000 | sld | yes | `9e4a020ef87bffd7a5003c380260cd59` |
| `kn6000_program_odd.rom` | kn6000 | sld | yes | `291b6caee074bdeef26db51673e7062d` |
| `kn6500_program_even.rom` | kn6500 | sld | yes | `5a6cb22b70f61ac7ffc6f37ec3f9432d` |
| `kn6500_program_odd.rom` | kn6500 | sld | yes | `d2442b2c68024da9dd2d0bdb731212b3` |
| `kn2400_program_even.rom` | kn2400 | sld | yes | `8d9c67eab4d1067c96395f0069493fc7` |
| `kn2400_program_odd.rom` | kn2400 | sld | yes | `ed67066933a236cfb569890a847f09a2` |
| `kn7000_table_{even,odd}.rom` in `roms/kn6000/` and `roms/kn6500/` | kn6xxx | derived | yes | same as the kn7000 table files |

`kn2600` is a clone of `kn2400` and resolves its ROMs from the kn2400 set — it ships no
folder of its own.

## Recipes

### 1. KN7000 program + table — from the update disks

The `.SLD` container (shared with the KN5000): 8-byte magic, 24-bit **big-endian**
decompressed size at offset 8, then an LZSS stream (4K window, zero-initialised).
Each update spans two floppies whose decompressed payloads are **concatenated**.

```
cd /home/fsanches/compartilhado/kn7000_extraction
venv/bin/python kn7000_extract.py /home/fsanches/compartilhado/KN7000 output
venv/bin/python rom_split_evenodd.py output/kn7000_program.rom 0x400000 \
    kn7000_program_even.rom kn7000_program_odd.rom
venv/bin/python rom_split_evenodd.py output/kn7000_table.rom 0x400000 \
    kn7000_table_even.rom kn7000_table_odd.rom
```

The venv supplies the `pylzss` module (`pip install -r requirements.txt`).

**This step is self-validating.** `kn7000_extract.py` checks the result against the
manufacturer's own `SMCK*.INF` oracle shipped on the disks — a 32-bit total byte-sum
plus 16-bit sums of each 0x40000 block. Observed on the verification run:
total `0x18CE8702` (program) and `0x13DCD1A3` (table), all 16 blocks matching.

| source | size | md5 |
|---|---|---|
| `KN7000/kn7-16/kn7-16a-files/JK1.SLD` → 0x200000 raw, magic `JKPRG4K\0` | 1143233 | `1edb292b84e980f02603bf9c71a825b7` |
| `KN7000/kn7-16/kn7-16b-files/JK2.SLD` → 0x1F6F01 raw, magic `JKPRG4K\0` | 945141 | `52e6b213b58fa7bacb8385550a8caa9d` |
| `KN7000/kn7-14/kn7-14_3-files/JKT1.SLD` → 0x200000 raw, magic `JKTB14K\0` | 1410544 | `39afaa7fdd144919234cc09c7cb9546a` |
| `KN7000/kn7-14/kn7-14_4-files/JKT2.SLD` → 0x1E94D4 raw, magic `JKTB24K\0` | 1193428 | `875541c451ce94b753af7c314543c2b5` |

So `kn7000_program.rom` = JK1+JK2 = 0x3F6F01, and `kn7000_table.rom` = JKT1+JKT2 = 0x3E94D4.
Both linear images are the raw concatenation, **not** padded; the padding to 0x400000
with `0xFF` (erased flash) happens in the even/odd split.

> **ERRATUM.** `notes/mame-pr-rom-manifest.md` used to say the KN7000 ROMs were "even/odd
> of the decompressed JK1.SLD (program, kn7-16 update) and JK2.SLD (table, kn7-14
> update)". That is wrong: **JK2 is the second half of the *program* image** (kn7-16),
> and the table comes from **JKT1+JKT2** (kn7-14). Corrected in that file.

### 2. KN6000 / KN6500 / KN2400 program — same container

Identical format, but these updates ship **no `.INF` checksum oracle**, so there is no
independent verification beyond the container's own declared decompressed size (which
`make-roms.sh` asserts).

| model | sources | linear size | magic |
|---|---|---|---|
| kn6000 | `kn7000_scratchpad_snapshot/kn6probe/IK1.SLD` + `IK2.SLD` | 0x3F7A31 | `IKPRG4K\0` |
| kn6500 | `kn7000_scratchpad_snapshot/kn6probe/IKV1.SLD` + `IKV2.SLD` | 0x381691 | `IKPRG4K\0` |
| kn2400 | `kn7000_scratchpad_snapshot/kn24/LKG1.SLD` + `LKG2.SLD` | 0x3965D3 | `LKGP14K\0` / `LKGP24K\0` |

| source | md5 |
|---|---|
| `kn6probe/IK1.SLD` | `af5298f34f0b5239a6a2a7d7572d63f2` |
| `kn6probe/IK2.SLD` | `65d6eeed95aee797eea5922ce06e5e19` |
| `kn6probe/IKV1.SLD` | `aa20a9e648303445d6853f80221c9186` |
| `kn6probe/IKV2.SLD` | `c78db978c5011bbe30c688052badd310` |
| `kn24/LKG1.SLD` | `fb29b14161ddcabaa80d4aa8b24e4512` |
| `kn24/LKG2.SLD` | `d583e495b5f842c62f17e76114589c5a` |

The kn2400 concatenation equals the `KN24PRG.DAT` shipped in `kn26-11.zip`
(3761619 bytes) — a useful independent cross-check.

Until 2026-07-20 **no committed script performed this decompression** — it had been done
ad hoc and only the outputs survived. `tools/make-roms.sh generate` now does it
(`gen_sld_model`), closing that gap.

**kn2400 has no table ROM**: the driver leaves the `0x48000000` region `ROMREGION_ERASEFF`
and a read-tap proved the firmware never touches it at boot (see `notes/kn2400-boot.md`).

### 3. The `.exe` → `.SLD` step is NOT scripted — and cannot be, here

The distributed archives contain DOS **self-extracting installers**, not the `.SLD` files:

| archive | md5 | contents |
|---|---|---|
| `KN7000/kn7-16/kn7-16.zip` | `edca672a9e145d7eac11452ed5499670` | program update (2 floppies) |
| `KN7000/kn7-14/kn7-14.zip` | `9a4c8aa2a168b601b3c5557a7055d0b7` | table update (2 floppies) |
| `KN6000/ca_software_files/kn6-71.zip` | `0703d083d255d1f29aacba742ceb5705` | `kn6-v7-1a.exe`, `kn6-v7-1b.exe` |
| `KN6000/ca_software_files/kn65-13.zip` | `8cff0740f2032e460697929fdade159c` | `kn65_v1-3a.exe`, `kn65_v1-3b.exe` |
| `KN2400_KN2600_KN7000/kn24-11.zip` | `627675f435a1cac2d5a60ea9e2bc187f` | `kn24_11a.exe`, `kn24_11b.exe` |

Checked directly: the `.SLD` payload is **not stored verbatim** inside these `.exe`s.
The SLD magic does not appear anywhere in the file and no 64-byte run of `IK1.SLD`
matches, so the SFX applies its own compression. The filenames *do* appear as plain
strings (e.g. `IK1.SLD` at `0x1022E` in `kn6-v7-1a.exe`), which is a directory entry, not
the data. Recovering a `.SLD` from a `.exe` therefore means **running the DOS installer**
(DOSBox/dosemu) to write its update floppy and reading the file off the FAT image.

**Consequence for preservation: the extracted `.SLD` files are the practical primary
source and must be preserved as such.** They are the input `make-roms.sh generate`
depends on. Losing them would mean re-running DOS installers to get back to a
reproducible state.

### 4. `kn7000_rhythms_synthetic.rom` — synthetic, deterministic

```
python3 tools/gen_technics_rhythms.py \
  --table <roms>/kn7000/kn7000_table.rom \
  --prog  /home/fsanches/compartilhado/kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin \
  --out   <roms>/kn7000/kn7000_rhythms_synthetic.rom
```

**Verified to reproduce the published file bit-identically**
(md5 `73c9e155defedf0b60b245ba8ba67bcf`, 4108415 bytes).

This is **NOT a dump.** The real ~4.1 MB rhythm flash is undumped. Every byte of the
output is either a verbatim copy of real dumped bytes (the intact directory prefix from
the table flash at `0x483E828C`, the 8 aux records and record-0 payload from the program
ROM stub) or a self-announcing placeholder — the 168 factory names that existed only on
the never-dumped flash are emitted as `"BALLAD 04 ?"`-style strings with a trailing `?`.
52 styles show their real names, resolved through the intact secondary catalog. The
driver loads it `BAD_DUMP`. See the integrity statement at the top of the generator.

Note the `--prog` input is a *derived* file (the decompressed program image); it is the
same bytes as `kn7000_program.rom`, kept in the scratchpad snapshot.

### 5. `kn7000_waves_synthetic.rom` — synthetic, deterministic, donor-based

The KN7000's four PCM wave mask ROMs (IC203/204/207/208) are **undumped**. This 16 MB
pack is a clearly-labelled placeholder built from donor samples carved out of the
**genuine dumped KN5000 waveform ROMs**, keyed by the KN7000's runtime sample-select
decode. It embeds a provenance block and the driver loads it `BAD_DUMP`.

Two stages, **both verified reproducible**:

```
# a) carve donor waves out of the genuine KN5000 dumps (744 waves, 6.0 MB PCM)
python3 tools/extract_kn5000_waves.py \
  --roms /home/fsanches/compartilhado/kn5000_original_roms/kn5000/kn5000_waveform_rom.ic30{4,5,6,7} \
  --outdir /home/fsanches/compartilhado/kn7000_scratchpad_snapshot/session-c6cf97f4-2026-07-16/kn5000_waves

# b) assemble the pack (mapping: tools/wave_pack_map.json)
python3 tools/make_wave_pack.py \
  --waves .../kn5000_waves --out <roms>/kn7000/kn7000_waves_synthetic.rom
```

Stage (a) reproduced `manifest.json` at md5 `dbb7d933ffed031231f31c3fe48b651b` and a
byte-identical `ic307/` WAV set; stage (b) reproduced the pack at md5
`70f62157c898143bd09ef4544ba6f4f1`. **So this file is regenerable** — an earlier
assumption that nothing generated it was wrong.

Donor ROM hashes (genuine KN5000 dumps, `kn5000_original_roms/kn5000/`):

| file | md5 |
|---|---|
| `kn5000_waveform_rom.ic304` | `9f5154dd3bbb10abd9f1c267c935c8fa` |
| `kn5000_waveform_rom.ic305` | `fd18beef43c95db2e9f98e850c6f3169` |
| `kn5000_waveform_rom.ic306` | `d9bc45bc922cd325caecab04cc0e2978` |
| `kn5000_waveform_rom.ic307` | `d779ac5782c63d5e911bf5c6559c6bd6` |

Do **not** use the copies under `custom_kn5000_roms/` — those are modified homebrew sets.

### 6. `kn7000_table_{even,odd}.rom` inside `roms/kn6000/` and `roms/kn6500/` — DO NOT "CLEAN"

These are **deliberate**, created by `publish-binary.sh` step 2a. The KN6000's own
table/font mask ROMs (IC13 `QSIGX3C16008` / IC14 `QSIGX3C16007`) and the KN6500's
(`C3FBMD000069` / `C3FBMD000068`) have **never been dumped**, and without a valid table
ROM those machines render no text at all. The driver therefore loads the *KN7000's*
table ROM into their `table` region, flagged `BAD_DUMP`, with `ROM_FILL(0x0, 0x200, 0xff)`
blanking the identity header (leaving it in place derails KN6000 boot to a black screen).
Because the `ROM_LOAD` entries name the `kn7000_table_*.rom` files, those files must
physically exist in each model's folder — hence the copies.

**Anything text-shaped on a KN6000/KN6500 screen is KN7000 data, not that model's own,
and must not be cited as KN6xxx-authentic.** Dumping IC13/IC14 is the real fix. Per the
project's cross-model ROM integrity policy, this substitution is an emulation hack,
documented as such, never presented as device history.

Retired: the old `kn6000_table_*.rom` / `kn6500_table_*.rom` files. They were never a
dump of IC13/IC14 — verified byte-for-byte that their low 1 MB simply reproduced the
program ROM's upper 1 MB (IK2/IKV2 loaded a second time) and their upper 1 MB was all
`0xFF`. They had zero emulation effect while wrongly implying IC13/IC14 had been dumped.
`publish-binary.sh` deletes them. `notes/mame-pr-rom-manifest.md` still lists their
hashes for the record; they are **not** part of the shipped set.

## Still undumped (not in the set, no recipe exists — and none is invented)

- KN7000 wave ROMs IC203/204/207/208 (`C3CBQD00000{1,2,3,4}`) — placeholder in §5.
- KN7000 rhythm-data flash (~4.1 MB) — placeholder in §4.
- KN7000 library/boot ROM at `0x4C000000` — *not* actually missing: boot copies it from
  the dumped program flash, so no separate file is needed.
- KN7000 picture flash at `0x57800000`.
- KN6000 IC13/IC14 and KN6500 IC13/IC14 table/font — placeholder in §6.

## Preservation notes

- The `.SLD` files are the primary source (see §3) and live under
  `kn7000_scratchpad_snapshot/` (kn6xxx, kn2400) and `KN7000/kn7-1{4,6}/` (kn7000).
  Note `kn7000_scratchpad_snapshot/` duplicates much of its content under a nested
  `scratchpad/` subdirectory; `make-roms.sh` uses the top-level paths as canonical.
- The genuine KN5000 wave dumps in `kn5000_original_roms/` are the donor for §5.
- Because every shipped ROM regenerates from the above, **no ROM file needs to be
  archived as a non-regenerable artifact.** What must be preserved is the *source* set:
  the `.SLD` files, the original `.zip` archives, and the KN5000 wave dumps.
