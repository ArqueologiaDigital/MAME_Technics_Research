-- tg_trace.lua -- every tone-generator register write, for single notes of chosen sounds.
-- rig-machine: kn7000
--
-- QUESTION: what does the firmware write to the two TGs for one note-on, and which of
-- those registers change with the sound, the key and the TG? (G13: which register
-- selects the wave-ROM sample.)
--
-- Taps the raw bus (0x98040000-3 and 0x98050000-3), so it sees what the chips see,
-- whatever the driver does with it. Writes one line per TG data write, except the idle
-- 0xFC0x refresh:
--     W <t> <tg> <addr> <data> [np16 rectype]
-- writes elsewhere in each TG's 64 KB window: X <t> <tg> <offset> <data> <mask>
-- and the global plane 0xFCxx (the idle refresh) only when an address's value changes:
--     G <t> <tg> <addr> <data>
-- tg 0 = 0x98040000, 1 = 0x98050000 (the driver's indices). On pitch writes (class
-- 0x2400) np16/rectype come from the firmware's voice record (base G13_RECBASE,
-- default 0x500AF940 = v16), as a cross-check only. Marker lines start with '#'.
--
-- ENV  G13_OUT     output path (required)
--      G13_GROUPS  comma list of sound groups to visit (default: all below)
--      G13_KEYS    comma list of key names (default C2,C3,C4,C5,C6,C7; ALL = C2..C7)
--      G13_T0      start time in s (default 16)
--      G13_RECBASE voice-record base (default 0x500AF940)
--      G13_STRAP   bits ORed into the 0x98070000 strap read (default 0 = the driver's value)
--      G13_ON/G13_GAP  key hold and gap in s (default 0.8 / 0.5)
-- RUN  ./tools/rig.sh <this file> kn7000 -s <secs> -- -bios v16

local mac  = manager.machine
local prog = mac.devices[":maincpu"].spaces["program"]
_G.g13 = _G.g13 or {}
local G = _G.g13
G.out = assert(io.open(assert(os.getenv("G13_OUT"), "G13_OUT not set"), "w"))
G.recbase = tonumber(os.getenv("G13_RECBASE") or "0x500AF940")
G.addr = {0, 0}
G.fc = {}

local function now() local t = mac.time; return t.seconds + t.attoseconds / 1e18 end
local function slot(tg, a) local s = (a >> 4) & 0x3F; return s | (tg == 0 and 0x40 or 0) end

local function tap(base, tg)
	return prog:install_write_tap(base, base + 3, "g13tg" .. tg, function(off, data, mask)
		if (mask & 0x0000ffff) ~= 0 then G.addr[tg + 1] = data & 0xffff end
		if (mask & 0xffff0000) ~= 0 then
			local a = G.addr[tg + 1]; local d = (data >> 16) & 0xffff
			local fc = (a & 0xff00) == 0xfc00
			if fc then
				-- the idle 0xFC0x refresh repeats every tick: log a global write only when its value changes
				local k = tg * 0x10000 + a
				if G.fc[k] ~= d then G.fc[k] = d; G.out:write(string.format("G %.6f %d %04x %04x\n", now(), tg, a, d)) end
			else
				local extra = ""
				if (a & 0xFC0E) == 0x2400 then
					local rec = G.recbase + slot(tg, a) * 0xB4
					extra = string.format(" %04x %02x", prog:read_u16(rec + 0x0C), prog:read_u16(rec + 0x02) & 0x7C)
				end
				G.out:write(string.format("W %.6f %d %04x %04x%s\n", now(), tg, a, d, extra))
			end
		end
		return nil
	end)
end
G.t0 = tap(0x98040000, 0)
G.t1 = tap(0x98050000, 1)
-- every other write in each TG's window (control +4/+0x10, wave port +6/+8, ...):
--     X <t> <tg> <offset> <data> <mask>
local function xtap(base, tg)
	return prog:install_write_tap(base + 4, base + 0xB, "g13x" .. tg, function(off, data, mask)
		G.out:write(string.format("X %.6f %d %04x %08x %08x\n", now(), tg, off - base, data, mask))
		return nil
	end)
end
-- G13_STRAP: OR these bits into the strap word read at 0x98070000 (e.g. 0x0400: bits 11:10 = 01,
-- hardware subtype 1 instead of the driver's 5; see PanelSubTypeGet 0x484D7751)
G.strap = tonumber(os.getenv("G13_STRAP") or "0")
if G.strap ~= 0 then
	G.st = prog:install_read_tap(0x98070000, 0x98070003, "g13strap", function(off, data, mask)
		if off == 0x98070000 then return data | (G.strap << 16) | G.strap end
		return data
	end)
end
G.x0 = xtap(0x98040000, 0)
G.x1 = xtap(0x98050000, 1)

local GROUPS = {
	PIANO = {":cpanel:CPR_SEG4", 0x10}, GUITAR = {":cpanel:CPR_SEG3", 0x10},
	STRINGS = {":cpanel:CPR_SEG0", 0x10}, SYNTH = {":cpanel:CPR_SEG0", 0x20},
	WORLD = {":cpanel:CPR_SEG1", 0x10}, PAD = {":cpanel:CPR_SEG1", 0x20},
	MALLET = {":cpanel:CPR_SEG2", 0x10}, ACCREG = {":cpanel:CPR_SEG2", 0x20},
	TABORGAN = {":cpanel:CPR_SEG3", 0x20}, DRAWBAR = {":cpanel:CPR_SEG4", 0x20},
	EXPLORER = {":cpanel:CPR_SEG6", 0x08}, ORGAN = {":cpanel:CPR_SEG7", 0x08},
	DRUMS = {":cpanel:CPR_SEG8", 0x04}, SAX = {":cpanel:CPR_SEG8", 0x08},
	BASS = {":cpanel:CPR_SEG9", 0x04}, BRASS = {":cpanel:CPR_SEG9", 0x08},
}
local ORDER = "PIANO,STRINGS,ORGAN,BRASS,GUITAR,BASS,SYNTH,PAD,MALLET,SAX,WORLD,DRUMS"
local KEYS = {}
do  -- key name -> port, mask (C2 = KEYS0 bit 0, 16 keys per port)
	local names = {"C","C#","D","D#","E","F","F#","G","G#","A","A#","B"}
	for i = 0, 60 do
		local nm = names[i % 12 + 1] .. tostring(2 + i // 12)
		KEYS[nm] = {":KEYS" .. (i // 16), 1 << (i % 16)}
	end
end

local function set(tag, mask, v)
	local p = mac.ioport.ports[tag]
	for _, f in pairs(p.fields) do if f.mask == mask then f:set_value(v) end end
end

local acts = {}
local function at(t, fn) acts[#acts + 1] = {t = t, fn = fn} end
local function mark(t, s) at(t, function() G.out:write(string.format("# %.6f %s\n", now(), s)) end) end

local t = tonumber(os.getenv("G13_T0") or "16")
local HOLD = tonumber(os.getenv("G13_ON") or "0.8")
local GAP = tonumber(os.getenv("G13_GAP") or "0.5")
local groups = os.getenv("G13_GROUPS") or ORDER
local keys = os.getenv("G13_KEYS") or "C2,C3,C4,C5,C6,C7"
if keys == "ALL" then
	local names = {"C","C#","D","D#","E","F","F#","G","G#","A","A#","B"}
	local l = {}
	for i = 0, 60 do l[#l + 1] = names[i % 12 + 1] .. tostring(2 + i // 12) end
	keys = table.concat(l, ",")
end
for g in groups:gmatch("[^,]+") do
	local b = assert(GROUPS[g], "unknown group " .. g)
	mark(t, "GROUP " .. g)
	at(t, function() set(b[1], b[2], 1) end)
	at(t + 0.35, function() set(b[1], b[2], 0) end)
	t = t + 1.6
	for k in keys:gmatch("[^,]+") do
		local kk = assert(KEYS[k], "unknown key " .. k)
		mark(t, "ON " .. g .. " " .. k)
		at(t, function() set(kk[1], kk[2], 1) end)
		mark(t + HOLD, "OFF " .. g .. " " .. k)
		at(t + HOLD, function() set(kk[1], kk[2], 0) end)
		t = t + HOLD + GAP
	end
end
mark(t, "END")
at(t + 0.05, function() G.out:close(); mac:exit() end)
table.sort(acts, function(a, b) return a.t < b.t end)
G.i = 1
G.h = emu.add_machine_frame_notifier(function()
	local tn = now()
	while G.i <= #acts and acts[G.i].t <= tn do acts[G.i].fn(); G.i = G.i + 1 end
end)
