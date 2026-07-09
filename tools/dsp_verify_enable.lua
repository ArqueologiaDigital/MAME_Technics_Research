-- Enable the "Effects DSP host stub" machine-config switch at startup, then at
-- t>=16s hash the LCD framebuffer to confirm the home screen still renders.
local mac = manager.machine
-- set CONFIG bit0 = 1 before the firmware's DSP boot probe runs
for _,f in pairs(mac.ioport.ports[":CONFIG"].fields) do
  if f.mask == 0x01 then f:set_value(1) end
end
local sp = mac.devices[":maincpu"].spaces["program"]
local fired = false
mac:add_notifier("frame", function()
  if fired or mac.time.seconds < 16 then return end
  fired = true
  local h, nz = 0, 0
  for a = 0x9ce00000, 0x9ce00000 + 640*240*2 - 1, 64 do
    local v = sp:read_u32(a); h = (h*131 + v) & 0xffffffff
    if v ~= 0 then nz = nz + 1 end
  end
  print(string.format("ON_FBHASH %08x nonzero=%d t=%.1f", h, nz, mac.time.seconds))
  mac:exit()
end)
