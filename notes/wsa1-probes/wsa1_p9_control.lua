-- CONTROL for the P9/DSPRDY fix: put CPU 2's port 9 back to what an unbound
-- MAME port read used to give (0), then run another probe on top.
-- (SX-WSA1R, 2026-08-27)
--
-- QUESTION IT ANSWERS: "would this have worked before cpu2_p9_r() existed?"
-- A read tap runs AFTER the port handler and its return value replaces the
-- data, so masking bits 0 and 3 off reproduces the old behaviour exactly,
-- in the same binary, with no rebuild and no second source tree.
--
-- Point CHAIN at another autoboot script to run it under this control:
--   CHAIN=.../wsa1_keybed_note.lua DISPLAY=:0 ./kn7000 wsa1 -rompath ./roms \
--       -skip_gameinfo -window -str 95 -autoboot_delay 1 \
--       -autoboot_script .../wsa1_p9_control.lua
local m = manager.machine
_G.wsa1_p9ctl = m.devices[":cpu2"].spaces["program"]:install_read_tap(
	0x000018, 0x000019, "p9ctl", function (off, data, mask)
		return data & ~0x0900          -- byte 0x19 (odd lane): clear bits 3 and 0
	end)
local chain = os.getenv("CHAIN")
if chain then dofile(chain) end
