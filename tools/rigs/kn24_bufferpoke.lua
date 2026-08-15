-- kn24_bufferpoke.lua -- do the 0xFF RAM buffers actually feed the KN2400's display?
-- rig-machine: kn2400
--
-- notes/FINDINGS-kn2400-table-rom.md closes the chain from the undumped table ROM to a RAM
-- buffer at 0x502A5024 that is 99.86% 0xFF (40 records x 712 B, copied by the loop at
-- 0x4860C274). What is still INFERENCE is the last link: that this buffer is what the text
-- drawer reads, and therefore why text renders as solid bars.
--
-- This tests it the only honest way available without a dump: overwrite the buffer at runtime
-- with a distinctive pattern, through the real memory, and look for a change on screen.
--
-- ⚠ THE CONTROL IS NOT OPTIONAL. A play screen that simply never redraws would produce "no
--   change" for a reason that has nothing to do with the buffer, and reading that as "the
--   buffer is not the source" would be exactly backwards. So:
--
--     POKE=1 ./tools/rig.sh kn24_bufferpoke kn2400 -s 32     # experiment
--     POKE=0 ./tools/rig.sh kn24_bufferpoke kn2400 -s 32     # control -- identical timing,
--                                                            #   no write
--
--   Compare the two. The test only says something if the CONTROL's before/after hashes are
--   EQUAL (screen is stable on its own) and the EXPERIMENT's differ.
--   If the control's hashes already differ, the screen redraws by itself and this design
--   cannot answer the question -- that is a real outcome and the rig says so.
--
-- ⚠ TIMING IS THE WHOLE EXPERIMENT. kn24_fbwrites.lua measured the KN2400 compositing its
--   screen at t=6 and never repainting after t=11.13. A poke at t=20 -- or even t=7 -- is
--   therefore AFTER the only paint, and cannot change the display no matter what the buffer
--   is for. Both were run before that was known, and both produced worthless nulls.
--   Use a WINDOW that straddles the paint:
--
--     POKE_AT=4 POKE_UNTIL=8 ./tools/rig.sh kn24_bufferpoke kn2400 -s 34
--
--   Compare the resulting snapshot against a POKE=0 control run's snapshot, byte for byte.
--   The within-run t=22 vs t=30 comparison says little on a screen that never redraws; the
--   BETWEEN-RUN comparison is the real signal.
--
-- POSITIVE CONTROL (verified 2026-08-15): poking the framebuffer itself,
--   POKE_LO=0x9C800000 POKE_HI=0x9C801900 POKE_VALUE=0xFF, changes the sampled hash from
--   571e1a45 to e046d445. So the poke mechanism demonstrably reaches the display. Re-run it
--   whenever a null result matters -- a test that cannot succeed is not evidence.
--
-- Env: POKE (1), POKE_VALUE (0x00), POKE_AT (20), POKE_UNTIL (-1 = single poke),
--      POKE_EVERY (0.1 s), POKE_LO/POKE_HI, T1 (22), T2 (30)

local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local POKE     = (tonumber(os.getenv("POKE")) or 1) ~= 0
local POKE_VAL = tonumber(os.getenv("POKE_VALUE")) or 0x00
local POKE_AT  = tonumber(os.getenv("POKE_AT")) or 20
local T1       = tonumber(os.getenv("T1")) or 22
local T2       = tonumber(os.getenv("T2")) or 30
-- REPEATED poking. A single poke is almost always the wrong test on this machine:
-- kn24_fbwrites.lua measured the last full framebuffer paint at t=6 and the last write at
-- t=11.13, so a poke at t=7 or t=20 lands AFTER the screen was composited and can never
-- change it, whatever the buffer feeds. Holding the buffer overwritten ACROSS the paint is
-- what makes the test fair. Default window 4.0-8.0 s straddles the t=6 paint.
local POKE_UNTIL = tonumber(os.getenv("POKE_UNTIL")) or -1
local POKE_EVERY = tonumber(os.getenv("POKE_EVERY")) or 0.1

-- The buffer found by kn24_tabledest.lua. Base is read from RAM rather than hardcoded, so a
-- firmware or timing change moves the poke with it instead of silently writing the wrong place.
local PTR = 0x500D7398
local SPAN = 40 * 712                     -- 40 records, stride 0x2C8

-- An explicit range overrides the pointer-derived one, so the OTHER buffers kn24_tabledest.lua
-- found can be tested the same way:
--   POKE_LO=0x502AC108 POKE_HI=0x502B0808 ./tools/rig.sh kn24_bufferpoke kn2400 -s 34
local LO_ENV = tonumber(os.getenv("POKE_LO") or "") or nil
local HI_ENV = tonumber(os.getenv("POKE_HI") or "") or nil

_G.BP = _G.BP or { phase = 0 }

local function signature()
    local scr
    for _, s in pairs(mac.screens) do scr = s break end
    if not scr then return nil end
    local ok, px = pcall(function() return scr:pixels() end)
    if not ok or type(px) ~= "string" then return nil end
    -- Same sampling as liveness.lua, which is known to work on this build.
    local seen, distinct, hash = {}, 0, 5381
    for i = 1, #px - 3, 64 do
        local v = px:byte(i) * 16777216 + px:byte(i + 1) * 65536
                + px:byte(i + 2) * 256 + px:byte(i + 3)
        if not seen[v] then seen[v] = true distinct = distinct + 1 end
        hash = (hash * 33 + v) % 4294967296
    end
    return distinct, hash
end

_G.BP.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds
    local S = _G.BP

    -- Repeated poking while inside the window, so the buffer is still overwritten at the
    -- instant the firmware composites.
    if S.phase == 1 and POKE and POKE_UNTIL > 0 and t < POKE_UNTIL and S.lo then
        local now = mac.time.seconds + mac.time.attoseconds / 1e18
        if not S.lastpoke or now - S.lastpoke >= POKE_EVERY then
            S.lastpoke = now
            S.repokes = (S.repokes or 0) + 1
            for a = S.lo, S.hi do pcall(function() prog:write_u8(a, POKE_VAL) end) end
        end
    end

    if S.phase == 0 and t >= POKE_AT then
        S.phase = 1
        if LO_ENV and HI_ENV then
            S.lo, S.hi = LO_ENV, HI_ENV
        else
            local ok, base = pcall(function() return prog:read_u32(PTR) end)
            if not ok or base == 0 or base == 0xFFFFFFFF then
                log(string.format("POKE ABORT -- [0x%08X] reads 0x%s; no buffer to poke.",
                    PTR, ok and string.format("%08X", base) or "?"))
                S.phase = 9
                return
            end
            S.lo = base + 0x10
            S.hi = S.lo + SPAN - 1
        end
        local NB = S.hi - S.lo + 1
        -- Count what is there BEFORE, so "we changed it" is measured, not assumed.
        local ff = 0
        for a = S.lo, S.hi, 32 do
            local okb, b = pcall(function() return prog:read_u8(a) end)
            if okb and b == 0xFF then ff = ff + 1 end
        end
        log(string.format("POKE buffer 0x%08X..0x%08X (%d B)  before: %d of %d sampled bytes are 0xFF",
            S.lo, S.hi, NB, ff, math.floor(NB / 32) + 1))
        if POKE then
            for a = S.lo, S.hi do pcall(function() prog:write_u8(a, POKE_VAL) end) end
            -- Verify the write actually took. RAM that is write-protected or shadowed would
            -- otherwise make this look like a clean negative result.
            local back = {}
            for _, a in ipairs({ S.lo, S.lo + math.floor(NB / 3), S.lo + math.floor(2 * NB / 3), S.hi }) do
                local okb, b = pcall(function() return prog:read_u8(a) end)
                back[#back + 1] = okb and string.format("%02X", b) or "??"
            end
            log(string.format("POKE wrote 0x%02X over %d bytes at t=%d; readback = %s",
                POKE_VAL, NB, t, table.concat(back, " ")))
        else
            log(string.format("POKE control run -- NO write performed (t=%d)", t))
        end
    elseif S.phase == 1 and t >= T1 then
        S.phase = 2
        if S.repokes then
            log(string.format("POKE held the buffer overwritten with %d repeats up to t=%.1f",
                S.repokes, POKE_UNTIL))
        end
        S.d1, S.h1 = signature()
        log(string.format("POKE t=%d signature distinct=%s hash=%s", t,
            tostring(S.d1), S.h1 and string.format("%08x", S.h1) or "-"))
    elseif S.phase == 2 and t >= T2 then
        S.phase = 3
        S.d2, S.h2 = signature()
        log(string.format("POKE t=%d signature distinct=%s hash=%s", t,
            tostring(S.d2), S.h2 and string.format("%08x", S.h2) or "-"))
        local changed = (S.h1 ~= S.h2) or (S.d1 ~= S.d2)
        log(string.format("POKE RESULT mode=%s screen_changed=%s",
            POKE and "EXPERIMENT" or "CONTROL", tostring(changed)))
        log("POKE  Interpretation needs BOTH runs:")
        log("POKE    control unchanged + experiment changed -> the buffer feeds the display")
        log("POKE    control unchanged + experiment unchanged -> it does not (for this screen)")
        log("POKE    control CHANGED -> screen redraws on its own; this design cannot answer")
        mac.video:snapshot()
        mac:exit()
    end
end)
