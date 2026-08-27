-- QUESTION: when the WSA1 firmware puts a HIGHLIGHT on screen, what OVLAY value
-- -- and therefore what MX composition mode -- is LIVE in the SED1330, which
-- layer does the highlight land in, and what do the other layers hold at the
-- same coordinates?
--
-- This exists because the emulated wsa1r renders every highlighted GUI element
-- as a SOLID WHITE BLOCK, and the answer had to be MEASURED rather than reasoned
-- from the boot-time OVLAY value (0x1C, MX = OR) recorded by an earlier study.
--
-- WHAT IT READS
--   * every byte written to the controller port on CPU 1 -- 0x790000 = data,
--     0x790001 = command -- decoded as a command/parameter stream, so OVLAY
--     (0x5B) and SCROLL (0x44) parameters are recovered rather than assumed;
--   * on each OVLAY: the parameter byte, MX = bits 0-1, OV = bit 4
--     (src/devices/video/sed1330.cpp:560-575, MX names at :51-54), the issuing
--     CPU 1 PC, and the four coordinate words RAM (0x2530) = X0, (0x2532) = Y0,
--     (0x2534) = X1, (0x2536) = Y1 plus (0x2540) = the firmware layer number.
--     Those are final at that moment: LCD_Svc_05_FillRect (prom_a 0xF8EEBD)
--     does `stdi8 (0x2540),0x01`, calls LCD_ClampCoordsToPanel, and only THEN
--     issues OVLAY at 0xF8EECD;
--   * at DUMP_S, the SED1330's own display RAM (device ":lcdc", space
--     "videoram"): for each recorded fill, one scanline of layer 0 (SAD1 =
--     0x0000), layer 1 (SAD2 = 0x2600) and layer 2 (SAD3 = 0x4C00), and a
--     non-zero-byte count per layer.
--
-- WHAT COUNTS AS THE ANSWER
--   "live OVLAY=0x.. MX=.." on the VRAM-DUMP line is the value in the register
--   while the highlight is being displayed.  MX = 1 means the panel is
--   composing with Exclusive-OR, i.e. a filled block in layer 1 INVERTS the
--   text layer under it instead of covering it.
--
-- MEASURED 2026-08-27 on wsa1r: OVLAY 0x1C (MX = OR) at t = 0.500 from
-- LCD_Init_SED1330 and again at t = 22.875 from service 0x10 (0xF8FC1B), then
-- 0x1D (MX = XOR) three times from LCD_Svc_05_FillRect (pc 0xF8EEE6), and 0x1D
-- is still live at t = 40 -- nothing re-issues OVLAY afterwards.  All three
-- fills went to firmware layer 1 = SAD2.  Layer 1 held 25255 set pixels, which
-- is EXACTLY the union of the three filled rectangles (307*82 + 9*9), so that
-- layer holds nothing but highlight blocks.
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -window \
--       -str 45 -autoboot_script \
--       ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_ovlay_and_highlight_layers.lua
--
-- Set DUMPBIN to also write the whole 32 KiB of display RAM to a file, which
-- notes/wsa1-probes/wsa1_compose_layers.py recomposes under OR / XOR / AND.

local DUMP_S  = 40.0
local AP      = 40
local DUMPBIN = nil   -- e.g. "/tmp/wsa1_vram.bin"

local m   = manager.machine
local sp  = m.devices[":cpu1"].spaces["program"]
local vr  = m.devices[":lcdc"].spaces["videoram"]
_G.cpu1   = m.devices[":cpu1"]

local MXNAME = { [0]="OR", [1]="XOR", [2]="AND", [3]="PRIORITY-OR" }
local BASE   = { [0]=0x0000, [1]=0x2600, [2]=0x4C00 }

_G.cmd, _G.pi   = -1, 0
_G.ovlay, _G.mx = -1, -1
_G.fills, _G.scrollbuf = {}, {}
_G.nov = 0

local function onbyte(port, b)
	if port == 1 then _G.cmd, _G.pi = b, 0 return end     -- command byte
	if _G.cmd == 0x5b and _G.pi == 0 then                 -- OVLAY parameter
		_G.nov = _G.nov + 1
		local mx = b & 0x03
		local x0, y0 = sp:read_u16(0x2530), sp:read_u16(0x2532)
		local x1, y1 = sp:read_u16(0x2534), sp:read_u16(0x2536)
		local ly     = sp:read_u8(0x2540)
		print(string.format(
			"OVLAY #%d t=%8.3f value=0x%02X MX=%d %-11s OV=%d pc=%06X rect=(%d,%d)-(%d,%d) layer=%d",
			_G.nov, m.time:as_double(), b, mx, MXNAME[mx], (b >> 4) & 1,
			_G.cpu1.state["CURPC"].value, x0, y0, x1, y1, ly))
		if mx == 1 then
			_G.fills[#_G.fills+1] = {x0=x0,y0=y0,x1=x1,y1=y1,ly=ly,t=m.time:as_double()}
		end
		_G.ovlay, _G.mx = b, mx
	elseif _G.cmd == 0x44 then                            -- SCROLL parameters
		_G.scrollbuf[#_G.scrollbuf+1] = b
		if #_G.scrollbuf == 8 then
			print(string.format("SCROLL t=%8.3f SAD1=0x%04X SL1=%d SAD2=0x%04X SL2=%d SAD3=0x%04X",
				m.time:as_double(),
				_G.scrollbuf[1] | (_G.scrollbuf[2] << 8), _G.scrollbuf[3],
				_G.scrollbuf[4] | (_G.scrollbuf[5] << 8), _G.scrollbuf[6],
				_G.scrollbuf[7] | (_G.scrollbuf[8] << 8)))
			_G.scrollbuf = {}
		end
	end
	_G.pi = _G.pi + 1
end

-- ⚠ 16-bit space: a byte store to 0x790001 arrives as offset 0x790000 with
-- mem_mask 0xFF00.  Both forms are handled so the decode cannot silently swap
-- commands and data.
_G.tap = sp:install_write_tap(0x790000, 0x790001, "lcdcmd", function (o, d, k)
	if o == 0x790001 then
		onbyte(1, d & 0xff)
	elseif (k & 0xff00) ~= 0 then
		onbyte(1, (d >> 8) & 0xff)
		if (k & 0x00ff) ~= 0 then onbyte(0, d & 0xff) end
	else
		onbyte(0, d & 0xff)
	end
	return d
end)

local function row(base, y, bx0, bx1)
	local s = {}
	for bx = bx0, bx1 do s[#s+1] = string.format("%02X", vr:read_u8(base + y*AP + bx)) end
	return table.concat(s, " ")
end

_G.done = false
_G.sub = emu.add_machine_frame_notifier(function ()
	if _G.done or m.time:as_double() < DUMP_S then return end
	_G.done = true
	m.video:snapshot()
	print(string.format("\n=== VRAM DUMP t=%.3f   live OVLAY=0x%02X MX=%d %s ===",
		m.time:as_double(), _G.ovlay, _G.mx, MXNAME[_G.mx] or "?"))
	for i, f in ipairs(_G.fills) do
		local ymid = (f.y0 + f.y1) // 2
		local bx0, bx1 = f.x0 // 8, f.x1 // 8
		if bx1 - bx0 > 11 then bx1 = bx0 + 11 end
		print(string.format(
			"FILL %d rect=(%d,%d)-(%d,%d) fwlayer=%d t=%.3f  scanline y=%d bytes %d..%d",
			i, f.x0, f.y0, f.x1, f.y1, f.ly, f.t, ymid, bx0, bx1))
		for L = 0, 2 do
			print(string.format("   layer%d SAD=0x%04X : %s", L, BASE[L], row(BASE[L], ymid, bx0, bx1)))
		end
	end
	for L = 0, 2 do
		local nz = 0
		for a = BASE[L], BASE[L] + 240*AP - 1 do
			if vr:read_u8(a) ~= 0 then nz = nz + 1 end
		end
		print(string.format("layer%d SAD=0x%04X : %d of %d bytes non-zero", L, BASE[L], nz, 240*AP))
	end
	if DUMPBIN then
		local t = {}
		for a = 0, 0x7fff do t[#t+1] = string.char(vr:read_u8(a)) end
		local fh = io.open(DUMPBIN, "wb"); fh:write(table.concat(t)); fh:close()
		print("display RAM written to " .. DUMPBIN)
	end
end)

print("OVLAY / HIGHLIGHT-LAYER PROBE armed")
