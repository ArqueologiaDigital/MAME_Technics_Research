-- kn5000_demo_capture.lua -- boot, start the internal Feature Presentation demo, hold it playing.
-- rig-machine: kn5000
--
-- QUESTION ANSWERED: give -wavwrite something that actually exercises the tone generator,
-- including the drum parts, deterministically and with no user input beyond the panel.
--
-- ⚠ STARTING THE DEMO TAKES THREE PRESSES, NOT ONE. This rig previously pressed DEMO alone
--   and claimed that started the demo. It does not: it opens a menu, and the machine then
--   sits there forever, producing a capture that is bit-for-bit as silent as a broken sound
--   device. That mistake cost most of a session and produced a "silent, therefore the sound
--   device is broken" conclusion that was entirely wrong. The sequence, read off the screen:
--
--     1. DEMO            (CPL_SEG3  0x01)  -> the DEMONSTRATION menu
--                                             (PERFORMANCES / FEATURE PRESENTATION)
--     2. LEFT 4          (CPL_SEG9  0x02)  -> the FEATURE PRESENTATION page
--     3. LEFT 2          (CPL_SEG10 0x01)  -> "Start the internal DEMO"
--
--   The other branch, DEMO -> LEFT 2 -> LEFT 3, starts the PERFORMANCES "Accordion Medley",
--   which is also a fine stimulus (76 note-on gates in its first 4 seconds).
--
--   IF A SCRIPTED PRESS SEEMS TO DO NOTHING, TAKE A SCREENSHOT (tools/rigs/kn5000_screenshots.lua)
--   BEFORE THEORISING ABOUT THE CODE. Nine presses and two wrong hypotheses were spent here
--   before anyone looked at the display, which answered it immediately.
--
--   ./tools/rig.sh kn5000_demo_capture kn5000 -s 130 -- -wavwrite out.wav
--
-- Each press is held 0.5 s: a shorter tap can be cleared by the input frame update before the
-- panel's own scan samples it.

local mac = manager.machine
local function log(s) emu.print_error(s) end

local START = tonumber(os.getenv("DEMO_PRESS_AT") or "") or 40.0
local HOLD  = tonumber(os.getenv("DEMO_HOLD") or "") or 0.5
local GAP   = tonumber(os.getenv("DEMO_GAP") or "") or 4.0

local function field(tag, mask)
    local p = mac.ioport.ports[":cpanel:" .. tag] or mac.ioport.ports[":" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do
        if f.mask == mask then return f end
    end
    return nil
end

local SEQUENCE = {
    { "DEMO",   field("CPL_SEG3",  0x01) },
    { "LEFT 4", field("CPL_SEG9",  0x02) },   -- FEATURE PRESENTATION
    { "LEFT 2", field("CPL_SEG10", 0x01) },   -- Start the internal DEMO
}

for _, step in ipairs(SEQUENCE) do
    if step[2] == nil then
        log(string.format("DEMOCAP FATAL -- panel field for %q not found", step[1]))
        mac:exit()
        return
    end
end

_G.DEMOCAP = _G.DEMOCAP or { i = 1 }

_G.DEMOCAP.h = emu.add_machine_frame_notifier(function()
    local S = _G.DEMOCAP
    local t = mac.time.seconds
    if S.i > #SEQUENCE then return end

    local at = START + (S.i - 1) * GAP
    local name, f = SEQUENCE[S.i][1], SEQUENCE[S.i][2]

    if not S.down and t >= at then
        f:set_value(1)
        S.down = true
        log(string.format("DEMOCAP press %s at t=%.2f", name, t))
    elseif S.down and t >= at + HOLD then
        f:set_value(0)
        S.down = false
        S.i = S.i + 1
        if S.i > #SEQUENCE then
            log("DEMOCAP demo started -- capturing until -seconds_to_run")
        end
    end
end)
