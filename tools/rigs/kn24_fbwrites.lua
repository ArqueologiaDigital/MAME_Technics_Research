-- kn24_fbwrites.lua -- WHEN is the KN2400's screen actually composited?
-- rig-machine: kn2400
--
-- This exists to make kn24_bufferpoke.lua's negative results interpretable. Poking a
-- suspected glyph buffer and seeing no change means nothing if the screen was drawn BEFORE
-- the poke and never redrawn -- and the positive control showed exactly that risk: writing
-- straight into the framebuffer at t=20 changed the display and the change was still there
-- at t=30, i.e. the firmware never re-composited over it.
--
-- So: tap the framebuffer and report when it is written. The KN2400/KN2600 composite into a
-- 2bpp 320x240 buffer at 0x9C800000 (stride 80 B, MSB-first pixel pairs) -- see
-- kn7000_state::screen_update.
--
-- A poke of a glyph source is only a fair test if it happens BEFORE the last framebuffer
-- write. This rig gives that deadline.
--
--   ./tools/rig.sh kn24_fbwrites kn2400 -s 34
--   TAP_UNTIL=32 ...     (default 32)
--
-- Reports first/last write time, total count, and a per-second histogram, so a screen that
-- is painted once at boot is visibly different from one repainted every frame.

local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local UNTIL = tonumber(os.getenv("TAP_UNTIL")) or 32
local FB_LO, FB_HI = 0x9C800000, 0x9C804AFF     -- 320*240*2bpp = 19200 B

_G.FB = _G.FB or { n = 0, per = {}, pcs = {} }

local function pc()
    local ok, v = pcall(function() return cpu.state["PC"].value end)
    return ok and v or -1
end

_G.FB.tap = prog:install_write_tap(FB_LO, FB_HI, "fb", function(offset, data, mask)
    local s = _G.FB
    s.n = s.n + 1
    local t = mac.time.seconds
    if not s.first then s.first = mac.time.seconds + mac.time.attoseconds / 1e18 end
    s.last = mac.time.seconds + mac.time.attoseconds / 1e18
    s.per[t] = (s.per[t] or 0) + 1
    -- WHO composites. This is the handle on the glyph source: disassembling the writer shows
    -- what it reads from, which is exactly how the table-ROM copy loop at 0x4860C274 was found.
    local p = pc()
    local e = s.pcs[p]
    if not e then e = { n = 0, lo = offset, hi = offset, tfirst = t }; s.pcs[p] = e end
    e.n = e.n + 1
    if offset < e.lo then e.lo = offset end
    if offset > e.hi then e.hi = offset end
    e.tlast = t
    return nil
end)

_G.FB.h = emu.add_machine_frame_notifier(function()
    if _G.FB.done or mac.time.seconds < UNTIL then return end
    _G.FB.done = true
    local s = _G.FB
    if s.n == 0 then
        log("FB no writes to 0x9C800000 at all -- the framebuffer address is wrong, or the")
        log("   firmware composites somewhere else. Check screen_update in the driver.")
        mac:exit()
        return
    end
    log(string.format("FB writes=%d first=%.2fs last=%.2fs", s.n, s.first, s.last))
    local secs = {}
    for t in pairs(s.per) do secs[#secs + 1] = t end
    table.sort(secs)
    local parts = {}
    for _, t in ipairs(secs) do parts[#parts + 1] = string.format("%d:%d", t, s.per[t]) end
    log("FB per second -- " .. table.concat(parts, " "))
    log(string.format("FB ---- a glyph-source poke is only a fair test if it lands BEFORE t=%.2f",
        s.last))

    local l = {}
    for p, e in pairs(s.pcs) do l[#l + 1] = { p, e } end
    table.sort(l, function(a, b) return a[2].n > b[2].n end)
    log(string.format("FB writers: %d distinct PCs", #l))
    for i = 1, math.min(12, #l) do
        local p, e = l[i][1], l[i][2]
        log(string.format("   pc=0x%08X  %6d writes  fb=0x%08X..0x%08X  t=%d..%d",
            p, e.n, e.lo, e.hi, e.tfirst, e.tlast))
    end
    log("FB ---- disassemble the top writer to find what it READS. That is the glyph source.")
    mac:exit()
end)
