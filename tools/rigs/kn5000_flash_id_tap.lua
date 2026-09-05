-- kn5000_flash_id_tap.lua -- read the KN5000 boot-time flash autoselect IDs.
--
-- Question it answers: did Flash_InitAllBanks (v10 boot/system_handlers.s:6466)
-- actually read a valid JEDEC device ID from the two flash banks, or did it fall
-- back to 0xFFFF because the region was mapped as plain ROM?
--
-- Flash_IdentifyAndValidateChip stores bank 1's ID (custom_data @ 0x300000, IC19)
-- at DRAM word 0x0205E0 and bank 2's ID (the HD-AE5000 card @ 0x280000) at 0x0205E2.
-- Accepted IDs are {0x2223, 0x22AB, 0x22D6, 0x2258} (Am29F400/800 T/B); anything
-- else stores 0xFFFF. With no extension card present, bank 2 = 0xFFFF is CORRECT.
--
--   SNAP_AT=8 ./kn7000 kn5000 -rompath ./roms -skip_gameinfo -window \
--       -autoboot_script tools/rigs/kn5000_flash_id_tap.lua
--
-- Prints one line to stderr after AT emulated seconds, then exits:
--   FLASHID 0205E0=xxxx 0205E2=xxxx
--
-- Reads through the maincpu program space (little-endian 16-bit read).
-- Held in a global (MAME's Lua GC collects a notifier kept only in a local).

local mac = manager.machine
local AT = tonumber(os.getenv("SNAP_AT")) or 8

_G.FLASHID = _G.FLASHID or {}

_G.FLASHID.h = emu.add_machine_frame_notifier(function()
	if _G.FLASHID.done then return end
	if mac.time.seconds < AT then return end
	_G.FLASHID.done = true
	local sp = mac.devices[":maincpu"].spaces["program"]
	local a = sp:read_u16(0x0205e0)
	local b = sp:read_u16(0x0205e2)
	emu.print_error(string.format("FLASHID 0205E0=%04X 0205E2=%04X", a, b))
	mac:exit()
end)
