-- Verify the WSA1R DSP devices' C-RAM in-emulator (WSA1R_ENABLE_DSP=1 build).
--
-- QUESTION THIS ANSWERS: with the three uPD6383GF devices instantiated and fed
-- the real upload, does the driver's coefficient de-framer (wsa1.cpp dsp_deframe)
-- load each device's on-chip C-RAM with the ACTUAL coefficients?  The offline
-- de-frame was proven against the known constants (dsp_deframe.py / dsp_cram_map.py,
-- golden-cram-map-boot.txt); this confirms the SAME map lands in C-RAM INSIDE the
-- emulator, through the device's cram_ptr_w/cram_data_w host methods.
--
-- The uPD6383 C-RAM is a 256 x 24-bit space named "cram" (32-bit, -2 shift); it is
-- indexed by CELL (0..255) exactly as the device's m_cram.read_dword(cell) does, so
-- lua reads it as sp:read_u32(cell).  The value is 24-bit, masked from the dword.
--
-- GOLDEN ANCHORS (dsp_cram_map.py on a 30 s boot capture, K-TAG routing -- values
-- routed by their own K tag: only K=0x26 lands in C-RAM).  The at-boot split is
-- IC6 81 / IC5 56 / IC30 0 C-RAM cells; IC30 gets NO C-RAM at boot (only a program
-- block + a few D-RAM-register values), so its C-RAM must be EMPTY.
--   IC6 (dsp0): cell 0x00 = 0x000072 (chorusLFO), 0x6B = 0x400000 (0.5), 0x77 = 0x400000
--   IC5 (dsp1): cell 0xC1 = 0x400000 (0.5), 0xD5 = 0x400000 (0.5)
--   IC30(dsp2): C-RAM empty (non-zero count must be 0)
--
-- RUN (needs a WSA1R_ENABLE_DSP=1 build):
--   ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \
--       -autoboot_script tools/rigs/wsa1_dsp_cram_verify.lua -seconds_to_run 25

local frames = 0
local done   = false

local NAMES   = { [0]="IC6", [1]="IC5", [2]="IC30" }
local ANCHORS = {
	[0] = { {0x00, 0x000072, "chorusLFO"}, {0x6B, 0x400000, "0.5"}, {0x77, 0x400000, "0.5"} },
	[1] = { {0xC1, 0x400000, "0.5"}, {0xD5, 0x400000, "0.5"} },
	[2] = { },   -- IC30: no C-RAM at boot; checked via the non-zero count == 0 below
}
local EXPECT_EMPTY = { [2] = true }

_G._wsa1cramv = emu.add_machine_frame_notifier(function()
	frames = frames + 1
	if done or frames < 900 then return end     -- let the upload finish (~15 s)
	done = true

	local all_ok = true
	for d = 0, 2 do
		local dsp = manager.machine.devices[":dsp" .. d]
		if not dsp then
			print("WSA1R-CRAM-VERIFY: no :dsp" .. d .. " (build without WSA1R_ENABLE_DSP=1?)")
			return
		end
		local sp = dsp.spaces["cram"]
		local nz = 0
		for c = 0, 255 do
			if (sp:read_u32(c) & 0xFFFFFF) ~= 0 then nz = nz + 1 end
		end
		local anchors_ok = true
		local detail = {}
		for _, a in ipairs(ANCHORS[d]) do
			local got = sp:read_u32(a[1]) & 0xFFFFFF
			local ok = (got == a[2])
			anchors_ok = anchors_ok and ok
			detail[#detail+1] = string.format("cram[0x%02X]=%06X %s(%s)", a[1], got,
				ok and "OK" or "FAIL!=", a[3])
		end
		if EXPECT_EMPTY[d] then
			local ok = (nz == 0)
			anchors_ok = anchors_ok and ok
			detail[#detail+1] = (ok and "EMPTY-OK" or "FAIL: expected empty C-RAM")
		end
		all_ok = all_ok and anchors_ok
		print(string.format("WSA1R-CRAM-VERIFY: dsp%d/%-4s  non-zero C-RAM = %3d/256   %s",
			d, NAMES[d], nz, table.concat(detail, "  ")))
	end
	print("WSA1R-CRAM-VERIFY: " .. (all_ok and "PASS -- C-RAM holds the golden coefficients"
		or "FAIL -- see mismatched anchors above"))
end)
