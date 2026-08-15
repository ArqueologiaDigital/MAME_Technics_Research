-- kn5000_democountdown.lua -- does the demo countdown timer ever get armed?
-- rig-machine: kn5000
--
-- kn5000-docs/ssf-presentation.md: entering the Feature Presentation (state 0xE4) calls
-- Demo_ResetCountdownTimer, which sets DRAM[0x0D2F] = 15; the timer ticks down and at 10 it
-- parses the next slide and calls Demo_SelectEntry_PlaySong.
--
-- Measured 2026-08-15: DRAM[0x0D2F] reads 0 continuously from t=125 to t=210 while the machine
-- IS in state 0xE4. Either it was armed and expired long before, or it was never armed at all.
-- A write tap distinguishes those, which a periodic read cannot.
--
-- PRE-DECLARED: no writes at all  -> Demo_ResetCountdownTimer never runs; the timer system
--                                     never starts, and that is the defect.
--               writes of 15 then a countdown -> the timer works and the fault is downstream.
--               writes that stop mid-count     -> whatever ticks it stalls.
--
-- Deliberately NOT assuming the docs' address labels are right: this session already found
-- 0x10420 mislabelled, so treat 0x0D2F as a hypothesis under test, not a fact.
--
--   ./tools/rig.sh kn5000_democountdown kn5000 -s 170

local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local mp  = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local PRESS_AT = tonumber(os.getenv("CD_PRESS_AT")) or 20.0

_G.CD = _G.CD or { phase = "wait", base = 0, n = 0, seen = {}, last = -1 }

local function pc() local ok,v = pcall(function() return cpu.state["PC"].value end) return ok and v or -1 end

-- 16-bit bus: the tap range must be word-aligned. 0x0D2F is the ODD byte of the word at
-- 0x0D2E, so tap the word and select the high lane.
_G.CD.tap = mp:install_write_tap(0x0D2E, 0x0D2F, "countdown", function(offset, data, mask)
    local S = _G.CD
    -- Observe from t=0, NOT only after the navigation completes: the ARMING write (the
    -- initial 15) happens during demo entry, and a tap gated on the "obs" phase misses it by
    -- milliseconds -- the first value seen was already 12.
    if (mask & 0xFF00) == 0 then return nil end          -- only the 0x0D2F lane
    local v = (data >> 8) & 0xFF
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    S.n = S.n + 1
    local p = pc()
    local key = string.format("%02X/%08X", v, p)
    if not S.seen[key] then
        S.seen[key] = true
        log(string.format("CD t=%7.2f 0x0D2F <- %3d  PC=0x%08X   (first time)", t, v, p))
    end
    -- On the ARMING write (value 15), dump the stack: Demo_ResetCountdownTimer is
    -- 0xF86D86 (`ld (0x0d2f),0x0f ; ret`) and is entered by calr, so no absolute reference
    -- to it exists anywhere in the ROM -- a static caller search returns zero. The live
    -- stack is XSSP (system mode); TLCS-900 has no register called SP.
    if v == 15 and not S.dumped then
        S.dumped = true
        local ok, err = pcall(function()
            local spv = cpu.state["XSSP"].value
            log(string.format("CD ★★ ARM at PC=0x%08X  XSSP=0x%08X -- stack:", p, spv))
            for i = 0, 9 do
                local a = spv + i * 4
                local ok2, w = pcall(function() return mp:read_u32(a) end)
                if ok2 and w then
                    local tag = (w >= 0xE00000 and w <= 0xFFFFFF) and "  <- code" or ""
                    log(string.format("    XSSP+%2d 0x%08X = 0x%08X%s", i * 4, a, w, tag))
                end
            end
        end)
        if not ok then log("CD stack dump ERROR: " .. tostring(err)) end
    end
    if S.n <= 60 then
        log(string.format("CD t=%7.2f write #%d value=%3d PC=0x%08X", t, S.n, v, p))
    end
    return nil
end)

local function field(tag, mask)
    local p = mac.ioport.ports[":" .. tag] or mac.ioport.ports[":cpanel:" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do if f.mask == mask then return f end end
    return nil
end
local function btn(tag, mask, v) local f = field(tag, mask) if f then f:set_value(v) end end

_G.CD.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    local S = _G.CD
    if S.phase == "wait" and t >= PRESS_AT then btn("CPL_SEG3", 0x01, 1) S.phase = "d1" S.base = t
    elseif S.phase == "d1" and t >= S.base + 0.3 then btn("CPL_SEG3", 0x01, 0) S.phase = "d2" S.base = t
    elseif S.phase == "d2" and t >= S.base + 1.5 then btn("CPL_SEG9", 0x02, 1) S.phase = "d3" S.base = t
    elseif S.phase == "d3" and t >= S.base + 0.3 then btn("CPL_SEG9", 0x02, 0) S.phase = "d4" S.base = t
    elseif S.phase == "d4" and t >= S.base + 1.5 then btn("CPL_SEG10", 0x01, 1) S.phase = "d5" S.base = t
    elseif S.phase == "d5" and t >= S.base + 0.3 then btn("CPL_SEG10", 0x01, 0) S.phase = "obs"
        log(string.format("CD demo engaged at t=%.2f -- watching 0x0D2F", t))
    end
    if S.phase ~= "obs" then return end
    local sec = math.floor(t)
    if sec % 20 == 0 and sec ~= S.last then
        S.last = sec
        log(string.format("CD t=%3d  total writes so far: %d", sec, S.n))
    end
end)
