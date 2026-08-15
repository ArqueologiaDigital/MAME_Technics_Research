-- kn24_planedump.lua -- dump the KN2400's UI source plane so it can be LOOKED at.
-- rig-machine: kn2400
--
-- Everything so far has been inference about a picture nobody has seen. The compositor
-- (0x485EC9D6) consumes 8 source bytes per 8 pixels -- one byte per pixel -- so its input is a
-- 320x240 = 76,800-byte 8bpp plane. Dumping it and rendering it as an image answers directly
-- what earlier rigs could only triangulate: does the plane already contain solid bars where
-- text belongs (defect upstream, in the text drawer) or readable glyphs (defect downstream)?
--
-- ⚠ This corrects a sizing mistake worth recording. kn24_planewriters.lua tapped
--   0x500B0000..0x500B3FFF -- 16 KB, a fifth of the plane -- and kn24_glyphsrc.lua printed only
--   its top 12 read buckets, which were all exactly 1536. That looked like "a cluster of 11
--   hot buckets" and was really the truncated head of a flat plateau spanning the whole plane.
--   A top-N histogram cannot distinguish a peak from a plateau; print the extent too.
--
--   ./tools/rig.sh kn24_planedump kn2400 -s 16
--   PLANE_BASE=0x500B0000 PLANE_BYTES=76800 PLANE_OUT=/tmp/kn24_plane.bin TAP_UNTIL=14
--
-- Then render it:
--   python3 tools/kn24_plane_to_png.py /tmp/kn24_plane.bin -o /tmp/plane.png
--
-- Also prints a value histogram, so a plane that is one flat fill is obvious without opening
-- the image.

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local UNTIL = tonumber(os.getenv("TAP_UNTIL")) or 14
local BASE  = tonumber(os.getenv("PLANE_BASE") or "") or 0x500B0000
local NB    = tonumber(os.getenv("PLANE_BYTES") or "") or (320 * 240)
local OUT   = os.getenv("PLANE_OUT") or "/tmp/kn24_plane.bin"

_G.PD = _G.PD or {}

_G.PD.h = emu.add_machine_frame_notifier(function()
    if _G.PD.done or mac.time.seconds < UNTIL then return end
    _G.PD.done = true

    local f, err = io.open(OUT, "wb")
    if not f then
        log("PD FAIL -- cannot open " .. OUT .. ": " .. tostring(err))
        mac:exit()
        return
    end

    local hist = {}
    local chunk = {}
    for i = 0, NB - 1 do
        local ok, b = pcall(function() return prog:read_u8(BASE + i) end)
        b = ok and b or 0
        hist[b] = (hist[b] or 0) + 1
        chunk[#chunk + 1] = string.char(b)
        -- write in blocks: string.char per byte into one concat at the end would peak memory
        if #chunk >= 4096 then f:write(table.concat(chunk)); chunk = {} end
    end
    if #chunk > 0 then f:write(table.concat(chunk)) end
    f:close()

    log(string.format("PD wrote %d bytes from 0x%08X to %s", NB, BASE, OUT))
    local l = {}
    for v, c in pairs(hist) do l[#l + 1] = { v, c } end
    table.sort(l, function(a, b) return a[2] > b[2] end)
    local distinct = #l
    log(string.format("PD %d distinct byte values; top:", distinct))
    for i = 1, math.min(8, #l) do
        log(string.format("   0x%02X  %7d  %5.1f%%", l[i][1], l[i][2], 100.0 * l[i][2] / NB))
    end
    if distinct <= 2 then
        log("PD ---- the plane is essentially a FLAT FILL. Nothing was drawn into it.")
    else
        log("PD ---- the plane has structure; render it and look before theorising further.")
    end
    mac:exit()
end)
