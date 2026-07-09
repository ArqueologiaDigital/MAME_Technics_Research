-- Confirm the home screen renders: hash the LCD framebuffer (0x9CE00000) once at
-- t>=16s. Uses emu.add_machine_frame_notifier (MAME >=0.254 API).
local mac = manager.machine
local sp  = mac.devices[":maincpu"].spaces["program"]
local fired = false
_fbsub = emu.add_machine_frame_notifier(function()
  if fired or mac.time.seconds < 16 then return end
  fired = true
  local h, nz = 0, 0
  for a = 0x9ce00000, 0x9ce00000 + 640*240*2 - 1, 64 do
    local v = sp:read_u32(a); h = (h*131 + v) & 0xffffffff
    if v ~= 0 then nz = nz + 1 end
  end
  print(string.format("FBHASH %08x nonzero=%d/%d t=%d", h, nz, (640*240*2)//64, mac.time.seconds))
end)
