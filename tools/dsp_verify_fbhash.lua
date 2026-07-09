local mac = manager.machine
local sp  = mac.devices[":maincpu"].spaces["program"]
local fired = false
mac:add_notifier("frame", function()
  if fired or mac.time.seconds < 16 then return end
  fired = true
  local h, nz = 0, 0
  for a = 0x9ce00000, 0x9ce00000 + 640*240*2 - 1, 64 do
    local v = sp:read_u32(a)
    h = (h * 131 + v) & 0xffffffff
    if v ~= 0 then nz = nz + 1 end
  end
  print(string.format("FBHASH %08x nonzero=%d/%d t=%.1f", h, nz, (640*240*2)//64, mac.time.seconds))
  mac:exit()
end)
