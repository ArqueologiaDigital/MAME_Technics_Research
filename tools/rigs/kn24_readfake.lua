-- kn24_readfake.lua -- force a memory region to read back a chosen value, and see what changes.
-- rig-machine: kn2400
--
-- The KN2400's table ROM is undumped and reads back as all-0xFF. Everything measured so far is
-- consistent with two very different stories:
--   (a) the missing ROM matters -- e.g. a font pointer in its descriptor reads 0xFFFFFFFF, the
--       text drawer bails, and the boxes get drawn with no glyphs in them;
--   (b) the missing ROM is irrelevant to text and the glyph pass is broken for another reason.
--
-- A read tap that RETURNS A VALUE lets the region be given different contents through the real
-- bus, without patching the driver or faking a dump. If the screen changes when the region
-- stops reading 0xFF, story (a) gains support; if nothing changes across several substitute
-- values, (b) does.
--
-- ⚠ THIS IS NOT A FIX AND MUST NEVER BECOME ONE. It fabricates ROM contents. It exists to
--   answer a yes/no question about causality. Nothing it produces is a dump, and no screenshot
--   taken under it should be presented as the machine working.
--
-- ⚠ POSITIVE CONTROL REQUIRED. If read taps cannot modify data on this build, every run looks
--   like a clean negative. So always run the control, which forces the UI PLANE to a constant:
--   the compositor reads that plane over the bus, so the screen MUST change.
--
--     FAKE=plane ./tools/rig.sh kn24_readfake kn2400 -s 34    # control: expect a CHANGED frame
--     FAKE=table ./tools/rig.sh kn24_readfake kn2400 -s 34    # experiment
--     FAKE=none  ./tools/rig.sh kn24_readfake kn2400 -s 34    # baseline
--
--   Compare the snapshots between runs (rig.sh --keep, then cmp the PNGs). If the CONTROL's
--   frame is identical to the baseline, taps cannot modify here and the experiment says
--   nothing -- report that, do not report a negative.
--
-- Env: FAKE (none|table|plane), FAKE_VALUE (default 0x00), T (snapshot time, default 30)

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local WHICH = os.getenv("FAKE") or "none"
local VAL   = tonumber(os.getenv("FAKE_VALUE") or "") or 0x00
local T     = tonumber(os.getenv("T") or "") or 30

local RANGES = {
    table = { 0x48000000, 0x483FFFFF, "table ROM (undumped, normally all-0xFF)" },
    plane = { 0x500ADE34, 0x500C0A33, "UI source plane (positive control)" },
}

_G.RF = _G.RF or { n = 0 }

if WHICH ~= "none" then
    local r = RANGES[WHICH]
    if not r then
        log("RF unknown FAKE=" .. WHICH .. " (use none|table|plane)")
    else
        -- Build a full-width pattern from the byte value, so any access width sees it.
        local word = VAL | (VAL << 8) | (VAL << 16) | (VAL << 24)
        local ok, tap = pcall(function()
            return prog:install_read_tap(r[1], r[2], "fake", function(offset, data, mask)
                _G.RF.n = _G.RF.n + 1
                return word
            end)
        end)
        if ok then
            _G.RF.tap = tap
            log(string.format("RF faking %s = 0x%02X over 0x%08X..0x%08X -- %s",
                WHICH, VAL, r[1], r[2], r[3]))
        else
            log("RF could not install the tap: " .. tostring(tap))
        end
    end
else
    log("RF baseline -- no substitution")
end

_G.RF.h = emu.add_machine_frame_notifier(function()
    if _G.RF.done or mac.time.seconds < T then return end
    _G.RF.done = true
    log(string.format("RF mode=%s value=0x%02X substituted_reads=%d", WHICH, VAL, _G.RF.n))
    if WHICH ~= "none" and _G.RF.n == 0 then
        log("RF ⚠ the tap never fired -- the range is wrong or unused. Not a negative result.")
    end
    local scr
    for _, s in pairs(mac.screens) do scr = s break end
    if scr then
        local ok, px = pcall(function() return scr:pixels() end)
        if ok and type(px) == "string" then
            local seen, distinct, hash = {}, 0, 5381
            for i = 1, #px - 3, 64 do
                local v = px:byte(i) * 16777216 + px:byte(i + 1) * 65536
                        + px:byte(i + 2) * 256 + px:byte(i + 3)
                if not seen[v] then seen[v] = true distinct = distinct + 1 end
                hash = (hash * 33 + v) % 4294967296
            end
            log(string.format("RF screen distinct=%d hash=%08x", distinct, hash))
        end
    end
    mac.video:snapshot()
    mac:exit()
end)
