-- Verify the WSA1R DSP device's I-RAM in-emulator (WSA1R_ENABLE_DSP=1 build).
--
-- QUESTION THIS ANSWERS: with the three uPD6383GF devices instantiated and fed
-- the real upload via host_w, does the device's I-RAM end up holding the actual
-- microcode?  The capture->corpus match was proven OFFLINE (dsp_verify_upload.py,
-- 63/63); this confirms host_w parses the same stream INSIDE the emulator.
--
-- It reads dsp2 (IC30, which receives the program block at DSP addr 0x30) I-RAM
-- and prints the first words + a non-zero count.  The uPD6383 I-RAM is the
-- program space, byte-addressed, word N at byte 5N (384 x 5 bytes).  Word 0x30
-- must read 0x08010C0821 (the first word of the block, per dsp_verify_upload.py).
--
-- RUN (needs a WSA1R_ENABLE_DSP=1 build):
--   ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \
--       -autoboot_script tools/rigs/wsa1_dsp_iram_verify.lua -seconds_to_run 25

local frames = 0
local done   = false

_G._wsa1dspv = emu.add_machine_frame_notifier(function()
	frames = frames + 1
	if done or frames < 900 then return end     -- let the upload finish (~15 s)
	done = true

	local dsp = manager.machine.devices[":dsp2"]
	if not dsp then print("WSA1R-DSP-VERIFY: no :dsp2 device (build without WSA1R_ENABLE_DSP=1?)"); return end
	local sp = dsp.spaces["iram"]               -- AS_IRAM, name "iram" (8-bit, byte-addressed)
	if not sp then print("WSA1R-DSP-VERIFY: dsp2 has no iram space"); return end

	local function word(n)
		local b = n * 5
		return string.format("%02X%02X%02X%02X%02X",
			sp:read_u8(b), sp:read_u8(b+1), sp:read_u8(b+2), sp:read_u8(b+3), sp:read_u8(b+4))
	end

	print("WSA1R-DSP-VERIFY: dsp2 I-RAM word 0x30 = " .. word(0x30) .. "  (expect 08010C0821)")
	local s = {}
	for i = 0x30, 0x35 do s[#s+1] = word(i) end
	print("WSA1R-DSP-VERIFY: words 0x30..0x35 = " .. table.concat(s, " "))
	local nz = 0
	for i = 0, 383 do if word(i) ~= "0000000000" then nz = nz + 1 end end
	print("WSA1R-DSP-VERIFY: non-zero I-RAM words = " .. nz .. " / 384")
end)
