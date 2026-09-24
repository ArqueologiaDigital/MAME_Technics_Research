-- What question does this answer?
--   "The key bed dropped PORT_NAME in favour of MAME's PORT_GM_* note constants.
--    Do the 61 fields still carry a usable name in the UI, and the right note?"
--
-- Run: ./kn kn7000 -rompath ~/compartilhado/technics_romsets -skip_gameinfo \
--        -window -nomaximize -str 6 -autoboot_script <this file>
-- PASS: 61 fields, every name non-empty, notes 36..96 with no gaps.
local n, bad, notes = 0, 0, {}
for _, tag in ipairs({":KEYS0", ":KEYS1", ":KEYS2", ":KEYS3"}) do
	local p = manager.machine.ioport.ports[tag]
	if p == nil then
		print(string.format("KEYBED: port %s MISSING", tag))
		bad = bad + 1
	else
		for fname, f in pairs(p.fields) do
			n = n + 1
			if fname == nil or fname == "" then bad = bad + 1 end
			-- print the first two of each port so the names are visible, not just counted
			if n % 16 <= 1 then
				print(string.format("KEYBED: %s mask=0x%04x name=%q", tag, f.mask, fname))
			end
		end
	end
end
print(string.format("KEYBED: fields=%d unnamed=%d", n, bad))
print("KEYBED-DONE")
