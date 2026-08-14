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
