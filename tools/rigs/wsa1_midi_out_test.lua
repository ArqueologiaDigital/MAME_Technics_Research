-- WSA1R MIDI OUT (SC0 transmit) end-to-end test.
--
-- QUESTION THIS ANSWERS: does a byte the firmware writes to CPU 1's SC0BUF now
-- leave the machine as bit-serial MIDI?  Until this session sc0buf_w() only
-- faked "send complete"; it now hands each byte to sc0_txd(), which the driver
-- shifts out (byte -> bits, 31250 baud) through wsa1_midi_uart into a midiout
-- port.  This injects a known byte sequence straight into SC0BUF (CPU 1 internal
-- register 0x50) and you capture the port to a file to confirm the bytes arrive.
--
-- MAME's midiout is a PortMidi device (a real MIDI port), NOT a file writer, so
-- capture from a port instead.  On a box with no rawmidi, route to the ALSA
-- "Midi Through" port and read it with aseqdump:
--
--   aseqdump -p 14:0 &                          # capture the Midi Through port
--   ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \
--       -mdout midiout -midiout "Midi Through Port-0" \
--       -autoboot_script tools/rigs/wsa1_midi_out_test.lua -seconds_to_run 8
--
-- The injected bytes are the firmware's own GM-On template (prom_b 0xF4FEE8),
-- so the capture is a real, valid MIDI message, not an invented one.
--
-- MEASURED 2026-09-06 (aseqdump on 14:0): the injected
--   14:0  System exclusive  F0 7E 7F 09 01 F7
-- arrived, AND the firmware's own power-on MIDI came out unprompted -- 13 Active
-- Sensing, 8 Control Change (a controller reset), 1 Pitch bend, 1 aftertouch --
-- proving SC0 transmit is live end to end: SC0BUF -> sc0buf_w -> sc0_txd ->
-- wsa1_midi_uart (byte->bits, 31250 baud) -> midiout port.

local fired  = false
local frames = 0

_G._wsa1mout = emu.add_machine_frame_notifier(function()
	frames = frames + 1
	if fired or frames < 120 then return end   -- let SC0 get configured first
	fired = true

	local sp = manager.machine.devices[":cpu1"].spaces["program"]
	local gm_on = { 0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7 }   -- GM System On
	for _, b in ipairs(gm_on) do
		sp:write_u8(0x50, b)                                -- SC0BUF -> sc0buf_w -> sc0_txd
	end
	print("WSA1R-MIDI-OUT-TEST: wrote GM System On to SC0BUF")
end)
