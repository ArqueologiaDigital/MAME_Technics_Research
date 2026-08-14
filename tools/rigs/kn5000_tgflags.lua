-- kn5000_tgflags.lua -- is ToneGen_GlobalFlags bit 2 EVER set on the shipped configuration?
--
-- WHY THIS ONE BIT MATTERS. The 2026-08-14 page-2 adjudication concluded that IC307 page 2's
-- 48% period-detection "failure" is not an audible defect, because the ~1020 wavetable entries
-- above 0x096 are unreachable: the only writer of the wave-select word (+0x040) is the sub-CPU
-- zone-record emitter, and no zone record names an entry >= 0x097.
--
-- That rests on one assumption. WaveSel_StageB_Store_Reg040 DOUBLES the class nibble when
-- ToneGen_GlobalFlags (sub-CPU 0x041343) bit 2 is set, which remaps class 3 -- 415 entries --
-- onto class 6. If that bit is ever set in practice, the unaddressed tail becomes reachable
-- and "not a defect" collapses into "a defect on ~1000 chunks".
--
-- The adjudicator flagged the existing evidence as weak because it quoted a note's recorded
-- value (0x0208) rather than re-running it. This re-runs it.
--
-- Samples the byte every frame from t=0 to t=UNTIL (default 40 s) and reports every distinct
-- value seen, with the time it first appeared, plus an explicit verdict on bit 2.
--
--   ./run.sh kn5000 -window -nothrottle -seconds_to_run 42 \
--       -autoboot_script tools/rigs/kn5000_tgflags.lua
--
-- PRE-DECLARED: bit 2 never set  -> the page-2 "not a defect" verdict stands.
--               bit 2 ever set   -> it collapses; ~1000 chunks become reachable.

local mac  = manager.machine
local sub  = mac.devices[":subcpu"]
local function log(s) emu.print_error(s) end

local UNTIL = tonumber(os.getenv("TGF_UNTIL")) or 40
local ADDR  = 0x041343

if not sub then
    log("TGFLAGS FAIL -- no :subcpu device")
    return
end
local sp = sub.spaces["program"]

-- Held in a global or the Lua GC collects the handle and the notifier stops firing.
_G.TGF = _G.TGF or { seen = {}, order = {}, n = 0 }

_G.TGF.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    if _G.TGF.done then return end

    local ok, v = pcall(function() return sp:read_u8(ADDR) end)
    if ok and v then
        _G.TGF.n = _G.TGF.n + 1
        if not _G.TGF.seen[v] then
            _G.TGF.seen[v] = t
            _G.TGF.order[#_G.TGF.order + 1] = v
        end
    end

    if t >= UNTIL then
        _G.TGF.done = true
        local anybit2 = false
        log(string.format("TGFLAGS samples=%d distinct=%d", _G.TGF.n, #_G.TGF.order))
        for _, v in ipairs(_G.TGF.order) do
            local b2 = (v & 0x04) ~= 0
            if b2 then anybit2 = true end
            log(string.format("  value 0x%02X  first seen t=%.2fs  bit2=%s",
                v, _G.TGF.seen[v], b2 and "SET" or "clear"))
        end
        if anybit2 then
            log("TGFLAGS VERDICT: bit 2 IS set -- class 3 can remap onto class 6, so the "
                .. "~1020 unaddressed page-2 wavetable entries ARE reachable. The 'page 2 "
                .. "errors are inaudible' conclusion FAILS.")
        else
            log("TGFLAGS VERDICT: bit 2 never set in this window -- the page-2 verdict stands "
                .. "on this run. (Absence over one boot is weaker than a proof; widen the "
                .. "window or exercise organ/drawbar patches to strengthen it.)")
        end
        mac:exit()
    end
end)
