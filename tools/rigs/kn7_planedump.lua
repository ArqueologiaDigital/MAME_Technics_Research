-- kn7_planedump.lua -- dump the KN7000's UI source plane: a WORKING text render.
-- rig-machine: kn7000
--
-- Reads 0x500D4080 for 0x25800 bytes = 153,600 = 640x240 at one byte per pixel -- the plane the
-- compositor consumes, before compositing.
--
-- Its value is comparison. notes/FINDINGS-kn2400-table-rom.md renders the KN2400's equivalent
-- plane and finds solid rectangles where text belongs; this is the same structure on a machine
-- whose text works, so the two can be put side by side.
--
--   ./tools/rig.sh kn7_planedump kn7000 -s 28
--   python3 tools/kn24_plane_to_png.py kn7_plane.bin -W 640 -H 240 -o /tmp/kn7_plane.png
--
-- ⚠ Writes kn7_plane.bin into the EMULATOR directory (overwritten on publish).

local cpu = manager.machine.devices[":maincpu"]
local mem = cpu.spaces["program"]
local done = false
emu.register_frame_done(function()
  if manager.machine.time.seconds >= 25 and not done then
    done = true
    local f = io.open("kn7_plane.bin", "wb")
    for a = 0x500d4080, 0x500d4080 + 0x257ff, 4 do
      local v = mem:read_u32(a)
      f:write(string.char(v & 0xff, (v>>8)&0xff, (v>>16)&0xff, (v>>24)&0xff))
    end
    f:close()
    print("dumped")
  end
end)
