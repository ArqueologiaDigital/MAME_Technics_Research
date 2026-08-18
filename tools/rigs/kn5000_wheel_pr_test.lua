-- kn5000_wheel_pr_test.lua -- acceptance test for the upstream TEMPO/PROGRAM wheel PR.
-- rig-machine: kn5000
--
-- QUESTION ANSWERED: does turning the data wheel change the on-screen tempo, on EVERY firmware
-- revision the driver offers? That is the test the previous DRAM-poke implementation could not
-- pass: it hardcoded the firmware's scan-list address, which is 0x8E94 only on v8/v9/v10 (v7 uses
-- 0x8DF8, v5/v6 use 0x8DD4 -- and v5/v6 use 0x8E94 for something else, so the poke corrupted it).
--
-- The PR reports the wheel over the control-panel serial link instead, as [0xD7, detent count],
-- which is encoded identically in all six dumped revisions.
--
-- SIGNAL: the tempo word in main-CPU DRAM at 0xFC62, low 9 bits (120 at boot).
-- STIMULUS: step the :ENCODER positional control one position at a time.
--
--   ./tools/rig.sh kn5000_wheel_pr_test kn5000 -s 40 -- -bios v5
--   WHEEL_DETENTS=20 WHEEL_EVERY=12 ...
--
-- PASS: bpm rises by WHEEL_DETENTS, then falls back to where it started. FAIL: any other value
-- (0 = the wheel is not reaching the firmware at all, which is what v5/v6/v7 did before).
--
-- ⚠ IT TESTS BOTH DIRECTIONS, and the first version did not. Turning only one way passes on an
--   implementation whose other direction is broken or inverted -- exactly the defect Felipe hit
--   from the keyboard while this rig was reporting PASS. A test that exercises half the control
--   is not a test of the control.
--
-- ⚠ IT ALSO DOES NOT TEST THE KEY BINDINGS. It drives the field with set_value(), so it proves
--   the wire path and says NOTHING about whether a keystroke reaches the control. Use
--   tools/rigs/input_seq_probe.lua for that, and a human for the rest.
--
-- ⚠ Uses the PR's port shape, ":ENCODER" on the driver. In the kn7000_mame overlay the port is
--   owned by the panel device and is ":cpanel:ENCODER"; both are tried so this runs against
--   either tree.

local mac = manager.machine
local function log(s) emu.print_error(s) end

local DETENTS = tonumber(os.getenv("WHEEL_DETENTS") or "") or 20
local EVERY   = tonumber(os.getenv("WHEEL_EVERY") or "") or 12   -- frames between detents
local START   = tonumber(os.getenv("WHEEL_START") or "") or 24   -- let the machine settle first

local port = mac.ioport.ports[":ENCODER"] or mac.ioport.ports[":cpanel:ENCODER"]
if port == nil then
    log("WPR FATAL -- no ENCODER port (is this the rebuilt binary?)")
    mac:exit()
    return
end
local fld = nil
for _, f in pairs(port.fields) do fld = f end
log(string.format("WPR port found, field=%q", fld and fld.name or "?"))

local prog = mac.devices[":maincpu"].spaces["program"]
local function bpm()
    local ok, v = pcall(function() return prog:read_u16(0xFC62) end)
    return ok and (v & 0x1FF) or -1
end

_G.WPR = _G.WPR or { frame = 0, emitted = 0, pos = 0, phase = 0 }

_G.WPR.h = emu.add_machine_frame_notifier(function()
    local S = _G.WPR
    local t = mac.time.seconds
    S.frame = S.frame + 1

    if S.phase == 0 then                        -- wait for the machine to settle
        if t < START then return end
        S.phase = 1
        S.base = bpm()
        log(string.format("WPR start: bpm=%d", S.base))
    elseif S.phase == 1 then                    -- turn CLOCKWISE
        if S.emitted >= DETENTS then
            S.phase = 2
            S.settle = S.frame + 90
            return
        end
        if S.frame % EVERY == 0 then
            S.pos = (S.pos + 1) % 24
            pcall(function() fld:set_value(S.pos) end)
            S.emitted = S.emitted + 1
        end
    elseif S.phase == 2 then
        if S.frame < S.settle then return end
        S.up = bpm()
        log(string.format("WPR up  : %d detent(s) CW  -> bpm %d (delta %+d, expect %+d)",
            S.emitted, S.up, S.up - S.base, DETENTS))
        S.phase = 3
        S.emitted = 0
    elseif S.phase == 3 then                    -- and back ANTICLOCKWISE
        if S.emitted >= DETENTS then
            S.phase = 4
            S.settle = S.frame + 90
            return
        end
        if S.frame % EVERY == 0 then
            S.pos = (S.pos - 1 + 24) % 24
            pcall(function() fld:set_value(S.pos) end)
            S.emitted = S.emitted + 1
        end
    elseif S.phase == 4 then
        if S.frame < S.settle then return end
        S.phase = 5
        local down = bpm()
        log(string.format("WPR down: %d detent(s) CCW -> bpm %d (delta %+d, expect %+d)",
            S.emitted, down, down - S.up, -DETENTS))

        local up_ok = (S.up - S.base) == DETENTS
        local dn_ok = (down - S.up) == -DETENTS
        local net_ok = down == S.base
        log(string.format("WPR net : %d -> %d (started at %d)", S.base, down, S.base))
        if up_ok and dn_ok and net_ok then
            log("WPR PASS -- both directions, and it returns to where it started")
        else
            if not up_ok then log("WPR FAIL -- clockwise did not give one step per detent") end
            if not dn_ok then log("WPR FAIL -- anticlockwise did not give one step per detent") end
            if not net_ok and up_ok and dn_ok then log("WPR FAIL -- did not return to the start") end
            if (S.up - S.base) == 0 then log("WPR   (clockwise moved nothing: the wheel is not reaching the firmware)") end
            if (down - S.up) == 0 then log("WPR   (anticlockwise moved nothing: one direction is dead)") end
        end
        mac:exit()
    end
end)
