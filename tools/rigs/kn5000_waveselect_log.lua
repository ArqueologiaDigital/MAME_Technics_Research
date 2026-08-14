-- kn5000_waveselect_log.lua -- which waveform chunks does the machine ACTUALLY select?
--
-- Answers the reachability question directly, without an audio A/B and without a second build.
-- The 2026-08-14 detect_period change affects 35 chunks; a 90 s Feature Presentation capture
-- came out BIT-IDENTICAL between the two builds, which proves the demo never selects one of
-- them but says nothing about whether anything else does.
--
-- HOW: the tone generator is register-indirect on the SUB-CPU bus --
--     0x100000 = address latch (write)
--     0x100002 = data           (write)
-- and a per-voice register address is (group << 8) | (bank << 6) | channel, with
-- REG_CHANNEL_MASK 0x3F / REG_BANK_SHIFT 6 / REG_GROUP_SHIFT 8 (kn5000_tonegen.h).
-- The wave-select word is group 0, bank 1 -- i.e. addr & 0xFFC0 == 0x0040 -- and its value
-- decodes as  chunk = w & 0xFFF,  page = (w >> 12) & 3,  bank = (w >> 14) & 3.
--
-- Prints one line per DISTINCT wave-select word, with a count:
--     WAVESEL 0x505B bank=1 page=1 chunk=0x05B n=12
-- Cross-reference the list against the affected chunks with
-- tools/kn5000_referenced_fallbacks.py -- do not hard-code that set here, so this rig stays
-- a plain observation with no hypothesis baked in.
--
--   ./run.sh kn5000 -window -nothrottle -seconds_to_run 90 \
--       -autoboot_script tools/rigs/kn5000_waveselect_log.lua
--
-- ⚠ Delete nvram/kn5000/nvram1 first, and use a fresh -cfg_directory.

local mac = manager.machine
local sub = mac.devices[":subcpu"]
local function log(s) emu.print_error(s) end

local UNTIL = tonumber(os.getenv("WS_UNTIL")) or 88
-- MAME takes only ONE -autoboot_script, so the stimulus lives here too rather than in a
-- separate rig. DEMO_PRESS_AT=0 disables it (e.g. to observe MIDI-driven playback instead).
local PRESS_AT = tonumber(os.getenv("DEMO_PRESS_AT")) or 34.0

if not sub then
    log("WAVESEL FAIL -- no :subcpu device")
    return
end
local sp = sub.spaces["program"]
-- Main-CPU demo/transport signals, so one run answers BOTH "what plays?" and "did the demo
-- actually start?". Addresses from notes/kn5000-demo-playback-stall.md.
local mp = mac.devices[":maincpu"].spaces["program"]
local SIG = { {0x0420, "transport"}, {0x0417, "subtick"}, {0x32ed, "watchdog"}, {0x22FC, "AccPlayMode"} }

-- Globals: a bare local handle is collected by the Lua GC and the taps stop firing.
_G.WS = _G.WS or { latch = 0, seen = {}, order = {}, nwrites = 0 }

_G.WS.t1 = sp:install_write_tap(0x100000, 0x100001, "wsaddr", function(offset, data, mask)
    _G.WS.latch = data & 0xFFFF
    return nil
end)

_G.WS.t2 = sp:install_write_tap(0x100002, 0x100003, "wsdata", function(offset, data, mask)
    local w = _G.WS
    w.nwrites = w.nwrites + 1
    if (w.latch & 0xFFC0) == 0x0040 then          -- group 0, bank 1 = wave select
        local v = data & 0xFFFF
        if not w.seen[v] then
            w.seen[v] = 0
            w.order[#w.order + 1] = v
        end
        w.seen[v] = w.seen[v] + 1
    end
    return nil
end)

local function field(tag, mask)
    local p = mac.ioport.ports[":" .. tag] or mac.ioport.ports[":cpanel:" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do if f.mask == mask then return f end end
    return nil
end

_G.WS.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    -- Start the demo. It needs NAVIGATION, not one button: DEMO -> LEFT 4 -> LEFT 2,
    -- copied from notes/kn5000-demo-probes/demo_probe.lua. Pressing DEMO alone leaves
    -- transport/AccPlayMode flat at 0x00 and the machine silent -- which is how a 90 s
    -- "A/B" of two silent captures got mistaken for a bit-identical result on 2026-08-14.
    if PRESS_AT > 0 then
        local N = _G.WS.nav or { phase = "wait", base = 0 }
        _G.WS.nav = N
        local function btn(tag, mask, v)
            local f = field(tag, mask)
            if f then f:set_value(v) end
        end
        if N.phase == "wait" and t >= PRESS_AT then
            btn("CPL_SEG3", 0x01, 1); N.phase = "d1"; N.base = t
        elseif N.phase == "d1" and t >= N.base + 0.3 then
            btn("CPL_SEG3", 0x01, 0); N.phase = "d2"; N.base = t
        elseif N.phase == "d2" and t >= N.base + 1.5 then
            btn("CPL_SEG9", 0x02, 1); N.phase = "d3"; N.base = t
        elseif N.phase == "d3" and t >= N.base + 0.3 then
            btn("CPL_SEG9", 0x02, 0); N.phase = "d4"; N.base = t
        elseif N.phase == "d4" and t >= N.base + 1.5 then
            btn("CPL_SEG10", 0x01, 1); N.phase = "d5"; N.base = t
        elseif N.phase == "d5" and t >= N.base + 0.3 then
            btn("CPL_SEG10", 0x01, 0); N.phase = "obs"
            log(string.format("WAVESEL demo engaged at t=%.2f", t))
        end
    end

    -- Track the extremes of each demo signal; a single end-of-run sample can miss a burst.
    _G.WS.sig = _G.WS.sig or {}
    for _, e in ipairs(SIG) do
        local ok, v = pcall(function() return mp:read_u8(e[1]) end)
        if ok and v then
            local r = _G.WS.sig[e[2]] or { min = 255, max = 0, last = -1 }
            if v < r.min then r.min = v end
            if v > r.max then r.max = v end
            r.last = v
            _G.WS.sig[e[2]] = r
        end
    end
    if _G.WS.done or mac.time.seconds < UNTIL then return end
    _G.WS.done = true
    local w = _G.WS
    log(string.format("WAVESEL total TG data writes=%d, distinct wave-select words=%d",
        w.nwrites, #w.order))
    table.sort(w.order)
    for _, v in ipairs(w.order) do
        log(string.format("WAVESEL 0x%04X bank=%d page=%d chunk=0x%03X n=%d",
            v, (v >> 14) & 3, (v >> 12) & 3, v & 0xFFF, w.seen[v]))
    end
    for _, e in ipairs(SIG) do
        local r = w.sig and w.sig[e[2]]
        if r then
            log(string.format("SIGNAL %-12s 0x%04X  min=0x%02X max=0x%02X last=0x%02X",
                e[2], e[1], r.min, r.max, r.last))
        end
    end
    if #w.order == 0 then
        log("WAVESEL none -- no voice selected a waveform in this window. The stimulus is "
            .. "not reaching the tone generator at all.")
    end
    mac:exit()
end)
