-- kn5000_poweroff.lua -- does the modelled POWER switch let the firmware save its state?
-- rig-machine: kn5000
--
-- Verification stage (a) of side-quests/pending/kn5000_splash_animation.txt. The driver now has
-- a POWER control that pulses the CPU's NMI and delays MAME's exit by POWER_DOWN_MS, so the
-- firmware's own NMI_StorePayloadChecksums (0xEF08D4) can run. What has to be shown is that the
-- handler actually reaches its last step: copying DRAM[0xF980..0xFFEE] into the battery-backed
-- IC21 SRAM at 0x1E8000. That block contains the two payload checksums at 0xFFD2/0xFFD4, and
-- the next boot restores it (0xEF0580) -- which is what makes the splash appear.
--
-- ⚠ Timing matters: the guard the handler tests (0x0400 == 0x80) is armed by the FIRMWARE at
--   t=7.69 (kn5000_nmiguard.lua). Pressing POWER before that would produce a legitimate no-op
--   and look like a broken switch, so the default press is well after it.
--
--   ./tools/rig.sh kn5000_poweroff kn5000 -s 45
--   PRESS_AT=30 ...
--
-- Reports each SRAM write region and a running count. MAME exits by itself when the driver's
-- power-down timer expires, so the tail of the log IS the result.

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local PRESS_AT = tonumber(os.getenv("PRESS_AT") or "") or 30
local SR_LO, SR_HI = 0x1E8000, 0x1E8FFF

_G.PO = _G.PO or { n = 0, lo = nil, hi = nil, pressed = false, shown = 0 }

_G.PO.tap = prog:install_write_tap(SR_LO, SR_HI, "sram", function(offset, data, mask)
    local S = _G.PO
    S.n = S.n + 1
    if not S.lo or offset < S.lo then S.lo = offset end
    if not S.hi or offset > S.hi then S.hi = offset end
    if S.shown < 4 then
        S.shown = S.shown + 1
        local t = mac.time.seconds + mac.time.attoseconds / 1e18
        log(string.format("PO t=%7.3f  SRAM 0x%06X <- 0x%04X", t, offset, data))
    end
    return nil
end)

_G.PO.h = emu.add_machine_frame_notifier(function()
    -- FRACTIONAL time: mac.time.seconds is whole seconds, and the power-down window is only
    -- POWER_DOWN_MS (100 ms), so a "+1 second" report never runs -- MAME has already exited.
    -- The first version of this rig did exactly that and produced a log that stopped at the
    -- press, which looks like a crash and is not one.
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    local S = _G.PO

    if not S.pressed and t >= PRESS_AT then
        S.pressed = true
        -- Confirm the guard first, so a null result cannot be blamed on the wrong thing.
        local okg, g = pcall(function() return prog:read_u8(0x0400) end)
        log(string.format("PO guard 0x0400 = 0x%02X %s", okg and g or -1,
            (okg and g == 0x80) and "(armed -- the handler will run)" or "(NOT armed -- expect nothing)"))
        log(string.format("PO SRAM writes before the press: %d", S.n))
        S.before = S.n

        local p = mac.ioport.ports[":POWER"]
        if not p then
            log("PO FAIL -- no :POWER port. Is this the rebuilt binary?")
            mac:exit()
            return
        end
        local f = nil
        for _, fl in pairs(p.fields) do if fl.mask == 0x01 then f = fl end end
        if not f then log("PO FAIL -- no field mask 0x01 on :POWER") mac:exit() return end
        f:set_value(1)
        log(string.format("PO POWER pressed at t=%.2f -- the driver should pulse NMI and delay exit", t))
    elseif S.pressed and not S.reported and t >= PRESS_AT + 0.05 then
        S.reported = true
        local after = S.n - (S.before or 0)
        log(string.format("PO SRAM writes AFTER the press: %d  (range 0x%06X..0x%06X)",
            after, S.lo or 0, S.hi or 0))
        if after > 0 then
            log("PO VERDICT: the firmware's power-down code RAN and reached the SRAM save.")
        else
            log("PO VERDICT: nothing reached the SRAM. The NMI did not fire, or the handler bailed.")
        end
    end
end)
