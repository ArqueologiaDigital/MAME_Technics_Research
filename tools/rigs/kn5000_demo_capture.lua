-- kn5000_demo_capture.lua -- boot, start the Feature Presentation demo, hold it playing.
-- rig-machine: kn5000
--
-- Purpose: give -wavwrite something to record that actually exercises the tone generator,
-- including the DRUM parts. The gate's liveness check sits at the home screen with no notes
-- playing, so it cannot see an audio change at all (project RULE 12: a test with no notes
-- playing is not a test).
--
-- The demo is the cheapest whole-instrument stimulus available: it drives the sequencer, the
-- accompaniment engine and the drum parts from ROM, deterministically, with no user input
-- beyond one button.
--
-- DEMO = CPL_SEG3 mask 0x01 (from notes/kn5000-demo-probes/cp_press.lua). Pressed at t=34 s,
-- once the boot has settled; held 0.5 s because a shorter tap is cleared by the input
-- frame-update before the 250 Hz panel scan samples it.
--
--   ./tools/rig.sh kn5000_demo_capture kn5000 -s 90 -w out.wav
--
-- ⚠ Delete nvram/kn5000/nvram1 first: 1 MB of work DRAM is persisted as NVRAM, so a stale
-- one changes what the run does.

local mac = manager.machine
local function log(s) emu.print_error(s) end

local PRESS_AT = tonumber(os.getenv("DEMO_PRESS_AT")) or 34.0
local HOLD     = tonumber(os.getenv("DEMO_HOLD")) or 0.5

local function field(tag, mask)
    local p = mac.ioport.ports[":" .. tag] or mac.ioport.ports[":cpanel:" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do if f.mask == mask then return f end end
    return nil
end

-- Held in a global: the Lua GC collects a bare local handle and the notifier stops firing.
_G.DC = _G.DC or { state = 0 }

_G.DC.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    local d = _G.DC
    if d.state == 0 and t >= PRESS_AT then
        d.f = field("CPL_SEG3", 0x01)
        if not d.f then
            log("DEMOCAP FAIL -- no CPL_SEG3 field; the demo will not start")
            d.state = 3
            return
        end
        d.f:set_value(1)
        log(string.format("DEMOCAP press DEMO at t=%.2f", t))
        d.state = 1
    elseif d.state == 1 and t >= PRESS_AT + HOLD then
        d.f:set_value(0)
        log(string.format("DEMOCAP release at t=%.2f -- capturing until -seconds_to_run", t))
        d.state = 2
    end
end)
