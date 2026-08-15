-- liveness.lua -- did this machine actually boot and draw its UI?
--
-- Model-agnostic on purpose: every Technics driver here has a screen, so one probe
-- serves all seven rather than needing a per-model RAM address that rots when the
-- firmware layout moves.
--
-- At LIVENESS_AT seconds (default 25) it samples the framebuffer and reports:
--   distinct  -- how many different pixel values are on screen
--   hash      -- an order-sensitive checksum of the sampled pixels
--
-- PASS means distinct >= LIVENESS_MIN (default 4). A machine that never draws sits
-- at 1 (uniform fill); a machine that draws only a background gradient sits at 2-3.
--
-- ⚠ PASS is a floor, not a health check. Measured 2026-08-14: kn7000=12, kn5000=20,
-- kn6000=9, kn6500=8, but kn2400=kn2600=4 -- barely over the line, consistent with
-- their known "renders no text" defect. Compare against the per-model baseline in
-- gate.sh rather than treating any PASS as good.
--
-- Reports SKIP, not FAIL, for a driver with no screen device (kn1500 renders through
-- SVG artwork off an HD44780). Such models need their own liveness signal.
-- The hash is NOT a pass criterion here -- it is printed so a caller can pin a
-- golden value once a model's screen is known-good.
--
-- Prints exactly one line to stderr:
--   LIVENESS <machine> distinct=<n> hash=<hex> <PASS|FAIL>
--
-- Usage (no rig-machine: header on purpose -- the gate runs this on every model):
--   LIVENESS_AT=25 LIVENESS_MIN=18 ./tools/rig.sh liveness kn5000 -s 27

local mac = manager.machine
local function log(s) emu.print_error(s) end

local AT  = tonumber(os.getenv("LIVENESS_AT")) or 25
local MIN = tonumber(os.getenv("LIVENESS_MIN")) or 4

-- Held in a global: a bare local handle is collected by the Lua GC and the
-- notifier silently never fires. This has cost the project real time before.
_G.LV = _G.LV or {}

_G.LV.h = emu.add_machine_frame_notifier(function()
    if _G.LV.done then return end
    if mac.time.seconds < AT then return end
    _G.LV.done = true

    local scr
    for _, s in pairs(mac.screens) do scr = s break end
    if not scr then
        -- Not a failure: some drivers (kn1500) render through SVG artwork driven by an
        -- HD44780, with no MAME screen device at all. This probe cannot speak about them.
        log("LIVENESS " .. emu.romname() .. " distinct=- hash=- SKIP (no screen device; "
            .. "needs a per-model signal)")
        mac:exit()
        return
    end

    local ok, px = pcall(function() return scr:pixels() end)
    if not ok or type(px) ~= "string" then
        log("LIVENESS " .. emu.romname() .. " distinct=0 hash=- FAIL (no pixels)")
        mac:exit()
        return
    end

    -- Sample every 16th pixel: enough to characterise a 640x240 UI, fast in pure Lua.
    local seen, distinct, hash = {}, 0, 5381
    for i = 1, #px - 3, 64 do
        local v = px:byte(i) * 16777216 + px:byte(i + 1) * 65536
                + px:byte(i + 2) * 256 + px:byte(i + 3)
        if not seen[v] then seen[v] = true distinct = distinct + 1 end
        hash = (hash * 33 + v) % 4294967296
    end

    log(string.format("LIVENESS %s distinct=%d hash=%08x %s",
        emu.romname(), distinct, hash, distinct >= MIN and "PASS" or "FAIL"))
    mac:exit()
end)
