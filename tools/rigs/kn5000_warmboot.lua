-- kn5000_warmboot.lua -- did this boot take the WARM path restored from the IC21 SRAM?
-- rig-machine: kn5000
--
-- Second half of the splash acceptance test (tools/tests/test_kn5000_splash.sh). After a clean
-- power-off through the modelled POWER switch, the next boot should:
--   1. find no 0x5AA5 magic at DRAM 0xFFCA (work DRAM is volatile, so it is a cold start),
--   2. restore DRAM[0xF980..0xFFEE] from the battery-backed SRAM at 0x1E8000 (code at 0xEF0580),
--   3. therefore find NON-ZERO payload checksums at 0xFFD4/0xFFD2,
--   4. so SubCPU_Payload_Verify (0xEF092B) passes, the sub-CPU transfer is SKIPPED, and the
--      splash animation plays.
--
-- This watches (2) and (3) directly, which are the observable, unambiguous steps. It does NOT
-- claim to see the splash: that is a picture, and the test script keeps a snapshot for a human.
--
--   ./tools/rig.sh kn5000_warmboot kn5000 -s 40
--
-- Prints WB lines and a verdict. A COLD verdict on the first-ever boot is correct, not a
-- failure -- there is nothing in SRAM yet.

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

-- ⚠ SAMPLE EARLY, AND SAMPLE THE TIMELINE. The verify (0xEF092B) runs around t=4; by t=32 the
-- firmware has long since reused these words for other things, and a single late sample says
-- nothing about what the verify saw. The first version of this rig sampled once at t=32 and
-- reported a confident "cold path" from values that were simply stale.
local AT = tonumber(os.getenv("WB_AT") or "") or 12

_G.WB = _G.WB or { restored = 0, first = nil, log = {}, prev4 = nil, prev2 = nil }

-- Watch the restore landing in the payload window. The restore copies SRAM -> DRAM 0xF980..,
-- so writes here early in boot are the signature of the warm path.
-- ⚠ 0xFFEF, not 0xFFEE: this bus is 16-bit and a tap range must END on an odd address, or MAME
-- fatals with "end address has low bits unset". The payload block itself is 0xF980..0xFFEE; the
-- extra byte only widens the watch.
_G.WB.tap = prog:install_write_tap(0xF980, 0xFFEF, "payload", function(offset, data, mask)
    local S = _G.WB
    S.restored = S.restored + 1
    if not S.first then
        S.first = mac.time.seconds + mac.time.attoseconds / 1e18
    end
    return nil
end)

local function rd16(a)
    local ok, v = pcall(function() return prog:read_u16(a) end)
    return ok and v or -1
end

_G.WB.h = emu.add_machine_frame_notifier(function()
    local S = _G.WB
    local t = mac.time.seconds + mac.time.attoseconds / 1e18

    -- Record every CHANGE of the two checksum words, so restore-then-clear is distinguishable
    -- from clear-then-restore. That ordering is the whole question.
    if not S.done then
        local c4, c2 = rd16(0xFFD4), rd16(0xFFD2)
        if c4 ~= S.prev4 or c2 ~= S.prev2 then
            S.prev4, S.prev2 = c4, c2
            if #S.log < 24 then
                S.log[#S.log + 1] = string.format("t=%6.2f  0xFFD4=0x%04X  0xFFD2=0x%04X", t, c4, c2)
            end
        end
    end

    if S.done or t < AT then return end
    S.done = true

    log(string.format("WB payload-window writes: %d (first at t=%s)",
        S.restored, S.first and string.format("%.2f", S.first) or "-"))
    log("WB checksum timeline (every change, earliest first):")
    for _, line in ipairs(S.log) do log("WB   " .. line) end
    log(string.format("WB magic 0xFFCA = 0x%04X at t=%.2f", rd16(0xFFCA), t))

    -- Load-bearing signal: were BOTH checksums ever non-zero at the same time before the verify?
    local warm = false
    for _, line in ipairs(S.log) do
        local a, b = line:match("0xFFD4=0x(%x+)%s+0xFFD2=0x(%x+)")
        if a and b and tonumber(a, 16) ~= 0 and tonumber(b, 16) ~= 0 then warm = true end
    end
    if warm then
        log("WB VERDICT: warm path -- both checksums were populated during boot.")
    else
        log("WB VERDICT: cold path -- the two checksums were never both non-zero.")
        log("WB   (correct on a first-ever boot; after a clean power-off it means the restore")
        log("WB    did not survive to the verify -- compare the timeline against the clear.)")
    end
    mac.video:snapshot()
    mac:exit()
end)
