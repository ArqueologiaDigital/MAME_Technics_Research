-- input_seq_probe.lua -- what is a control ACTUALLY bound to?
--
-- QUESTION ANSWERED: given a port tag, print the real input sequences MAME has assigned to each
-- of its fields -- standard, increment and decrement.
--
-- ⚠ WHY THIS EXISTS RATHER THAN `-listxml`: listxml does NOT report default sequences for ANALOG
--   ports. An IPT_POSITIONAL / IPT_DIAL / IPT_ADJUSTER port prints as a bare
--   `<analog mask="31"/>` whether it has PORT_CODE_DEC/PORT_CODE_INC or nothing at all. That is
--   how the KN5000 tempo wheel reached a supposedly-finished PR with NO key binding: the port
--   existed, listxml looked identical either way, and the control simply could not be turned
--   without opening the input menu.
--
--   ./tools/rig.sh input_seq_probe kn5000 -s 8
--   SEQ_PORT=":ENCODER" ...            (default ":ENCODER"; try ":cpanel:ENCODER" too)
--
-- Prints one line per field per sequence kind:
--   SEQ standard   = MOUSECODE_1_XAXIS
--   SEQ increment  = KEYCODE_CLOSEBRACE
--   SEQ decrement  = KEYCODE_OPENBRACE
-- "(none)" means nothing is bound and the control is unreachable out of the box.

local mac = manager.machine
local function log(s) emu.print_error(s) end
local TAG = os.getenv("SEQ_PORT") or ":ENCODER"

_G.SEQP = _G.SEQP or {}

_G.SEQP.h = emu.add_machine_frame_notifier(function()
    if _G.SEQP.done then return end
    _G.SEQP.done = true

    local p = mac.ioport.ports[TAG]
    if not p then
        log("SEQ no port " .. TAG .. " -- available ports:")
        local n = 0
        for tag in pairs(mac.ioport.ports) do
            n = n + 1
            if n <= 24 then log("   " .. tostring(tag)) end
        end
        mac:exit()
        return
    end

    for _, f in pairs(p.fields) do
        log(string.format("SEQ field %q (type %s)", f.name or "?", tostring(f.type)))
        for _, kind in ipairs({ "standard", "increment", "decrement" }) do
            local ok, s = pcall(function()
                return mac.input:seq_to_tokens(f:input_seq(kind))
            end)
            log(string.format("SEQ   %-10s = %s", kind,
                (ok and s and s ~= "") and s or "(none)"))
        end
    end
    mac:exit()
end)
