-- kn7_fontdump.lua -- dump the KN7000's font descriptor area (the WORKING reference).
-- rig-machine: kn7000
--
-- Reads 0x50122D00..0x501233FF at t=25 s. The KN7000 renders text correctly, so this is the
-- reference for what a resolved font looks like on this family -- useful precisely because the
-- KN6000 and KN2400 do not render text and their equivalents can be compared against it.
--
--   ./tools/rig.sh kn7_fontdump kn7000 -s 28
--
-- ⚠ Writes kn7_font.bin into the EMULATOR directory (overwritten on publish).

local cpu = manager.machine.devices[":maincpu"]
local mem = cpu.spaces["program"]
local done = false
emu.register_frame_done(function()
  if manager.machine.time.seconds >= 25 and not done then
    done = true
    local f = io.open("kn7_font.bin", "wb")
    for a = 0x50122d00, 0x501233ff, 4 do
      local v = mem:read_u32(a)
      f:write(string.char(v & 0xff, (v>>8)&0xff, (v>>16)&0xff, (v>>24)&0xff))
    end
    f:close()
    print("dumped")
  end
end)
