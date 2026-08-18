-- encoder_input_watch.lua -- does keyboard/mouse input reach the ENCODER port AT ALL?
--
-- QUESTION ANSWERED: when you press the wheel's increment/decrement keys, does the ioport value
-- actually move? This separates two very different faults that look identical on screen:
--
--   value moves, tempo does not  -> the input works; the driver's handling of it is wrong
--   value never moves            -> the input never reaches the port; the driver is blameless
--
-- ⚠ WHY THIS IS NEEDED: on the KN5000 the on-screen knob can be dragged and the tempo follows,
--   while the keys do nothing. That is NOT evidence that input works -- the layout script calls
--   field:set_value() directly and bypasses MAME's analog input pipeline entirely. Only a probe
--   on the port value can tell the two apart.
--
--   ./tools/rig.sh encoder_input_watch kn5000 -s 120 -- -plugin layout -pluginspath ./plugins
--   ENC_PORT=":ENCODER"    (default; the kn7000_mame overlay uses ":cpanel:ENCODER")
--
-- Prints a line every time the value changes, plus a heartbeat every 5 s so you can see it is
-- alive. Press the wheel keys while it runs.

local mac = manager.machine
local function log(s) emu.print_error(s) end
local TAG = os.getenv("ENC_PORT") or ":ENCODER"

local port = mac.ioport.ports[TAG] or mac.ioport.ports[":cpanel:ENCODER"]
if not port then log("EIW FATAL -- no port " .. TAG) return end
local fld; for _, f in pairs(port.fields) do fld = f end

_G.EIW = _G.EIW or { last = nil, lastlive = nil, n = 0, beat = -1 }

_G.EIW.h = emu.add_machine_frame_notifier(function()
    local S = _G.EIW
    local t = mac.time.seconds

    local okr, rv = pcall(function() return port:read() end)
    local okl, lv = pcall(function() return fld.live and fld.live().value end)
    rv = okr and rv or -1
    lv = okl and lv or -1

    if S.last == nil then
        S.last, S.lastlive = rv, lv
        log(string.format("EIW watching %s -- initial port:read()=%d field.live=%d", TAG, rv, lv))
        log("EIW press the wheel's keys now; every change prints a line")
        return
    end

    if rv ~= S.last or lv ~= S.lastlive then
        S.n = S.n + 1
        log(string.format("EIW t=%6.2f  port:read() %d -> %d   field.live %d -> %d",
            t, S.last, rv, S.lastlive, lv))
        S.last, S.lastlive = rv, lv
    end

    local b = math.floor(t / 5)
    if b ~= S.beat then
        S.beat = b
        log(string.format("EIW t=%3d  (still watching; %d change(s) so far, value=%d)", t, S.n, rv))
    end
end)
