-- cpu_state_probe.lua -- what registers does this CPU actually expose to Lua?
--
-- Guessing register names wastes whole emulator runs. On 2026-08-15 a stack-dump rig looked
-- for "XSP" and "SP" on the KN5000's TMP94C241, found neither, and produced NO OUTPUT AT ALL
-- for a 10-minute run -- the TLCS-900 exposes **XNSP** (normal stack pointer) and **XSSP**
-- (system stack pointer), and has no register called SP. This probe answers the question in
-- five seconds instead.
--
-- It also reports which of a candidate list are readable, so a rig can be written against
-- names that are known to exist rather than names that seem plausible.
--
-- Deliberately NO rig-machine: header -- the question is per-CPU, so name the model you
-- mean. The measurement below is kn5000 (TLCS-900); kn7000 is an MN10300 and answers
-- differently, which is the entire point of running it.
--   ./tools/rig.sh cpu_state_probe kn5000 -s 5
--   CPU_TAG=":subcpu" ...        (default ":maincpu")
--
-- Measured on kn5000 :maincpu (TMP94C241, TLCS-900/H2), 41 keys, including:
--   PC, XWA0..XHL3 (four register banks), XIX, XIY, XIZ, XNSP, XSSP, DMAS0.., DMAD0..
-- ⚠ Note there is no "SP" and no "F"/flags entry under those names.

local mac = manager.machine
local tag = os.getenv("CPU_TAG") or ":maincpu"
local cpu = mac.devices[tag]
local function log(s) emu.print_error(s) end

if not cpu then
    log("STATE FAIL -- no device " .. tag)
    return
end

_G.SP_ = _G.SP_ or {}
_G.SP_.h = emu.add_machine_frame_notifier(function()
    if _G.SP_.done or mac.time.seconds < 3 then return end
    _G.SP_.done = true

    local ok, err = pcall(function()
        local n = 0
        for k, _ in pairs(cpu.state) do
            n = n + 1
            log(string.format("STATE key %2d: %s", n, tostring(k)))
        end
        log("STATE total keys: " .. n)
    end)
    if not ok then log("STATE iteration ERROR: " .. tostring(err)) end

    -- common guesses, so the failure mode is visible rather than silent
    for _, nm in ipairs({ "PC", "SP", "XSP", "XNSP", "XSSP", "A", "F", "XIX" }) do
        local ok2, v = pcall(function() return cpu.state[nm].value end)
        log(string.format("STATE probe %-5s readable=%-5s value=%s",
            nm, tostring(ok2), ok2 and string.format("0x%X", v) or "-"))
    end
    mac:exit()
end)
