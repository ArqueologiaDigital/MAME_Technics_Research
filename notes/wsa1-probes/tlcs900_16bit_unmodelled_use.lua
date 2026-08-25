-- DOES ANY TECHNICS FIRMWARE ACTUALLY USE THE PARTS OF THE 16-BIT TIMERS THAT
-- ARE STILL NOT MODELLED?
--
-- QUESTION IT ANSWERS: after OVERLAY FIX 2/3 the counters, the compares, CLE
-- and the stop-clear are all in.  Four things are still missing, and the honest
-- choice between "implement it" and "write it down as a gap" is a measurement,
-- not a guess.  This probe watches every one of them on a live machine:
--
--   CAPTURE REGISTERS.  CAP1/CAP2 read back at internal I/O 0x34-0x37 and
--     CAP3/CAP4 at 0x44-0x47 (tmp95c061.cpp's internal_mem map), and nothing
--     ever writes m_t16_cap, so they return 0 forever.  If firmware READS one,
--     it is being fed a fabricated zero and the gap is load-bearing.
--   SOFTWARE CAPTURE.  Databook Figure 3.9 (4) p.96: writing 0 to T4MOD bit 5
--     <CAP1IN> loads the up-counter into CAP1 (T5MOD bit 5 <CAP3IN> -> CAP3);
--     the bit always READS as 1.  A write to 0x38/0x48 with bit 5 clear is a
--     capture request.
--   PIN-TRIGGERED CAPTURE + EXTERNAL CLOCK.  T4MOD/T5MOD bits 4:3
--     <CAP12M1,0> select the TI4/TI5 edge that latches CAP1/CAP2, and bits 1:0
--     = 00 clocks the counter from the TI4/TI6 pin instead of the prescaler.
--     Both need a pin this driver does not wire, so a non-zero <CAP12M> or a
--     clock-select of 00 after boot means the gap is load-bearing.
--   OUTPUT FLIP-FLOPS.  T4FFCR (0x39) / T5FFCR (0x49) drive TFF4/TFF5/TFF6 out
--     to the TO4/TO5/TO6 pins and are what 16-bit PPG mode is built from.  A
--     non-zero write is a request this device cannot honour.
--   T45CR (0x3A).  Figure 3.9 (9) p.101: b0/b1 are the TREG4/TREG6 double-
--     buffer enables, b2/b3 the pattern-generator shift triggers.  Stored and
--     never decoded.  A non-zero write means that is no longer exact.
--
-- The taps are on the CPU program space, where the internal I/O block lives.
--
-- RUN (both TMP95C061 machines):
--   cd ~/compartilhado/kn7000_mame_build
--   for m in wsa1r kn1500; do DISPLAY=:0 ./kn7000 $m -rompath ./roms \
--     -skip_gameinfo -str 60 -window -autoboot_script \
--     ~/compartilhado/kn7000_mame/notes/wsa1-probes/tlcs900_16bit_unmodelled_use.lua ; done
--   (the SX-WSA1R has two TMP95C061; CPUTAG picks which one, default cpu1)
--
-- READING IT: every counter at 0 means the four gaps are genuinely unreachable
-- on this machine and documenting them is exact.  Any non-zero counter is a
-- fabricated value being handed to firmware and has to be implemented.

local tag = os.getenv("CPUTAG")
if tag == nil then
	tag = manager.machine.devices[":cpu1"] and ":cpu1" or ":maincpu"
end
local sp = manager.machine.devices[tag].spaces["program"]

_G.c = { cap12r = 0, cap34r = 0, softcap = 0, extclk = 0, capmode = 0,
         ffcr = 0, t45cr = 0 }
_G.detail = {}
_G.taps = {}
local function seen(what, s)
	if _G.detail[what] == nil then
		_G.detail[what] = s
		print(string.format("!! %s : %s", what, s))
	end
end

_G.taps[1] = sp:install_read_tap(0x000034, 0x000037, "cap12",
	function (o, d, m) _G.c.cap12r = _G.c.cap12r + 1
		seen("CAP1/CAP2 READ", string.format("offset %06X pc=%06X", o,
			manager.machine.devices[tag].state["CURPC"].value)) return d end)
_G.taps[2] = sp:install_read_tap(0x000044, 0x000047, "cap34",
	function (o, d, m) _G.c.cap34r = _G.c.cap34r + 1
		seen("CAP3/CAP4 READ", string.format("offset %06X pc=%06X", o,
			manager.machine.devices[tag].state["CURPC"].value)) return d end)

-- T4MOD (0x38) and T5MOD (0x48) share a word with T4FFCR (0x39) / T5FFCR (0x49)
local function modtap(base, name)
	return sp:install_write_tap(base, base + 1, name,
		function (o, d, m)
			if (m & 0x00ff) ~= 0 then
				local v = d & 0xff
				if (v & 0x20) == 0 then _G.c.softcap = _G.c.softcap + 1
					seen(name .. " SOFTWARE CAPTURE", string.format("wrote %02X", v)) end
				if (v & 0x03) == 0 then _G.c.extclk = _G.c.extclk + 1
					seen(name .. " EXTERNAL CLOCK", string.format("wrote %02X", v)) end
				if (v & 0x18) ~= 0 then _G.c.capmode = _G.c.capmode + 1
					seen(name .. " PIN CAPTURE MODE", string.format("wrote %02X", v)) end
			end
			if (m & 0xff00) ~= 0 then
				local v = (d >> 8) & 0xff
				if v ~= 0 then _G.c.ffcr = _G.c.ffcr + 1
					seen(name:gsub("MOD", "FFCR") .. " NON-ZERO", string.format("wrote %02X", v)) end
			end
			return d
		end)
end
_G.taps[3] = modtap(0x000038, "T4MOD")
_G.taps[4] = modtap(0x000048, "T5MOD")

-- T45CR is 0x3A, the low byte of the 0x3A word
_G.taps[5] = sp:install_write_tap(0x00003a, 0x00003b, "t45cr",
	function (o, d, m)
		if (m & 0x00ff) ~= 0 and (d & 0xff) ~= 0 then
			_G.c.t45cr = _G.c.t45cr + 1
			seen("T45CR NON-ZERO", string.format("wrote %02X", d & 0xff))
		end
		return d
	end)

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 600) ~= 0 then return end
	print(string.format(
		"t=%6.2f [%s] CAP12r=%d CAP34r=%d softcap=%d extclk=%d capmode=%d ffcr=%d t45cr=%d",
		manager.machine.time:as_double(), tag,
		_G.c.cap12r, _G.c.cap34r, _G.c.softcap, _G.c.extclk, _G.c.capmode,
		_G.c.ffcr, _G.c.t45cr))
end)
