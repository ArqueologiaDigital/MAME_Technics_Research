-- WSA1R live parameter mirror (tempo) end-to-end test.
--
-- QUESTION THIS ANSWERS: with the "Live parameter mirror" special mode ON, does
-- changing the tempo on the emulated WSA1R transmit the exact tempo SysEx that a
-- real unit's own receive parser accepts?  The message (traced from the firmware,
-- command 0x25 -> live slot 9 -> 0xFB33FE, value=(H<<4)|L, store 0x7EE2/0x7EE3):
--     F0 50 25 <BPM & 0x0F> <BPM >> 4> F7
--
-- This turns the LIVESYNC port on, then writes three known BPMs straight into the
-- tempo store (standing in for a panel edit); the ~30 Hz mirror poll picks each
-- up and transmits it.  Capture MIDI OUT and compare:
--     120 (0x078) -> F0 50 25 08 07 F7
--     200 (0x0C8) -> F0 50 25 08 0C F7
--     300 (0x12C) -> F0 50 25 0C 12 F7   (9-bit: 0x7EE3 bit 0 = 1)
--
-- RUN (no host rawmidi needed -- route to ALSA Midi Through and read it):
--   aseqdump -p 14:0 &
--   ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \
--       -mdout midiout -midiout "Midi Through Port-0" \
--       -autoboot_script tools/rigs/wsa1_livesync_test.lua -seconds_to_run 12
--   # aseqdump should show three System Exclusive lines, the bytes above.

local step   = 0
local frames = 0
local bpms   = { 0x078, 0x0C8, 0x12C }   -- 120, 200, 300

_G._wsa1ls = emu.add_machine_frame_notifier(function()
	frames = frames + 1
	if frames < 120 then return end               -- let the machine settle

	-- Turn the special mode ON once (PORT_CONFNAME field on :LIVESYNC).
	if step == 0 then
		local port = manager.machine.ioport.ports[":LIVESYNC"]
		for _, f in pairs(port.fields) do f:set_value(1) end
		step = 1
		return
	end

	-- Every ~40 frames, write the next BPM into the tempo store (0x7EE2 low 8,
	-- 0x7EE3 bit 0 = bit 8).  The mirror poll transmits the matching SysEx.
	if (frames % 40) ~= 0 then return end
	local idx = step
	if idx > #bpms then return end
	local bpm = bpms[idx]
	local sp = manager.machine.devices[":cpu1"].spaces["program"]
	sp:write_u8(0x7ee2, bpm & 0xff)
	sp:write_u8(0x7ee3, (sp:read_u8(0x7ee3) & 0xfe) | ((bpm >> 8) & 1))
	print(string.format("WSA1R-LIVESYNC-TEST: wrote BPM %d -> expect F0 50 25 %02X %02X F7",
		bpm, bpm & 0x0f, bpm >> 4))
	step = step + 1
end)
