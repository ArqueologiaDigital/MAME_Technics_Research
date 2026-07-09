-- Turn ON the "Effects DSP host stub" machine-config switch, then framebuffer-hash
-- at t>=16s (emu.add_machine_frame_notifier API).
local mac = manager.machine
for _,f in pairs(mac.ioport.ports[":CONFIG"].fields) do
  if f.mask == 0x01 then f:set_value(1); print("CONFIG bit0 set -> DSP stub ON") end
end
local sp = mac.devices[":maincpu"].spaces["program"]
local fired = false
_onsub = emu.add_machine_frame_notifier(function()
  if fired or mac.time.seconds < 16 then return end
  fired = true
  local h, nz = 0, 0
  for a = 0x9ce00000, 0x9ce00000 + 640*240*2 - 1, 64 do
    local v = sp:read_u32(a); h=(h*131+v)&0xffffffff; if v~=0 then nz=nz+1 end
  end
  print(string.format("ON_FBHASH %08x nonzero=%d t=%d", h, nz, mac.time.seconds))
end)
