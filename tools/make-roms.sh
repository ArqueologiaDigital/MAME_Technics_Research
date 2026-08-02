#!/usr/bin/env bash
# make-roms.sh -- the SINGLE documented path from preserved sources to the MAME ROM set.
#
# ★ THE AUTHORITATIVE COPY OF EVERY ROM NOW LIVES IN ITS OWN PRIVATE GIT REPO:
#       /home/fsanches/compartilhado/technics_roms
#   That repo is the source of truth. The build tree and the published
#   kn7000-emulator/ folder are DERIVED copies. See its README for full provenance,
#   the integrity manifest, and the do-not-publish privacy guard.
#
# Every .rom file the kn7000/kn6000/kn6500/kn2400 drivers load is either
#   (a) REGENERABLE -- rebuilt bit-identically by this script from a preserved source, or
#   (b) DERIVED     -- a copy of another file in the set (the KN6xxx table placeholder).
# Verified 2026-07-20: all 14 rebuild bit-identically. Nothing is unreconstructable.
#
# WHY THIS EXISTS: the build tree (kn7000_mame_build/) is DISPOSABLE -- build.sh recreates
# it and it is not version-controlled -- while tools/publish-binary.sh copies ROMs ONE WAY
# out of it and never deletes. When the build tree lost its ROMs, the published folder
# silently became the only surviving copy of several images and publish just shipped stale
# ones. This script makes the set reproducible instead of merely present.
#
# Usage:
#   tools/make-roms.sh check      # verify the build tree against the expected md5s
#   tools/make-roms.sh generate   # rebuild every regenerable ROM from preserved sources
#   tools/make-roms.sh restore    # populate the build tree from the technics_roms repo
#   tools/make-roms.sh list       # print the manifest (file, model, md5, regenerable?)
#
# Full provenance -- what each file IS and where it came from -- is notes/rom-provenance.md
# and, in more detail, technics_roms/README.md.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
SHARE=/home/fsanches/compartilhado
BUILD="${BUILD_TREE:-$SHARE/kn7000_mame_build}"
DEST="${PUBLISH_DIR:-$SHARE/kn7000-emulator}"
ROMS="$BUILD/roms"
# The authoritative, git-versioned home of every ROM artifact (private repo, never pushed).
ROMREPO="${TECHNICS_ROMS:-$SHARE/technics_roms}"

# Preserved sources.
EXTRACT="$SHARE/kn7000_extraction"          # KN7000 .SLD -> linear .rom (+ its own venv)
PY="$EXTRACT/venv/bin/python"               # needs the 'pylzss' module
DISKS="$SHARE/KN7000"                       # kn7-16/ and kn7-14/ update-disk file trees
SNAP="$SHARE/kn7000_scratchpad_snapshot"    # preserved .SLD for KN6000/KN6500/KN2400
KN5000_ROMS="$SHARE/kn5000_original_roms/kn5000"   # GENUINE KN5000 wave dumps (donor)
WAVES_DIR="$SNAP/session-c6cf97f4-2026-07-16/kn5000_waves"  # extracted donor waves

# ---------------------------------------------------------------------------
# Manifest: md5  model  filename  regenerable-kind
#   sld     = decompress preserved .SLD -> concatenate -> even/odd split
#   synth   = deterministic generator script in tools/
#   derived = byte copy of another file already in the set
# ---------------------------------------------------------------------------
read -r -d '' MANIFEST <<'EOF' || true
5b085ad9269750fddb5faa4d69eb5ac7 kn7000 kn7000_program_even.rom      sld
102cfa7773b087271726107ade5c7183 kn7000 kn7000_program_odd.rom       sld
38079d4c334c46dca061a6339739dbbf kn7000 kn7000_program.rom           sld
ccdfdad619d6740f6f1754d0432d22eb kn7000 kn7000_table_even.rom        sld
cda9079ed33867454745903f91addc6d kn7000 kn7000_table_odd.rom         sld
aaae68589e59f98bc2a521be1c851dec kn7000 kn7000_table.rom             sld
73c9e155defedf0b60b245ba8ba67bcf kn7000 kn7000_rhythms_synthetic.rom synth
70f62157c898143bd09ef4544ba6f4f1 kn7000 kn7000_waves_synthetic.rom   synth
9e4a020ef87bffd7a5003c380260cd59 kn6000 kn6000_program_even.rom      sld
291b6caee074bdeef26db51673e7062d kn6000 kn6000_program_odd.rom       sld
5a6cb22b70f61ac7ffc6f37ec3f9432d kn6500 kn6500_program_even.rom      sld
d2442b2c68024da9dd2d0bdb731212b3 kn6500 kn6500_program_odd.rom       sld
8d9c67eab4d1067c96395f0069493fc7 kn2400 kn2400_program_even.rom      sld
ed67066933a236cfb569890a847f09a2 kn2400 kn2400_program_odd.rom       sld
EOF

# Files publish-binary.sh DERIVES into the KN6xxx set (deliberate BAD_DUMP placeholder --
# the KN7000's table/font ROM standing in for the never-dumped KN6xxx IC13/IC14).
# Documented here so nobody "cleans up" what looks like a stray KN7000 file.
read -r -d '' DERIVED <<'EOF' || true
ccdfdad619d6740f6f1754d0432d22eb kn6000 kn7000_table_even.rom
cda9079ed33867454745903f91addc6d kn6000 kn7000_table_odd.rom
ccdfdad619d6740f6f1754d0432d22eb kn6500 kn7000_table_even.rom
cda9079ed33867454745903f91addc6d kn6500 kn7000_table_odd.rom
EOF

fail=0
note() { printf '  %s\n' "$*"; }

# ---------------------------------------------------------------------------
cmd_list() {
  printf '%-32s %-7s %-6s %s\n' FILE MODEL KIND MD5
  while read -r md5 model file kind; do
    [ -n "${md5:-}" ] || continue
    printf '%-32s %-7s %-6s %s\n' "$file" "$model" "$kind" "$md5"
  done <<< "$MANIFEST"
  echo
  echo "DERIVED by publish-binary.sh (KN7000 table ROM as the KN6xxx BAD_DUMP font placeholder):"
  while read -r md5 model file; do
    [ -n "${md5:-}" ] || continue
    printf '%-32s %-7s %-6s %s\n' "$file" "$model" derived "$md5"
  done <<< "$DERIVED"
}

# ---------------------------------------------------------------------------
cmd_check() {
  local root="${1:-$ROMS}"
  echo "checking ROM set under $root"
  while read -r md5 model file kind; do
    [ -n "${md5:-}" ] || continue
    local p="$root/$model/$file"
    if [ ! -f "$p" ]; then
      note "MISSING  $model/$file    ($kind)"; fail=1; continue
    fi
    local got; got=$(md5sum < "$p" | cut -d' ' -f1)
    if [ "$got" = "$md5" ]; then
      note "ok       $model/$file"
    else
      note "MISMATCH $model/$file  got $got want $md5"; fail=1
    fi
  done <<< "$MANIFEST"
  if [ "$fail" != 0 ]; then
    echo
    echo "ROM set is INCOMPLETE or ALTERED. Rebuild with:  tools/make-roms.sh generate"
    echo "(or, if the published folder still has them:      tools/make-roms.sh restore)"
    echo "Provenance for every file: notes/rom-provenance.md"
    return 1
  fi
  echo "ROM set complete and byte-exact."
}

# ---------------------------------------------------------------------------
cmd_restore() {
  # Prefer the authoritative repo; fall back to the published folder only if it is absent.
  local src="$ROMREPO/roms" what="technics_roms repo"
  if [ ! -d "$src" ]; then
    src="$DEST/roms"; what="published folder (FALLBACK -- technics_roms repo missing!)"
    echo "warning: authoritative repo not found at $ROMREPO -- falling back to $DEST"
  fi
  echo "restoring build-tree ROMs from the $what: $src"
  [ -d "$src" ] || { echo "error: no ROM set at $src"; exit 1; }
  while read -r md5 model file kind; do
    [ -n "${md5:-}" ] || continue
    mkdir -p "$ROMS/$model"
    if [ -f "$ROMS/$model/$file" ]; then
      note "have     $model/$file"
    elif [ -f "$src/$model/$file" ]; then
      cp -p "$src/$model/$file" "$ROMS/$model/$file"
      note "restored $model/$file"
    else
      note "ABSENT   $model/$file  -- not in $src either; use 'generate'"
      fail=1
    fi
  done <<< "$MANIFEST"
  [ "$fail" = 0 ] || { echo "restore incomplete"; exit 1; }
  cmd_check
}

# ---------------------------------------------------------------------------
# KN7000: decompress the two-floppy .SLD pairs and split into even/odd chips.
# kn7000_extract.py verifies the result against the manufacturer's own SMCK*.INF
# checksum oracle (total byte-sum + 16 per-block sums), so a successful run is
# self-validating.
gen_kn7000_flash() {
  echo "== kn7000 program/table (from the kn7-16 / kn7-14 update disks)"
  [ -x "$PY" ] || { echo "error: no extraction venv at $PY (cd $EXTRACT && python3 -m venv venv && venv/bin/pip install -r requirements.txt)"; exit 1; }
  [ -d "$DISKS/kn7-16" ] || { echo "error: update-disk tree not found at $DISKS/kn7-16"; exit 1; }
  local tmp; tmp=$(mktemp -d)
  ( cd "$EXTRACT" && "$PY" kn7000_extract.py "$DISKS" "$tmp" )
  mkdir -p "$ROMS/kn7000"
  local b
  for b in program table; do
    ( cd "$EXTRACT" && "$PY" rom_split_evenodd.py "$tmp/kn7000_$b.rom" 0x400000 \
        "$ROMS/kn7000/kn7000_${b}_even.rom" "$ROMS/kn7000/kn7000_${b}_odd.rom" )
    cp -f "$tmp/kn7000_$b.rom" "$ROMS/kn7000/kn7000_$b.rom"
  done
  rm -rf "$tmp"
}

# KN6000 / KN6500 / KN2400: same container. The .SLD files themselves are the preserved
# source (see notes/rom-provenance.md on why the self-extracting .exe -> .SLD step is NOT
# scripted here).
#
# CORRECTION 2026-08-02: this used to say "no .INF oracle shipped". That was wrong -- all
# three ship one, in the same format as the KN7000's, but inside the .exe rather than at
# the top level of the .zip, which is why it had been missed. They are now preserved in
# technics_roms/sources/<model>/ and all three verify exactly (total + every 0x40000
# block, over the unpadded linear image):
#   kn6000 SMCKPR1.INF  0x166ADB67  16/16
#   kn6500 SMCKPV1.INF  0x157ED142  15/15
#   kn2400 SMCKPR1.INF  0x16DA58C4  15/15
gen_sld_model() {
  local model="$1" s1="$2" s2="$3"
  echo "== $model program (from $(basename "$s1") + $(basename "$s2"))"
  [ -x "$PY" ] || { echo "error: no extraction venv at $PY"; exit 1; }
  [ -f "$s1" ] && [ -f "$s2" ] || { echo "error: preserved .SLD missing ($s1 / $s2)"; exit 1; }
  mkdir -p "$ROMS/$model"
  "$PY" - "$model" "$s1" "$s2" "$ROMS/$model" <<'PY'
import sys, lzss
model, s1, s2, out = sys.argv[1:5]

def dec(path):
    d = open(path, "rb").read()
    want = int.from_bytes(d[8:11], "big")          # 24-bit BE decompressed size
    raw = lzss.decompress(data=d[11:], initial_buffer_values=0)   # 4K window, zero-filled
    assert len(raw) == want, "%s: got 0x%X want 0x%X" % (path, len(raw), want)
    print("  %s magic=%s -> 0x%X" % (path.split("/")[-1], d[:8].decode("latin1").strip("\0"), len(raw)))
    return raw

lin = dec(s1) + dec(s2)
print("  linear 0x%X bytes -> even/odd 16-bit word split, 0xFF-padded to 0x400000" % len(lin))
lin += b"\xff" * (0x400000 - len(lin))
ev = bytearray(); od = bytearray()
for i in range(0, len(lin), 4):
    ev += lin[i:i+2]; od += lin[i+2:i+4]
for nm, data in (("even", ev), ("odd", od)):
    open("%s/%s_program_%s.rom" % (out, model, nm), "wb").write(bytes(data))
PY
}

gen_synthetics() {
  echo "== kn7000 synthetic rhythm resource (deterministic; NOT a dump)"
  python3 "$HERE/gen_technics_rhythms.py" \
    --table "$ROMS/kn7000/kn7000_table.rom" \
    --prog "$SNAP/kn7000_program_decompressed.bin" \
    --out "$ROMS/kn7000/kn7000_rhythms_synthetic.rom"

  echo "== kn7000 synthetic wave pack (deterministic; donor = GENUINE KN5000 dumps; NOT a dump)"
  if [ ! -f "$WAVES_DIR/manifest.json" ]; then
    echo "  donor wave extraction missing -- rebuilding from $KN5000_ROMS"
    python3 "$HERE/extract_kn5000_waves.py" \
      --roms "$KN5000_ROMS"/kn5000_waveform_rom.ic30{4,5,6,7} \
      --outdir "$WAVES_DIR"
  fi
  python3 "$HERE/make_wave_pack.py" --waves "$WAVES_DIR" \
    --out "$ROMS/kn7000/kn7000_waves_synthetic.rom"
}

cmd_generate() {
  gen_kn7000_flash
  gen_sld_model kn6000 "$SNAP/kn6probe/IK1.SLD"  "$SNAP/kn6probe/IK2.SLD"
  gen_sld_model kn6500 "$SNAP/kn6probe/IKV1.SLD" "$SNAP/kn6probe/IKV2.SLD"
  gen_sld_model kn2400 "$SNAP/kn24/LKG1.SLD"     "$SNAP/kn24/LKG2.SLD"
  gen_synthetics
  echo
  cmd_check
}

case "${1:-check}" in
  check)    cmd_check "${2:-$ROMS}" ;;
  generate) cmd_generate ;;
  restore)  cmd_restore ;;
  list)     cmd_list ;;
  *) echo "usage: $0 {check|generate|restore|list}"; exit 2 ;;
esac
