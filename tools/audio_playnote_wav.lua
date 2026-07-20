-- audio_playnote_wav.lua -- hold one key-bed note so -wavwrite captures a steady tone.
--
-- Usage (env vars, all optional):
--   KN_NOTE   MIDI note number to press   (default 60 = C4)
--   KN_AT     machine time to press at    (default 16 s -- KN7000 home screen)
--   KN_OFF    machine time to release at  (default: never)
--
-- ============================ WHY BY MASK, NOT BY NAME ============================
-- The previous version searched :KEYS0 for a field literally named "Key C4" and set
-- it.  That silently stopped working when the key bed was widened to the full 61 keys
-- (C2..C7): C2 became :KEYS0 bit 0, so C4 (MIDI 60) moved to :KEYS1 bit 8 and the name
-- "Key C4" no longer exists in :KEYS0 at all.  The loop then matched nothing, `hit`
-- was false, no key was pressed, and every capture made with this script recorded
-- SILENCE -- while still printing a cheerful-looking status line.
--
-- Field NAMES are cosmetic and get rewritten; the port+mask geometry is what the
-- driver actually commits to.  So resolve the key arithmetically from its MIDI note --
-- key index = note - 36, port = KEYS<index/16>, mask = 1 << (index%16) -- which is
-- exactly the KN_KEYM() layout in kn7000.cpp, and fail LOUDLY if that port or mask is
-- absent instead of quietly capturing nothing.
-- =================================================================================

local mac  = manager.machine
local sp   = mac.devices[":maincpu"].spaces["program"]

local note  = tonumber(os.getenv("KN_NOTE") or "60")
local at    = tonumber(os.getenv("KN_AT")   or "16")
local offat = tonumber(os.getenv("KN_OFF")  or "")

-- Key bed geometry (kn7000.cpp PORT_START("KEYS0"/"KEYS1"/...)): the FIFO value is the
-- KEY INDEX, 0 = bottom C2 = MIDI 36, 16 keys per port.
local idx = note - 36
if idx < 0 or idx > 60 then
    error(string.format("note %d outside the 61-key bed (MIDI 36..96)", note))
end
local pname = string.format(":KEYS%d", idx // 16)
local mask  = 1 << (idx % 16)

local port = mac.ioport.ports[pname]
if not port then error("no such port: " .. pname) end

-- Find the field by MASK (masks survive renames; names do not).
local field = nil
for _, f in pairs(port.fields) do
    if f.mask == mask then field = f end
end
if not field then
    error(string.format("%s has no field with mask 0x%04X (note %d)", pname, mask, note))
end

-- machine.time.seconds is an INTEGER in MAME's Lua binding -- use the attoseconds
-- fraction too or every comparison snaps to whole seconds.
local function now() return mac.time.seconds + mac.time.attoseconds / 1e18 end

-- Retain the notifier handle in _G: a frame notifier whose handle is dropped gets
-- garbage-collected and silently unsubscribed, which looks exactly like "the key press
-- did nothing" -- the same failure mode, and the same silent capture, as the by-name
-- lookup this script used to do.
_G._keep = {}
local pressed, released = false, false
_G._keep[#_G._keep + 1] = emu.add_machine_frame_notifier(function()
    local t = now()
    if not pressed and t >= at then
        pressed = true
        field:set_value(1)
        -- home-screen sanity: framebuffer nonzero count
        local nz = 0
        for a = 0x9ce00000, 0x9ce00000 + 640 * 240 * 2 - 1, 256 do
            if sp:read_u32(a) ~= 0 then nz = nz + 1 end
        end
        print(string.format("KEY DOWN note=%d (%s mask 0x%04X, field %q)  fb_nonzero=%d  t=%.3f",
                            note, pname, mask, field.name, nz, t))
    end
    if pressed and not released and offat and t >= offat then
        released = true
        field:set_value(0)
        print(string.format("KEY UP   note=%d  t=%.3f", note, t))
    end
end)
