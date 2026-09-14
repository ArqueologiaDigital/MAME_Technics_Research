-- Verify PEEK: the monitor is asked to read 8 bytes at 0xFBA236 -- which is its OWN reply table,
-- so the expected answer is known exactly and the test is self-verifying.
local mach = manager.machine
local prog = mach.devices[":cpu1"].spaces["program"]
local done = false
_G._f = emu.register_frame_done(function()
  local t = mach.time.seconds + mach.time.attoseconds/1e18
  if t >= 12.5 and not done then
    done = true
    local function hex(a, n)
      local s = {}
      for i = 0, n-1 do s[#s+1] = string.format("%02X", prog:read_u8(a+i)) end
      return table.concat(s, " ")
    end
    emu.print_error("### MST_POS   = " .. string.format("0x%02X", prog:read_u8(0x67FF00)))
    emu.print_error("### MST_CMD   = " .. string.format("0x%02X", prog:read_u8(0x67FF01)))
    emu.print_error("### MST_ADDR  = " .. hex(0x67FF04, 4) .. "   (LE, expect 36 A2 FB 00)")
    emu.print_error("### MST_BUF   = " .. hex(0x67FF10, 21))
    emu.print_error("###   expect  = F0 7E 7D 7E 0F 00 07 0E 07 0D 07 0F 00 01 00 00 0F 07 00 00 F7")
    emu.print_error("### source    = " .. hex(0xFBA236, 8) .. "   (the table it was asked to read)")
    mach:exit()
  end
end)
