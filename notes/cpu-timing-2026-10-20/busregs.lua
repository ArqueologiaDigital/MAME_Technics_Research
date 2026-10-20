-- busregs.lua -- at 20 s of emulated time, print the bus controller registers and CHCTR as the CPU reads them
-- (BUSREGS line on stderr), then quit: compare with pass 9's register snapshot of the unit.
local M = manager.machine
local sp = M.devices[":maincpu"].spaces["program"]
_G.BR = emu.add_machine_frame_notifier(function()
  if M.time:as_double() > 20 then
    local t = {}
    for _, a in ipairs({0x32000010, 0x32000020, 0x32000022, 0x32000024, 0x32000026, 0x32000028, 0x3200002a, 0x3200002c, 0x3200002e, 0x32000040, 0x32000042}) do
      t[#t + 1] = string.format("%08X=%04X", a, sp:read_u16(a)) end
    t[#t + 1] = string.format("CHCTR=%04X", sp:read_u16(0x20000070))
    emu.print_error("BUSREGS " .. table.concat(t, " "))
    M:exit()
  end
end)
