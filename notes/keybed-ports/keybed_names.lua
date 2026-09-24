-- What question does this answer?
--   The key bed was rewritten from two bespoke macros (KN_KEYM/KN_KEYPC) to plain
--   PORT_BIT lines using MAME's PORT_GM_* note constants, which meant dropping
--   PORT_NAME and changing IPT_KEYBOARD to IPT_OTHER. Two things to prove:
--     (1) the 61 fields still carry a usable name, and land on the right masks;
--     (2) no field is asserted at reset, so no phantom note reaches the audio.
--
-- (2) needs a positive control: a port that always read 0 looks exactly like a port
-- with nothing pressed. So drive a field and require the read to move. set_value
-- lands on the next input update, hence the emu.wait between set and read.
--
-- Run: ./kn kn7000 -rompath ~/compartilhado/technics_romsets -skip_gameinfo \
--        -window -nomaximize -str 8 -sound none -autoboot_script <this file>
local TAGS = { ":KEYS0", ":KEYS1", ":KEYS2", ":KEYS3" }

local function ports()
	local t = {}
	for _, tag in ipairs(TAGS) do t[tag] = manager.machine.ioport.ports[tag] end
	return t
end

emu.add_machine_reset_notifier(function () end)   -- keep the Lua state alive

local function run()
	emu.wait(2.0)
	local p = ports()

	local n, unnamed = 0, 0
	for _, tag in ipairs(TAGS) do
		for fname, f in pairs(p[tag].fields) do
			n = n + 1
			if fname == nil or fname == "" then unnamed = unnamed + 1 end
			if n % 16 <= 1 then
				print(string.format("KEYBED: %s mask=0x%04x name=%q", tag, f.mask, fname))
			end
		end
	end
	print(string.format("KEYBED: fields=%d unnamed=%d", n, unnamed))

	-- positive control first: prove the read can move before trusting a zero
	local f = p[":KEYS1"].fields["C4"]
	f:set_value(1);  emu.wait(0.2);  local hi = p[":KEYS1"]:read()
	f:set_value(0);  emu.wait(0.2);  local lo = p[":KEYS1"]:read()
	local movable = (hi ~= 0 and lo == 0)
	print(string.format("KEYBED: control C4 pressed=0x%04x released=0x%04x -> %s",
		hi, lo, movable and "READ CAN MOVE" or "READ IS STUCK"))

	local stuck = 0
	for _, tag in ipairs(TAGS) do
		local v = p[tag]:read()
		if v ~= 0 then stuck = stuck + 1 end
		print(string.format("KEYBED: %s reads 0x%04x at reset", tag, v))
	end
	print(string.format("KEYBED: ports-asserted-at-reset=%d control=%s",
		stuck, movable and "VALID" or "INVALID"))
	print("KEYBED-DONE")
end

_G.kn_keybed_task = coroutine.create(run)
emu.register_periodic(function ()
	if coroutine.status(_G.kn_keybed_task) == "suspended" then
		local ok, err = coroutine.resume(_G.kn_keybed_task)
		if not ok then print("KEYBED: error " .. tostring(err)) end
	end
end)
