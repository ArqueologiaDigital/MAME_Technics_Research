-- QUESTION: which code issues the final `DISP ON, parameter 0x54` -- the command
-- that turns the three layer attributes on and makes the panel show anything?
-- Logs the CPU1 PC for every DISP ON / DISP OFF command and its parameter byte.
local m = manager.machine
local cpu = m.devices[":cpu1"]
local sp = cpu.spaces["program"]
local STOP = tonumber(os.getenv("STOP_AT") or "10")
local pend = nil
_G.dt = sp:install_write_tap(0x790000, 0x790001, "disp", function (offset, data, mask)
  local cmdlane = (mask & 0xff00) ~= 0
  if cmdlane then
    local b = (data >> 8) & 0xff
    pend = (b == 0x58 or b == 0x59) and {b, cpu.state["CURPC"].value} or nil
    if pend then
      emu.print_error(string.format("DISP t=%7.2f cmd %02X (bare so far)  pc=%06X", m.time:as_double(), b, pend[2]))
    end
  elseif pend then
    emu.print_error(string.format("DISP t=%7.2f cmd %02X PARAM %02X        pc=%06X",
      m.time:as_double(), pend[1], data & 0xff, cpu.state["CURPC"].value))
    pend = nil
  end
end)
_G.dn = emu.add_machine_frame_notifier(function () if m.time:as_double() >= STOP then m:exit() end end)
