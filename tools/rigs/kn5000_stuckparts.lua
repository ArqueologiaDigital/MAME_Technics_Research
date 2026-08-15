-- kn5000_stuckparts.lua -- are the 4 stuck sequencer parts the same bug as the stuck EG voices?
--
-- Established 2026-08-15: after the Feature Presentation's first song stops at t=139.47, the
-- next song never starts because FDemo_MultiGuardCheck sees DRAM[0x10420] = 0x044A -- four
-- sequencer parts (bits 1, 3, 6, 10) that never clear. The docs call these the "4 stuck
-- accompaniment parts" and blame missing waveform ROMs.
--
-- Task-queue item P3 separately records "stuck EG voices: Type A voices park at their final EG
-- segment target forever at ~-77 dB, so eg_running never clears". Four stranded parts and
-- envelopes that never terminate may well be ONE bug seen from two ends. This rig measures
-- both at once so the question is settled by data rather than by plausibility.
--
-- The tone generator's active-voice bitmap is the SUB-CPU read at 0x100000 (kn5000.cpp:
-- status_r / "active-voice bitmap poll"). This rig TAPS the firmware's own reads rather than
-- issuing its own: a Lua read would invoke the device handler and could perturb the very state
-- being measured.
--
--   ./run.sh kn5000 -window -nothrottle -seconds_to_run 200 \
--       -cfg_directory <fresh> -nvram_directory <fresh> \
--       -autoboot_script tools/rigs/kn5000_stuckparts.lua
--
-- Prints once a second from SP_FROM: the parts mask and the most recent active-voice bitmap
-- the firmware saw, plus a popcount of each. If voices stay active while parts stay stuck,
-- the two are the same phenomenon; if voices go quiet while parts remain set, they are not.

local mac  = manager.machine
local mp   = mac.devices[":maincpu"].spaces["program"]
local subd = mac.devices[":subcpu"]
local function log(s) emu.print_error(s) end
local function u8(a)  local ok,v = pcall(function() return mp:read_u8(a)  end) return ok and v or -1 end
local function u16(a) local ok,v = pcall(function() return mp:read_u16(a) end) return ok and v or -1 end

local FROM     = tonumber(os.getenv("SP_FROM")) or 120
local PRESS_AT = tonumber(os.getenv("SP_PRESS_AT")) or 20.0

local function popcount(x)
    local n = 0
    while x > 0 do n = n + (x & 1) x = x >> 1 end
    return n
end

_G.SPK = _G.SPK or { phase = "wait", base = 0, last = -1, voices = -1, nreads = 0 }

-- Observe, do not disturb: log what the firmware reads from the active-voice poll.
if subd then
    _G.SPK.tap = subd.spaces["program"]:install_read_tap(0x100000, 0x100001, "tgstat",
        function(offset, data, mask)
            _G.SPK.voices = data & 0xFFFF
            _G.SPK.nreads = _G.SPK.nreads + 1
            return nil
        end)
end

local function field(tag, mask)
    local p = mac.ioport.ports[":" .. tag] or mac.ioport.ports[":cpanel:" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do if f.mask == mask then return f end end
    return nil
end
local function btn(tag, mask, v) local f = field(tag, mask) if f then f:set_value(v) end end

_G.SPK.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    local S = _G.SPK
    if S.phase == "wait" and t >= PRESS_AT then btn("CPL_SEG3", 0x01, 1) S.phase = "d1" S.base = t
    elseif S.phase == "d1" and t >= S.base + 0.3 then btn("CPL_SEG3", 0x01, 0) S.phase = "d2" S.base = t
    elseif S.phase == "d2" and t >= S.base + 1.5 then btn("CPL_SEG9", 0x02, 1) S.phase = "d3" S.base = t
    elseif S.phase == "d3" and t >= S.base + 0.3 then btn("CPL_SEG9", 0x02, 0) S.phase = "d4" S.base = t
    elseif S.phase == "d4" and t >= S.base + 1.5 then btn("CPL_SEG10", 0x01, 1) S.phase = "d5" S.base = t
    elseif S.phase == "d5" and t >= S.base + 0.3 then btn("CPL_SEG10", 0x01, 0) S.phase = "obs"
        log(string.format("SPK demo engaged at t=%.2f", t))
    end
    if S.phase ~= "obs" then return end

    local sec = math.floor(t)
    if sec >= FROM and sec ~= S.last then
        S.last = sec
        local parts = u16(0x10420)
        log(string.format("SPK t=%3d parts=0x%04X (%d set)  voices=0x%04X (%d active, %d polls)  transport=0x%02X",
            sec, parts, popcount(parts < 0 and 0 or parts),
            S.voices < 0 and 0 or S.voices, popcount(S.voices < 0 and 0 or S.voices),
            S.nreads, u8(0x0420)))
    end
end)
