#!/bin/bash
# run_fdc_ab.sh <binary-before> <binary-after> <outdir> -- A/B of the floppy interrupt fix.
# For kn6000, kn6500, kn2400 and kn7000, runs fdc_irq_probe.lua for 12 s on each binary
# (visible windows) and prints FDC register reads and group-0x19 acks side by side.
set -u
A=$(readlink -f "$1"); B=$(readlink -f "$2"); OUT=$(readlink -m "$3")
HERE=$(dirname "$(readlink -f "$0")")
ROMS="${ROMS:-$HOME/compartilhado/technics_romsets}"   # ROMS= overrides (the overlay uses technics_roms/roms)
SD="$HOME/compartilhado/kn7000-emulator/sdcard_work.img"
one() {  # one <binary> <set> <dir>
	mkdir -p "$3" && cd "$3" || return
	local extra=()
	[ "$2" = kn7000 ] && { cp "$SD" "$3/sd.img"; extra=(-hard "$3/sd.img"); }
	timeout -k 10 300 "$1" "$2" -rompath "$ROMS" -video soft -sound none -nothrottle -skip_gameinfo \
		-nonvram_save -cfg_directory "$3/cfg" -nvram_directory "$3/nvram" -seconds_to_run 12 \
		-autoboot_script "$HERE/fdc_irq_probe.lua" "${extra[@]}" > "$3/stdout.txt" 2> "$3/stderr.txt"
	rm -f -- "$3/sd.img"
}
for s in kn6000 kn6500 kn2400 kn7000; do
	one "$A" "$s" "$OUT/before/$s" & one "$B" "$s" "$OUT/after/$s" & wait
done
printf '%-8s %-50s %s\n' set before after
for s in kn6000 kn6500 kn2400 kn7000; do
	printf '%-8s %-50s %s\n' "$s" "$(grep -h 'FDC register' "$OUT/before/$s/stdout.txt" | sed 's/\[fdc\] //')" \
		"$(grep -h 'FDC register' "$OUT/after/$s/stdout.txt" | sed 's/\[fdc\] //')"
done
