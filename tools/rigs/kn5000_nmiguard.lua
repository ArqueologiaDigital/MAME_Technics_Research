-- kn5000_nmiguard.lua -- does the firmware ever ARM the power-off NMI guard by itself?
-- rig-machine: kn5000
--
-- The power-off handler NMI_StorePayloadChecksums (0xEF08D4) begins:
--     ef08d4: cp  (0x0400),0x80
--     ef08d9: ret NZ
-- so it does nothing unless that byte holds 0x80. Restoring the boot splash means letting this
-- handler run for real (side-quests/pending/kn5000_splash_animation.txt), and the honest way is
-- for the FIRMWARE to have armed the guard, not for the driver to poke it -- forcing it would be
-- exactly the kind of substitution Felipe asked to avoid.
--
-- So: watch the byte. If the firmware sets it to 0x80 during normal running, the driver only has
-- to assert NMI and give the CPU time. If nothing ever sets it, the arming has its own trigger
-- (a panel POWER button? a supply signal?) that has to be found first.
--
-- A static search cannot answer this: a byte-pattern scan for the 0x0400 operand finds six other
-- hits and the disassembler decodes every one as `db`, i.e. they are data or mid-instruction.
-- Only the read at 0xEF08D4 is real, so the writer uses some other addressing mode.
--
--   ./tools/rig.sh kn5000_nmiguard kn5000 -s 40
--   GUARD_ADDR=0x0400 TAP_UNTIL=38 ...
--
-- Reports every write with its value and PC, plus the value sampled once a second.

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local ADDR  = tonumber(os.getenv("GUARD_ADDR") or "") or 0x0400
local UNTIL = tonumber(os.getenv("TAP_UNTIL") or "") or 38

local function pc()
    local ok, v = pcall(function() return cpu.state["PC"].value end)
    return ok and v or -1
end

_G.NG = _G.NG or { n = 0, last = -1, seen = {} }

-- The TLCS-900 bus is 16-bit: tap the containing word and pick the byte lane from the mask.
-- (A non-word-aligned range is a fatal error in MAME -- learned on the KN5000 before.)
local lo, hi = ADDR & ~1, (ADDR & ~1) + 1
local odd = (ADDR & 1) == 1

_G.NG.tap = prog:install_write_tap(lo, hi, "guard", function(offset, data, mask)
    local S = _G.NG
    local lane = odd and 0xFF00 or 0x00FF
    if (mask & lane) == 0 then return nil end
    local v = odd and ((data >> 8) & 0xFF) or (data & 0xFF)
    local p = pc()
    S.n = S.n + 1
    local key = string.format("%02X/%08X", v, p)
    if not S.seen[key] then
        S.seen[key] = true
        local t = mac.time.seconds + mac.time.attoseconds / 1e18
        log(string.format("NG t=%7.2f  0x%04X <- 0x%02X  from PC=0x%08X%s",
            t, ADDR, v, p, v == 0x80 and "   <<< ARMED" or ""))
    end
    return nil
end)

_G.NG.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds
    local S = _G.NG
    if not S.done and t ~= S.last then
        S.last = t
        local ok, v = pcall(function() return prog:read_u8(ADDR) end)
        if ok and t % 5 == 0 then
            log(string.format("NG t=%3d  0x%04X = 0x%02X", t, ADDR, v))
        end
    end
    if not S.done and t >= UNTIL then
        S.done = true
        local ok, v = pcall(function() return prog:read_u8(ADDR) end)
        log(string.format("NG ---- %d write(s) seen; final 0x%04X = 0x%02X",
            S.n, ADDR, ok and v or -1))
        if ok and v == 0x80 then
            log("NG VERDICT: the guard IS armed by the firmware. The driver only needs to assert")
            log("NG          NMI and let the CPU run -- no poking of this byte.")
        else
            log("NG VERDICT: the guard is NOT armed during normal running. Find what arms it")
            log("NG          before building the power switch; do NOT force it.")
        end
        mac:exit()
    end
end)
