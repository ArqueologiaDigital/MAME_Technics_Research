-- kn5000_note_capture.lua -- hold one known keybed note, so its pitch can be measured.
--
-- For task-queue item P10, the octave error: the emulator's onset centroid measures ~13
-- semitones above a reference render, and nobody has yet played a KNOWN note and measured
-- what comes out. This plays one and reports enough state to prove the stimulus fired.
--
-- Modelled on liveness.lua, which is known to work on this build. Two things the older
-- note.lua got wrong and this does not:
--   * the notifier handle is held in a GLOBAL, or the Lua GC collects it and nothing fires;
--   * diagnostics go through emu.print_error, which reliably reaches stderr.
--
-- Reports:
--   NOTECAP port=:KEYS0 field="Key C4" found=yes pressed_at=16.00
--   NOTECAP fields available: ...        (only when the named field is NOT found)
--
--   ./run.sh kn5000 -window -nothrottle -seconds_to_run 30 -wavwrite out.wav \
--       -autoboot_script tools/rigs/kn5000_note_capture.lua
--   NOTE_NAME="Key C4" NOTE_AT=16 ...
--
-- Expected pitch for C4 is 261.626 Hz; an octave high reads 523.25, an octave low 130.81.

local mac = manager.machine
local function log(s) emu.print_error(s) end

local AT   = tonumber(os.getenv("NOTE_AT")) or 16.0
local NAME = os.getenv("NOTE_NAME") or "Key C4"
local PORT = os.getenv("NOTE_PORT") or ":KEYS0"

_G.NC = _G.NC or { done = false }

_G.NC.h = emu.add_machine_frame_notifier(function()
    if _G.NC.done then return end
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    if t < AT then return end
    _G.NC.done = true

    local p = mac.ioport.ports[PORT]
    if not p then
        log("NOTECAP FAIL -- no port " .. PORT)
        local n = 0
        for tag, _ in pairs(mac.ioport.ports) do
            n = n + 1
            if n <= 30 then log("  port: " .. tostring(tag)) end
        end
        return
    end

    local hit = nil
    for _, f in pairs(p.fields) do
        if f.name == NAME then hit = f end
    end
    if not hit then
        log(string.format("NOTECAP FAIL -- no field %q on %s; available:", NAME, PORT))
        local n = 0
        for _, f in pairs(p.fields) do
            n = n + 1
            if n <= 40 then log("  field: " .. tostring(f.name)) end
        end
        return
    end

    hit:set_value(1)
    _G.NC.field = hit
    log(string.format("NOTECAP port=%s field=%q found=yes pressed_at=%.2f", PORT, NAME, t))
end)
