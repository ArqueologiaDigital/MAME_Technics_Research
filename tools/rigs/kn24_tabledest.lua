-- kn24_tabledest.lua -- where in RAM does the KN2400's table-ROM read land?
-- rig-machine: kn2400
--
-- notes/FINDINGS-kn2400-table-rom.md established that the undumped table region
-- (0x48000000-0x483FFFFF, ROMREGION_ERASEFF) is read 164,300 times between t=0 and t=6 and
-- then never again -- so the black text bars drawn at t=25 come from a RAM copy taken at
-- boot, not from live fetches. That makes the destination buffer investigable RIGHT NOW,
-- with no dump and no hardware.
--
-- This rig names it. It taps reads of the table region and writes to work RAM, keyed by the
-- PC doing them, then reports the destination ranges written by the same PCs that read the
-- table. A copy loop reads and writes from one routine, so the overlap is the copy.
--
-- Both RAM windows are watched, because on this machine they are the same memory:
--   0x50000000-0x503FFFFF  work RAM
--   0x90000000-0x903FFFFF  its +0x40000000 write/execute alias -- the KN2400's block loader
--                          (0x4870587E, descriptors at 0x487965BB) adjusts destinations by
--                          +0x40000000, so copies LAND in the alias. Watching only 0x50…
--                          would miss the writes entirely.
--
-- Reports:
--   DEST readers=<n>  -- top PCs reading the table region
--   DEST writers=<n>  -- top PCs writing RAM
--   DEST OVERLAP pc=0x… reads=<n> writes=<n> dst=0x…..0x…   <- the copy loops
--
-- ⚠ Value matching is useless here: the source reads back as all-0xFF, so "the byte I just
--   read appeared at this address" would match essentially everywhere. PC correlation is the
--   only honest join.
--
--   ./tools/rig.sh kn24_tabledest kn2400 -s 32
--   TAP_UNTIL=12 ...        (default 10 -- the traffic is over by t=6)

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local UNTIL = tonumber(os.getenv("TAP_UNTIL")) or 10

-- Confirm the register exists before relying on it. Guessing a register name once cost a
-- 10-minute run that produced no output at all (see cpu_state_probe.lua).
local PCOK = pcall(function() return cpu.state["PC"].value end)
if not PCOK then
    log("DEST FATAL -- this CPU exposes no 'PC' state key; run cpu_state_probe.lua first.")
end
local function pc()
    if not PCOK then return -1 end
    local ok, v = pcall(function() return cpu.state["PC"].value end)
    return ok and v or -1
end

-- Globals: a local handle is collected by the Lua GC and the tap silently stops firing.
_G.DS = _G.DS or { rd = {}, wr = {}, nrd = 0, nwr = 0 }

_G.DS.rtap = prog:install_read_tap(0x48000000, 0x483FFFFF, "tabsrc", function(offset, data, mask)
    local s = _G.DS
    s.nrd = s.nrd + 1
    local p = pc()
    local e = s.rd[p]
    if not e then e = { n = 0 }; s.rd[p] = e end
    e.n = e.n + 1
    return nil
end)

local function wtap(lo, hi, tag)
    return prog:install_write_tap(lo, hi, tag, function(offset, data, mask)
        local s = _G.DS
        s.nwr = s.nwr + 1
        local p = pc()
        local e = s.wr[p]
        if not e then e = { n = 0, lo = offset, hi = offset }; s.wr[p] = e end
        e.n = e.n + 1
        if offset < e.lo then e.lo = offset end
        if offset > e.hi then e.hi = offset end
        return nil
    end)
end

_G.DS.w1 = wtap(0x50000000, 0x503FFFFF, "ram50")
_G.DS.w2 = wtap(0x90000000, 0x903FFFFF, "ram90")

_G.DS.h = emu.add_machine_frame_notifier(function()
    if _G.DS.done or mac.time.seconds < UNTIL then return end
    _G.DS.done = true
    local s = _G.DS

    local function top(tbl, k)
        local l = {}
        for p, e in pairs(tbl) do l[#l + 1] = { p, e } end
        table.sort(l, function(a, b) return a[2].n > b[2].n end)
        local out = {}
        for i = 1, math.min(k, #l) do out[i] = l[i] end
        return out, #l
    end

    local rtop, nr = top(s.rd, 10)
    local wtop, nw = top(s.wr, 10)
    log(string.format("DEST table_reads=%d from %d distinct PCs; ram_writes=%d from %d PCs",
        s.nrd, nr, s.nwr, nw))

    log("DEST top table READERS:")
    for _, e in ipairs(rtop) do
        log(string.format("   pc=0x%08X  %d reads", e[1], e[2].n))
    end
    log("DEST top RAM WRITERS:")
    for _, e in ipairs(wtop) do
        log(string.format("   pc=0x%08X  %d writes  dst=0x%08X..0x%08X",
            e[1], e[2].n, e[2].lo, e[2].hi))
    end

    -- The join: a routine that both reads the table and writes RAM is a copy loop.
    --
    -- ⚠ MUST be a WINDOW, not equality. The first version of this rig joined on exact PC and
    -- reported "0 overlaps -- the reader and writer are different routines". That was a bug in
    -- the rig, not a fact about the firmware: a copy loop's load and store are SEPARATE
    -- instructions at different addresses. The loop at 0x4860C274 is
    --     movhu (a0),d0   @ 0x4860C275     <- read tap fires here
    --     movhu d0,(a1)   @ 0x4860C279     <- write tap fires here
    -- Four bytes apart, and exact-match join can never see it. Verified by disassembly.
    local WIN = tonumber(os.getenv("JOIN_WINDOW")) or 64
    local hits = {}
    for p, r in pairs(s.rd) do
        local best, bestpc = nil, nil
        for q, w in pairs(s.wr) do
            if math.abs(q - p) <= WIN and (not best or w.n > best.n) then best, bestpc = w, q end
        end
        if best then hits[#hits + 1] = { p, r, best, bestpc } end
    end
    table.sort(hits, function(a, b) return a[2].n > b[2].n end)
    log(string.format("DEST COPY LOOPS: %d table readers have a RAM writer within %d bytes",
        #hits, WIN))
    for i = 1, math.min(12, #hits) do
        local p, r, w, q = hits[i][1], hits[i][2], hits[i][3], hits[i][4]
        log(string.format("   rd_pc=0x%08X reads=%-7d  wr_pc=0x%08X writes=%-7d  dst=0x%08X..0x%08X (%d B)",
            p, r.n, q, w.n, w.lo, w.hi, w.hi - w.lo + 1))
    end
    if #hits == 0 then
        log("   none even with the window -- the data really is staged through another routine.")
    end

    -- The copy loop at 0x4860C271 takes its destination base from RAM:
    --     mov (0x500D7398), d1 ; add 0x10, d1 ; add index*0x2C8, d1 ; mov d1, a1
    -- so the buffer it fills is [0x500D7398] + 0x10. Report it, since the address is the
    -- thing a later investigation needs and it is not derivable statically.
    local ok, base = pcall(function() return prog:read_u32(0x500D7398) end)
    if ok then
        log(string.format("DEST buffer pointer [0x500D7398] = 0x%08X  (records start at +0x10 = 0x%08X,"
            .. " stride 0x2C8 = 712 B)", base, base + 0x10))
    else
        log("DEST buffer pointer [0x500D7398] unreadable")
    end

    -- ---- close the chain: is what LANDED in RAM actually 0xFF?
    -- Everything above is about traffic. This is about content, and it is the step that turns
    -- "the source region is empty" into "the destination is full of 0xFF, which is why the
    -- glyph cells draw solid". Without it the causal claim is inference.
    local seen = {}
    local regions = {}
    for i = 1, math.min(12, #hits) do
        local w = hits[i][3]
        if not seen[w.lo] then
            seen[w.lo] = true
            regions[#regions + 1] = w
        end
    end
    log("DEST destination CONTENT (sampled after the copy):")
    for _, w in ipairs(regions) do
        local span = w.hi - w.lo + 1
        local step = math.max(1, math.floor(span / 2048))
        local n, ff, zero = 0, 0, 0
        for a = w.lo, w.hi, step do
            local okb, b = pcall(function() return prog:read_u8(a) end)
            if okb then
                n = n + 1
                if b == 0xFF then ff = ff + 1 elseif b == 0x00 then zero = zero + 1 end
            end
        end
        if n > 0 then
            log(string.format("   0x%08X..0x%08X  %6.2f%% 0xFF  %6.2f%% 0x00  (%d samples)",
                w.lo, w.hi, 100.0 * ff / n, 100.0 * zero / n, n))
        end
    end
    log("DEST ---- a buffer that is ~100% 0xFF is the missing table ROM, copied verbatim.")
    mac:exit()
end)
