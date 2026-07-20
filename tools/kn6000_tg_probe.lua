-- kn6000_tg_probe.lua -- LIVE cross-check of the KN6000 tone-generator map.
--
-- The KN6000 plane map and voice-record layout were recovered STATICALLY from the
-- firmware's own note-on register blit (0x484948CB) and its voice-record initialiser
-- (0x48493D80).  This script is the independent LIVE confirmation, run on the real
-- firmware in MAME while a key-bed note is held:
--
--   1. taps the single TG window (0x98050000 addr / 0x98050002 data) and records the
--      ORDERED write burst for the first voice slot the note allocates;
--   2. at the moment of the burst, reads back the two RAM structures the static RE
--      says drive it -- the library voice record (0x502858F8 + slot*0xB4) and the
--      shadow register image (0x50043100 + slot*0xA0);
--   3. repeats an octave up, so a field that carries ABSOLUTE musical pitch must move
--      by exactly 0x0C00 in 1/256-semitone units (12 semitones * 0x100).
--
-- Usage: mame kn6000 -window -skip_gameinfo -autoboot_delay 0 \
--                    -autoboot_script tools/kn6000_tg_probe.lua
-- (NEVER -video none.)  Handles are retained in _G so GC does not unsubscribe them.

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
_G._keep = {}

local LIB_BASE,   LIB_STRIDE   = 0x5027AF28, 0xB4   -- PER-TG-SLOT voice record (copy of the library record)
local SHAD_BASE,  SHAD_STRIDE  = 0x50043100, 0xA0   -- shadow register image

local tg_addr = 0
local watching, burst, lockslot, atnoteon = false, {}, nil, nil

_G._keep[#_G._keep + 1] = prog:install_write_tap(0x98050000, 0x98050003, "kn6tg",
    function(off, data, mask)
        if (mask & 0x0000ffff) ~= 0 then tg_addr = data & 0xffff end
        if (mask & 0xffff0000) ~= 0 and watching then
            local a    = tg_addr
            local d    = (data >> 16) & 0xffff
            if (a & 0xff00) == 0xfc00 then return nil end   -- idle/status refresh
            local slot = (a >> 4) & 0x3F
            local cls  = a & 0xFC0F
            -- Lock onto the FIRST slot of the burst and follow only that voice.
            if lockslot == nil then lockslot = slot end
            if slot == lockslot and #burst < 80 then
                burst[#burst + 1] = { cls = cls, data = d }
            end
            -- Snapshot the library voice record AT THE PITCH WRITE (cls 0x50xx), which
            -- is the note-on trigger the tone generator uses. Reading it seconds later
            -- is wrong: the record is recycled as soon as the voice is freed.
            if slot == lockslot and (cls & 0xFC00) == 0x5000 and atnoteon == nil then
                local lib = LIB_BASE + slot * LIB_STRIDE
                atnoteon = {
                    a08 = prog:read_u8(lib + 0x08), a0a = prog:read_u16(lib + 0x0A),
                    a0c = prog:read_u16(lib + 0x0C), a07 = prog:read_u8(lib + 0x07),
                    a10 = prog:read_u8(lib + 0x10), p18 = ((cls & 0x0F) << 16) | d,
                }
                -- ...and find EVERY active record, so the slot<->record mapping is
                -- measured rather than assumed.
                -- Full shadow record: is the musical note reachable per-SLOT?
                atnoteon.shadow = {}
                for o = 0, 0x9E, 2 do
                    atnoteon.shadow[#atnoteon.shadow + 1] = prog:read_u16(SHAD_BASE + slot * SHAD_STRIDE + o)
                end
                atnoteon.active = {}
                for i = 0, 63 do
                    local r = LIB_BASE + i * LIB_STRIDE
                    local b = prog:read_u8(r + 0x08)
                    if (b & 0x80) ~= 0 then
                        local hx = ""
                        for o = 0, 0xB2, 2 do hx = hx .. string.format(" %02X:%04X", o, prog:read_u16(r + o)) end
                        atnoteon.active[#atnoteon.active + 1] =
                            string.format("rec%02d note=%d pitch16=%04X part=%02X\n           %s",
                                          i, b & 0x7F, prog:read_u16(r + 0x0C), prog:read_u8(r + 0x07), hx)
                    end
                end
            end
        end
        return nil
    end)

local function keyfield(note)
    local idx  = note - 36
    local port = mac.ioport.ports[string.format(":KEYS%d", idx // 16)]
    local mask = 1 << (idx % 16)
    for _, f in pairs(port.fields) do if f.mask == mask then return f end end
    error(string.format("no key-bed field for note %d", note))
end

local function dump(note)
    print(string.format("\n================ NOTE %d  (slot %s) ================",
                        note, lockslot and tostring(lockslot) or "NONE"))
    if not lockslot then print("  NO TG WRITES SEEN"); return end

    print("  -- ordered write burst (cls : data) --")
    local line = "   "
    for i, w in ipairs(burst) do
        line = line .. string.format(" %04X=%04X", w.cls, w.data)
        if i % 8 == 0 then print(line); line = "   " end
    end
    if line ~= "   " then print(line) end

    local lib  = LIB_BASE  + lockslot * LIB_STRIDE
    local shad = SHAD_BASE + lockslot * SHAD_STRIDE
    if atnoteon then
        local s = atnoteon
        print(string.format("  -- library voice record @%08X, SAMPLED AT THE NOTE-ON PITCH WRITE --", lib))
        print(string.format("     chip pitch18    = %05X", s.p18))
        print(string.format("     +0x07 part      = %02X", s.a07))
        print(string.format("     +0x08 act|note  = %02X   (active=%s note=%d)",
                            s.a08, tostring((s.a08 & 0x80) ~= 0), s.a08 & 0x7F))
        print(string.format("     +0x0A basePitch = %04X", s.a0a))
        print(string.format("     +0x0C notePitch = %04X   => MIDI %.3f  [(v-0x80)/256]",
                            s.a0c, (s.a0c - 0x80) / 256.0))
        print(string.format("     +0x10 velocity  = %02X", s.a10))
        print("     -- FULL shadow record at that instant (0x00..0x9E, halfwords) --")
        local ln = "       "
        for i, w in ipairs(s.shadow) do
            ln = ln .. string.format(" %02X:%04X", (i - 1) * 2, w)
            if i % 8 == 0 then print(ln); ln = "       " end
        end
        if ln ~= "       " then print(ln) end
        print("     -- ALL active records at that instant (slot<->record mapping) --")
        for _, l in ipairs(s.active) do print("        " .. l) end
    else
        print("  -- NO PITCH (cls 0x50xx) WRITE SEEN FOR THIS SLOT --")
    end
    print(string.format("  -- shadow register image @%08X --", shad))
    print(string.format("     +0x74 (plane 0x14 / cls 0x5000) = %08X", prog:read_u32(shad + 0x74)))
    print(string.format("     +0x78 (plane 0x15 / cls 0x5400) = %08X", prog:read_u32(shad + 0x78)))
    print(string.format("     +0x7C (plane 0x16 / cls 0x5800) = %08X", prog:read_u32(shad + 0x7C)))
    print(string.format("     +0x08/0C/10 (amp EG r4/r5/r6)   = %04X %04X %04X",
                        prog:read_u16(shad + 0x08), prog:read_u16(shad + 0x0C),
                        prog:read_u16(shad + 0x10)))
end

local NOTES = { 60, 72 }          -- C4 then C5: absolute pitch must move by 0x0C00
local step, held = 0, nil
local function now() return mac.time.seconds + mac.time.attoseconds / 1e18 end

_G._keep[#_G._keep + 1] = emu.add_machine_frame_notifier(function()
    local t = now()
    local T0 = 14                                  -- KN6000 reaches its play screen well before this
    local i  = (step // 2) + 1
    if step % 2 == 0 and i <= #NOTES and t >= T0 + step * 2 then
        burst, lockslot, atnoteon, watching = {}, nil, nil, true
        held = keyfield(NOTES[i]); held:set_value(1)
        step = step + 1
    elseif step % 2 == 1 and t >= T0 + step * 2 then
        watching = false
        dump(NOTES[i])
        held:set_value(0)
        step = step + 1
        if step // 2 > #NOTES then
            print("\nPROBE COMPLETE")
        end
    end
end)
