-- kn24_barcaller.lua -- WHICH caller draws the KN2400's black text bars?
-- rig-machine: kn2400
--
-- notes/FINDINGS-kn2400-table-rom.md: the bars are painted by the solid-fill store at
-- 0x485FA546, inside the routine entered at 0x485FA44C. That routine is a general-purpose rect
-- primitive with **54 direct callers** (tools/mn10300_callers.py --range), so naming the writer
-- did not name the drawer. This narrows the 54 to the one that paints the bars.
--
-- Method: tap the UI plane, and on a write of the BAR COLOUR (0xFF, established by dumping the
-- plane) dump the stack and report every word that looks like a code address. MN10300 `call`
-- pushes the return address, so the caller shows up there -- the same technique that identified
-- the KN5000 stop routine when static search could not.
--
--   ./tools/rig.sh kn24_barcaller kn2400 -s 16
--   BAR_VALUE=0xFF PLANE_LO=0x500ADE34 ...
--
-- Reports the first few distinct stack pictures, then a tally of candidate return addresses by
-- frequency. The bar-drawing caller should dominate: the bars are ~3,900 bytes of the plane and
-- nothing else writes 0xFF into it.
--
-- ⚠ A stack dump is a NEIGHBOURHOOD, not a call graph. Values in the code range may be stale
--   frames from earlier calls. Cross-check any candidate against the 54 known call sites with
--   `python3 tools/mn10300_callers.py 0x485FA44C` before believing it.

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local UNTIL   = tonumber(os.getenv("TAP_UNTIL") or "") or 12
local BARVAL  = tonumber(os.getenv("BAR_VALUE") or "") or 0xFF
local LO      = tonumber(os.getenv("PLANE_LO") or "") or 0x500ADE34
local HI      = tonumber(os.getenv("PLANE_HI") or "") or 0x500C0A33
local DEPTH   = tonumber(os.getenv("STACK_DEPTH") or "") or 16

-- Find the stack pointer's name once, and say so if it is not there. Guessing a register name
-- cost a whole 10-minute run on the KN5000 (it exposes XNSP/XSSP and no "SP").
local SPNAME = nil
for _, cand in ipairs({ "SP", "A3", "USP", "SSP" }) do
    local ok = pcall(function() return cpu.state[cand].value end)
    if ok then SPNAME = cand break end
end
if not SPNAME then
    log("BC FATAL -- no stack-pointer register found. Run cpu_state_probe.lua on kn2400 first.")
end

_G.BC = _G.BC or { n = 0, shown = 0, tally = {} }

local function is_code(v)
    return v >= 0x48400000 and v <= 0x487FFFFF
end

_G.BC.tap = prog:install_write_tap(LO, HI, "bars", function(offset, data, mask)
    local S = _G.BC
    if S.done or not SPNAME then return nil end
    -- Only the byte lanes actually written, and only the bar colour.
    local hit = false
    for lane = 0, 3 do
        if (mask & (0xFF << (lane * 8))) ~= 0 and ((data >> (lane * 8)) & 0xFF) == BARVAL then
            hit = true
        end
    end
    if not hit then return nil end

    S.n = S.n + 1
    local oksp, spv = pcall(function() return cpu.state[SPNAME].value end)
    if not oksp then return nil end

    local pic = {}
    for i = 0, DEPTH - 1 do
        local okw, w = pcall(function() return prog:read_u32(spv + i * 4) end)
        if okw and is_code(w) then
            S.tally[w] = (S.tally[w] or 0) + 1
            pic[#pic + 1] = string.format("+%02d:0x%08X", i * 4, w)
        end
    end
    if S.shown < 3 and #pic > 0 then
        S.shown = S.shown + 1
        log(string.format("BC bar write #%d at 0x%08X  %s=0x%08X", S.n, offset, SPNAME, spv))
        log("   code-looking stack words: " .. table.concat(pic, " "))
    end
    return nil
end)

_G.BC.h = emu.add_machine_frame_notifier(function()
    if _G.BC.done or mac.time.seconds < UNTIL then return end
    _G.BC.done = true
    local S = _G.BC
    log(string.format("BC total bar-colour (0x%02X) writes into the plane: %d", BARVAL, S.n))
    if S.n == 0 then
        log("BC none -- wrong colour or wrong plane range; re-check against kn24_planedump.")
        mac:exit()
        return
    end
    local l = {}
    for a, c in pairs(S.tally) do l[#l + 1] = { a, c } end
    table.sort(l, function(x, y) return x[2] > y[2] end)
    log("BC candidate return addresses by frequency:")
    for i = 1, math.min(12, #l) do
        log(string.format("   0x%08X  %d", l[i][1], l[i][2]))
    end
    log("BC ---- cross-check the top entries against the 54 known call sites:")
    log("BC      python3 tools/mn10300_callers.py 0x485FA44C")
    mac:exit()
end)
