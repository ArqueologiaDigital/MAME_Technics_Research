-- kn5000_wheel_two_field.lua -- do BOTH wheel controls reach the firmware, independently?
-- rig-machine: kn5000
--
-- QUESTION ANSWERED: the data wheel is driven by two ioport fields that the panel device sums --
-- :cpanel:ENCODER (IPT_POSITIONAL, the keys and the mouse axis) and :cpanel:ENCODER_DRAG
-- (IPT_ADJUSTER, the layout's circular pointer drag). Does each move the tempo by one step per
-- detent, and does moving one leave the other working?
--
-- WHY TWO FIELDS: an analog field's only Lua write path is set_value(), which sets
-- m_use_adjoverride permanently (ioport.cpp:3822) so the field stops reading its accumulator and
-- the KEYS go dead for the rest of the session. user_value does not latch, but it is ignored on
-- anything that is not an IPT_ADJUSTER (ioport.cpp:1048). So the two routes need two fields.
--
-- SIGNAL: the tempo word in main-CPU DRAM at 0xFC62, low 9 bits (120 at boot).
--
--   ./tools/rig.sh kn5000_wheel_two_field kn5000 -s 60
--
-- PASS: each phase moves the tempo by exactly WHEEL_DETENTS in the right direction, and the run
-- ends where it started.
--
-- ⚠ WHAT THIS CANNOT PROVE. It drives the positional with set_value(), which is NOT how a key
--   press drives it -- a key moves the accumulator, which no Lua binding can touch. So this rig
--   cannot show that the keys still work after a drag, which is the exact bug a user reported.
--   What it CAN show is that the drag control no longer writes the positional field at all, which
--   is the structural reason the bug cannot recur. The keyboard half needs a human.

local mac = manager.machine
local function log(s) emu.print_error(s) end

local DETENTS = tonumber(os.getenv("WHEEL_DETENTS") or "") or 12
local EVERY   = tonumber(os.getenv("WHEEL_EVERY") or "") or 14
local START   = tonumber(os.getenv("WHEEL_START") or "") or 24

local key_port  = mac.ioport.ports[":cpanel:ENCODER"]
local drag_port = mac.ioport.ports[":cpanel:ENCODER_DRAG"]
if key_port == nil or drag_port == nil then
    log(string.format("W2F FATAL -- missing port (ENCODER=%s ENCODER_DRAG=%s)",
        tostring(key_port ~= nil), tostring(drag_port ~= nil)))
    mac:exit()
    return
end
local function first_field(p) local f = nil; for _, v in pairs(p.fields) do f = v end; return f end
local key_field, drag_field = first_field(key_port), first_field(drag_port)

local prog = mac.devices[":maincpu"].spaces["program"]
local function bpm()
    local ok, v = pcall(function() return prog:read_u16(0xFC62) end)
    return ok and (v & 0x1FF) or -1
end

-- Each mover steps its OWN control by one detent in `sign`, from that control's CURRENT position.
-- ⚠ The first version of this rig kept one step counter across all four phases, so the positional
--   phase began by writing an absolute value 13 positions from where the field actually sat -- a
--   jump the device correctly read as -11 detents. The rig failed, the device was fine. A relative
--   stimulus must be generated relatively.
local keyval = 0
local function step_positional(sign)
    keyval = (keyval + sign) % 24
    key_field:set_value(keyval)
end
local function step_drag(sign)
    drag_field.user_value = (drag_field.user_value + sign) % 101
end

-- description, mover, expected sign
local PHASES = {
    { "drag adjuster CW",  step_drag,       1 },
    { "positional CW",     step_positional, 1 },
    { "drag adjuster CCW", step_drag,      -1 },
    { "positional CCW",    step_positional, -1 },
}

_G.W2F = _G.W2F or { frame = 0, phase = 0, step = 0, emitted = 0, fails = 0 }

_G.W2F.h = emu.add_machine_frame_notifier(function()
    local S = _G.W2F
    S.frame = S.frame + 1
    if mac.time.seconds < START then return end

    if S.phase == 0 then
        S.phase, S.base = 1, bpm()
        log(string.format("W2F start: bpm=%d", S.base))
        return
    end
    if S.phase > #PHASES then return end

    local name, mover, sign = table.unpack(PHASES[S.phase])
    if S.settle then
        if S.frame < S.settle then return end
        local now = bpm()
        local got, want = now - S.mark, sign * DETENTS
        local ok = (got == want)
        if not ok then S.fails = S.fails + 1 end
        log(string.format("W2F %-18s -> bpm %3d (delta %+d, expect %+d) %s",
            name, now, got, want, ok and "ok" or "FAIL"))
        S.settle, S.phase, S.emitted = nil, S.phase + 1, 0
        if S.phase > #PHASES then
            log(string.format("W2F net : %d -> %d (started at %d)", S.base, bpm(), S.base))
            if S.fails == 0 and bpm() == S.base then
                log("W2F PASS -- both controls move the wheel, independently and reversibly")
            else
                log(string.format("W2F FAIL -- %d phase(s) wrong%s", S.fails,
                    (bpm() ~= S.base) and ", and it did not return to the start" or ""))
            end
            mac:exit()
        end
        return
    end

    if S.emitted == 0 then S.mark = bpm() end
    if S.emitted >= DETENTS then
        S.settle = S.frame + 90
        return
    end
    if S.frame % EVERY == 0 then
        pcall(function() mover(sign) end)
        S.emitted = S.emitted + 1
    end
end)
