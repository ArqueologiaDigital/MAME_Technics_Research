local m = manager.machine
local sp = m.devices[":cpu1"].spaces["program"]
local n = 0
_G.pt = sp:install_write_tap(0x790000, 0x790001, "lcd", function (offset, data, mask)
  if n < 12 then
    emu.print_error(string.format("TAP off=%06X data=%04X mask=%04X", offset, data, mask))
    n = n + 1
  end
end)
_G.pn = emu.add_machine_frame_notifier(function () if m.time:as_double() >= 2 then m:exit() end end)
