-- kn6_fbdump.lua -- dump the KN6000's composited FRAMEBUFFER for offline inspection.
-- rig-machine: kn6000
--
-- Reads 0x9CE00000..0x9CE4AFFF (the 640x240 RGB555 buffer the LCD scans; the KN6000 panel is
-- mounted rotated 180 degrees, so decode it reversed -- see kn7000_state::screen_update) and
-- writes kn6_fb.bin at t=25 s.
--
--   ./tools/rig.sh kn6_fbdump kn6000 -s 28
--
-- ⚠ Writes into the EMULATOR directory, which publish-binary.sh overwrites. Copy anything you
--   want to keep.

local cpu = manager.machine.devices[":maincpu"]
local mem = cpu.spaces["program"]
local done = false
emu.register_frame_done(function()
  if manager.machine.time.seconds >= 25 and not done then
    done = true
    local f = io.open("kn6_fb.bin", "wb")
    for a = 0x9ce00000, 0x9ce4afff, 4 do
      local v = mem:read_u32(a)
      f:write(string.char(v & 0xff, (v>>8)&0xff, (v>>16)&0xff, (v>>24)&0xff))
    end
    f:close()
    print("dumped")
  end
end)
