-- kn24_planewriters.lua -- who fills the KN2400's UI source plane, and with what?
-- rig-machine: kn2400
--
-- Where the hunt stands (notes/FINDINGS-kn2400-table-rom.md): the undumped table ROM is
-- exonerated twice over, and kn24_glyphsrc.lua showed the compositor's input is work RAM at
-- 0x500B0C00..0x500B2800 which is 0.0% 0xFF -- real, varied data. So "0xFF glyphs draw solid"
-- is dead as an explanation.
--
-- THE ARGUMENT THAT NARROWS IT: the KN2400 draws its grand-piano ICONS correctly and its TEXT
-- as solid bars, and both go through the SAME compositor (0x485EC9D6) and the SAME per-pixel
-- lookup at 0x5039B700. A stage shared by a working case and a broken case cannot be the
-- defect. So the source plane must already contain solid bars before compositing, and the bug
-- is upstream in whatever draws text into it.
--
-- This finds that writer: tap the plane, group writes by PC, and report for each writer how
-- much of what it writes is SOLID (0xFF/0x00 runs) versus varied. A text drawer emitting
-- all-ones bytes is the defect; one emitting varied bytes means the plane is fine and the
-- fault moved downstream again.
--
--   ./tools/rig.sh kn24_planewriters kn2400 -s 16
--   PLANE_LO=0x500B0000 PLANE_HI=0x500B3FFF TAP_UNTIL=14 ...
--
-- Reports per writer PC: count, address span, and the value histogram of what it wrote.

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local UNTIL = tonumber(os.getenv("TAP_UNTIL")) or 14
local LO    = tonumber(os.getenv("PLANE_LO") or "") or 0x500B0000
local HI    = tonumber(os.getenv("PLANE_HI") or "") or 0x500B3FFF

local function pc()
    local ok, v = pcall(function() return cpu.state["PC"].value end)
    return ok and v or -1
end

_G.PW = _G.PW or { n = 0, pcs = {} }

_G.PW.tap = prog:install_write_tap(LO, HI, "plane", function(offset, data, mask)
    local s = _G.PW
    s.n = s.n + 1
    local p = pc()
    local e = s.pcs[p]
    if not e then e = { n = 0, lo = offset, hi = offset, vals = {}, ones = 0, zeros = 0 } ; s.pcs[p] = e end
    e.n = e.n + 1
    if offset < e.lo then e.lo = offset end
    if offset > e.hi then e.hi = offset end
    -- Count the byte lanes actually written, so "solid" is measured on real bytes and not on
    -- whatever happens to sit in the unwritten half of a 32-bit bus cycle.
    for lane = 0, 3 do
        if (mask & (0xFF << (lane * 8))) ~= 0 then
            local b = (data >> (lane * 8)) & 0xFF
            e.vals[b] = (e.vals[b] or 0) + 1
            if b == 0xFF then e.ones = e.ones + 1 elseif b == 0x00 then e.zeros = e.zeros + 1 end
        end
    end
    return nil
end)

_G.PW.h = emu.add_machine_frame_notifier(function()
    if _G.PW.done or mac.time.seconds < UNTIL then return end
    _G.PW.done = true
    local s = _G.PW
    log(string.format("PW plane 0x%08X..0x%08X  writes=%d", LO, HI, s.n))
    if s.n == 0 then
        log("PW nothing writes this range -- the plane address is wrong, or it is filled via an alias.")
        mac:exit()
        return
    end
    local l = {}
    for p, e in pairs(s.pcs) do l[#l + 1] = { p, e } end
    table.sort(l, function(a, b) return a[2].n > b[2].n end)
    log(string.format("PW %d distinct writer PCs", #l))
    for i = 1, math.min(12, #l) do
        local p, e = l[i][1], l[i][2]
        local tot = 0
        for _, c in pairs(e.vals) do tot = tot + c end
        -- the most common byte this PC writes, and how dominant it is
        local bb, bc = nil, 0
        for b, c in pairs(e.vals) do if c > bc then bb, bc = b, c end end
        local distinct = 0
        for _ in pairs(e.vals) do distinct = distinct + 1 end
        log(string.format("   pc=0x%08X %7d writes  0x%08X..0x%08X  bytes: %d distinct, "
            .. "top=0x%02X (%.1f%%), 0xFF %.1f%%, 0x00 %.1f%%",
            p, e.n, e.lo, e.hi, distinct, bb or 0,
            tot > 0 and 100.0 * bc / tot or 0,
            tot > 0 and 100.0 * e.ones / tot or 0,
            tot > 0 and 100.0 * e.zeros / tot or 0))
    end
    log("PW ---- a writer emitting almost only 0xFF (or 0x00) into the text area is the defect;")
    log("PW      varied bytes mean the plane is healthy and the fault is further downstream.")
    mac:exit()
end)
