-- kn5000_p9_writer.lua -- WHO stops the Feature Presentation?
--
-- P9 is now pinned (notes/p9-stall-2026-08-15.log): the demo does not stall, it reaches its own
-- terminal STOP. Transport 0x0420 goes 0x04 -> 0x0C at t=139.48, then 0x00, with AccPlayMode
-- 0x22FC dropping 0x03 -> 0x00 and the sub-tick frozen at 0x18.
--
-- So the question is no longer "what wedged?" but "why does the firmware think the song ended
-- at 58%?". This rig answers the first half of that: it watches writes to the transport byte
-- and reports the PC of every writer, so the deciding code can be named instead of guessed.
--
-- Also taps AccPlayMode, because whichever of the two moves FIRST is the cause and the other
-- is the consequence -- and a one-second sampling cannot tell them apart.
--
--   ./run.sh kn5000 -window -nothrottle -seconds_to_run 150 \
--       -cfg_directory <fresh> -nvram_directory <fresh> \
--       -autoboot_script tools/rigs/kn5000_p9_writer.lua
--
-- Prints every write to either address once the demo is engaged:
--   P9W t=139.48 transport <- 0x0C  from PC=0x00FEE1A2
-- Values are logged for ALL writes, not just the stop, so the normal traffic is visible as a
-- control -- if 0x04 is written repeatedly by the same PC, that PC is the tick, not the stop.
--
-- ⚠ PC CAVEAT: the tlcs900 core prefetches, so the reported PC is near the writing
-- instruction but not guaranteed to BE it. Treat it as a neighbourhood to disassemble, not
-- as an exact address, and confirm against the disassembly before naming a function.

local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local sp  = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local PRESS_AT = tonumber(os.getenv("P9_PRESS_AT")) or 20.0

_G.P9W = _G.P9W or { phase = "wait", base = 0, n = 0, seen = {} }

local function pc()
    local ok, v = pcall(function() return cpu.state["PC"].value end)
    return ok and v or -1
end

-- The TLCS-900 bus is 16-bit: a tap range must be word-aligned, or MAME aborts with
-- "end address has low bits unset". So tap the containing word and pick the byte lane out
-- of the mask. (Learned the hard way: the first version fatal-errored on 0x0420-0x0420.)
local function watch(addr, name)
    local lo, hi = addr & ~1, (addr & ~1) + 1
    local odd = (addr & 1) == 1
    return sp:install_write_tap(lo, hi, name, function(offset, data, mask)
        local S = _G.P9W
        if S.phase ~= "obs" then return nil end
        -- Only report when THIS byte lane is actually being written.
        local lane = odd and 0xFF00 or 0x00FF
        if (mask & lane) == 0 then return nil end
        local t = mac.time.seconds + mac.time.attoseconds / 1e18
        local v = odd and ((data >> 8) & 0xFF) or (data & 0xFF)
        local p = pc()
        -- Log every DISTINCT (name, value, pc) once, plus always log a departure from 0x04,
        -- so the output stays readable over 100+ seconds of normal ticking.
        local key = string.format("%s/%02X/%08X", name, v, p)
        if not S.seen[key] then
            S.seen[key] = true
            log(string.format("P9W t=%7.2f %-11s <- 0x%02X  from PC=0x%08X   (first time)",
                t, name, v, p))
        end
        if name == "transport" and v ~= 0x04 and v ~= 0x00 then
            log(string.format("P9W ★ t=%7.2f %s <- 0x%02X from PC=0x%08X", t, name, v, p))
        end
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

_G.P9W.t1 = watch(0x0420, "transport")
_G.P9W.t2 = watch(0x22FC, "AccPlayMode")

_G.P9W.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    local S = _G.P9W
    if S.phase == "wait" and t >= PRESS_AT then btn("CPL_SEG3", 0x01, 1) S.phase = "d1" S.base = t
    elseif S.phase == "d1" and t >= S.base + 0.3 then btn("CPL_SEG3", 0x01, 0) S.phase = "d2" S.base = t
    elseif S.phase == "d2" and t >= S.base + 1.5 then btn("CPL_SEG9", 0x02, 1) S.phase = "d3" S.base = t
    elseif S.phase == "d3" and t >= S.base + 0.3 then btn("CPL_SEG9", 0x02, 0) S.phase = "d4" S.base = t
    elseif S.phase == "d4" and t >= S.base + 1.5 then btn("CPL_SEG10", 0x01, 1) S.phase = "d5" S.base = t
    elseif S.phase == "d5" and t >= S.base + 0.3 then btn("CPL_SEG10", 0x01, 0) S.phase = "obs"
        log(string.format("P9W demo engaged at t=%.2f -- watching 0x0420 and 0x22FC", t))
    end
end)
