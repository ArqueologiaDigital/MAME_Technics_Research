-- kn24_glyphsrc.lua -- what memory does the KN2400's compositor actually read?
-- rig-machine: kn2400
--
-- The hunt so far (notes/FINDINGS-kn2400-table-rom.md): the undumped table ROM is copied at
-- boot into RAM buffers that are ~all 0xFF, but overwriting those buffers across the paint
-- changes NOTHING on screen -- so they are not what draws the black text bars. This finds the
-- real source.
--
-- kn24_fbwrites.lua named the compositor: 0x485EC9D6 `movhu d1,(a0)` writes the 2bpp
-- framebuffer, 40 halfwords per row (= 80 B = one 320px scanline) x 240 rows. Its pixel input
-- is `movbu (a2),d0` at 0x485EC993 / 0x485EC9A2.
--
-- Rather than reverse-engineer where a2 points, this asks the machine: tap every plausible
-- region and record only the reads whose PC lies inside the compositor body. Whatever region
-- lights up IS the glyph source.
--
-- Regions tapped (from kn7000_state::maincpu_mem):
--   0x48000000  table ROM (undumped, ERASEFF)      0x4C000000  libram
--   0x48400000  program ROM                        0x50000000  work RAM
--   0x8C000000  libram alias                       0x90000000  work RAM alias
--   0x9C000000  LCD buffer
--
--   ./tools/rig.sh kn24_glyphsrc kn2400 -s 16
--   PC_LO=0x485EC900 PC_HI=0x485ECA00 TAP_UNTIL=14 ...
--
-- Reports per region: read count, address range, and the top 256 B buckets -- so a font table
-- shows up as a bounded, hot span rather than a vague "it reads RAM".

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local UNTIL = tonumber(os.getenv("TAP_UNTIL")) or 14
local PC_LO = tonumber(os.getenv("PC_LO") or "") or 0x485EC900
local PC_HI = tonumber(os.getenv("PC_HI") or "") or 0x485ECA00

local REGIONS = {
    { 0x48000000, 0x483FFFFF, "table(UNDUMPED)" },
    { 0x48400000, 0x487FFFFF, "programROM" },
    { 0x4C000000, 0x4CFFFFFF, "libram" },
    { 0x50000000, 0x503FFFFF, "workram" },
    { 0x8C000000, 0x8CFFFFFF, "libram_alias" },
    { 0x90000000, 0x903FFFFF, "workram_alias" },
    { 0x9C000000, 0x9CFFFFFF, "lcdbuf" },
}

local function pc()
    local ok, v = pcall(function() return cpu.state["PC"].value end)
    return ok and v or -1
end

_G.GS = _G.GS or { r = {}, taps = {}, total = 0 }

for i, reg in ipairs(REGIONS) do
    local lo, hi, name = reg[1], reg[2], reg[3]
    _G.GS.r[name] = { n = 0, lo = nil, hi = nil, hist = {} }
    -- pcall: a region absent on this machine must not kill the whole rig.
    local ok, tap = pcall(function()
        return prog:install_read_tap(lo, hi, "gs" .. i, function(offset, data, mask)
            local p = pc()
            if p < PC_LO or p > PC_HI then return nil end
            -- Skip the routine's own INSTRUCTION FETCH. The PC window lies inside programROM,
            -- so without this the top "read" is the compositor reading itself -- 9.85 M hits at
            -- exactly PC_LO..PC_HI, which looks like a finding and is an artifact.
            if offset >= PC_LO and offset <= PC_HI then return nil end
            local e = _G.GS.r[name]
            e.n = e.n + 1
            _G.GS.total = _G.GS.total + 1
            if not e.lo or offset < e.lo then e.lo = offset end
            if not e.hi or offset > e.hi then e.hi = offset end
            local b = offset & 0xFFFFFF00
            e.hist[b] = (e.hist[b] or 0) + 1
            return nil
        end)
    end)
    if ok then _G.GS.taps[#_G.GS.taps + 1] = tap
    else log("GS could not tap " .. name) end
end

_G.GS.h = emu.add_machine_frame_notifier(function()
    if _G.GS.done or mac.time.seconds < UNTIL then return end
    _G.GS.done = true

    log(string.format("GS reads by PC in [0x%08X..0x%08X] = %d total", PC_LO, PC_HI, _G.GS.total))
    if _G.GS.total == 0 then
        log("GS NOTHING -- the PC window is wrong, or the compositor reads a region not tapped.")
        log("   Re-check the writer PC with kn24_fbwrites.lua before trusting this null.")
        mac:exit()
        return
    end
    for _, reg in ipairs(REGIONS) do
        local name = reg[3]
        local e = _G.GS.r[name]
        if e.n > 0 then
            log(string.format("GS %-16s %8d reads  0x%08X..0x%08X", name, e.n, e.lo, e.hi))
            local top = {}
            for a, c in pairs(e.hist) do top[#top + 1] = { a, c } end
            table.sort(top, function(x, y) return x[2] > y[2] end)
            for i = 1, math.min(12, #top) do
                -- Content matters as much as traffic: a glyph source that is all-0xFF is the
                -- black-bar cause, one that is varied is healthy data.
                local ff, nn = 0, 0
                for a = top[i][1], top[i][1] + 255 do
                    local okb, b = pcall(function() return prog:read_u8(a) end)
                    if okb then nn = nn + 1; if b == 0xFF then ff = ff + 1 end end
                end
                log(string.format("      0x%08X  %8d reads   %5.1f%% 0xFF",
                    top[i][1], top[i][2], nn > 0 and 100.0 * ff / nn or -1))
            end
        else
            log(string.format("GS %-16s        0", name))
        end
    end
    mac:exit()
end)
