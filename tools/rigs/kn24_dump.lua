-- dump 0x9C800000..0x9C87FFFF (512KB) at t=40 to kn24_lcd.bin; also fine-scan extent.
local cpu = manager.machine.devices[":maincpu"]
local mem = cpu.spaces["program"]
local done = false
emu.register_frame_done(function()
  local t = manager.machine.time
  local ts = t.seconds + t.attoseconds/1e18
  if ts >= 40 and not done then
    done = true
    local f = io.open("kn24_lcd.bin", "wb")
    for a = 0x9c800000, 0x9c87ffff, 4 do
      local v = mem:read_u32(a)
      f:write(string.char(v & 0xff, (v>>8)&0xff, (v>>16)&0xff, (v>>24)&0xff))
    end
    f:close()
    -- also dump 0x9c000000 low block in case regs live there
    local g = io.open("kn24_lcd_low.bin", "wb")
    for a = 0x9c000000, 0x9c00ffff, 4 do
      local v = mem:read_u32(a)
      g:write(string.char(v & 0xff, (v>>8)&0xff, (v>>16)&0xff, (v>>24)&0xff))
    end
    g:close()
    print("dumped")
  end
end)
