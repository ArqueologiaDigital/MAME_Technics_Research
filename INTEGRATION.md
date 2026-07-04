# Integrating into a MAME tree

These files are an overlay: each sits at the path it occupies inside MAME. To
build them into a MAME checkout:

## 1. Copy the files in

```
cp -r src/devices/cpu/mn10300/mn10300.{h,cpp}  <mame>/src/devices/cpu/mn10300/
cp    src/mame/matsushita/kn7000.cpp           <mame>/src/mame/matsushita/
```

`src/devices/cpu/mn10300/mn103dasm.{cpp,h}` (the disassembler) already exists in
MAME and is reused unchanged.

## 2. Promote the MN10300 from disassembler-only to a full CPU

In `scripts/src/cpu.lua`, the MN10300 is currently registered as a disassembler
only. Replace that block with a full-CPU block (mirroring the MN10200 one):

```lua
--------------------------------------------------
-- Panasonic MN10300
--@src/devices/cpu/mn10300/mn10300.h,CPUS["MN10300"] = true
--------------------------------------------------
if CPUS["MN10300"] then
	files {
		MAME_DIR .. "src/devices/cpu/mn10300/mn10300.cpp",
		MAME_DIR .. "src/devices/cpu/mn10300/mn10300.h",
	}
end
if opt_tool(CPUS, "MN10300") then
	table.insert(disasm_files, MAME_DIR .. "src/devices/cpu/mn10300/mn103dasm.cpp")
	table.insert(disasm_files, MAME_DIR .. "src/devices/cpu/mn10300/mn103dasm.h")
end
```

## 3. Register the driver

Add the KN7000 to `src/mame/mame.lst` (in the `matsushita` section, next to
`kn5000`):

```
kn7000
```

and, if your MAME version uses per-folder source lists, ensure
`src/mame/matsushita/kn7000.cpp` is picked up the same way `kn5000.cpp` is.

## 4. Provide the ROM images

MAME will look for a `kn7000` romset containing `kn7000_program.rom` and
`kn7000_table.rom` — the decompressed `.SLD` images produced by the
`kn7000_extraction` tool. Place them in a `kn7000.zip` (or a `roms/kn7000/`
folder) on your ROM path. Their CRC/SHA1 are already filled in the driver
(flagged `BAD_DUMP` because they are reconstructed from the update disks rather
than read from the physical flash).

## 5. Build and run

```
make SUBTARGET=kn7000 SOURCES=src/mame/matsushita/kn7000.cpp   # focused build
./kn7000 kn7000 -debug                                          # step the boot code
```

Expect the CPU to start fetching at `0x48400000` (`jmp 0x4840FF7E`). The execute
core currently implements only a first batch of instructions, so it will soon
hit an `unimplemented opcode` log entry — that is the current frontier of the
work.
