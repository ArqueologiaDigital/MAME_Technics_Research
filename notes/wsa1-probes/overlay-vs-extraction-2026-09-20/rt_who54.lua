-- QUESTION: who calls the DISP-attribute routine (prom_a 0xF8F7B8) with all
-- three layers on (C = 7, parameter 0x54)?  Prints the stack words above SP at
-- the moment the parameter byte goes out, so the call chain can be read off.
local m = manager.machine
local cpu = m.devices[":cpu1"]
local sp = cpu.spaces["program"]
local STOP = tonumber(os.getenv("STOP_AT") or "10")
local pend = false
_G.wt = sp:install_write_tap(0x790000, 0x790001, "who", function (offset, data, mask)
  if (mask & 0xff00) ~= 0 then
    pend = (((data >> 8) & 0xff) == 0x59)
  elseif pend then
    pend = false
    if (data & 0xff) ~= 0x54 then return end
    local s = cpu.state["XSP"].value
    local out = {}
    for i = 0, 11 do
      out[#out+1] = string.format("%06X", sp:read_u32(s + i*4) & 0xffffff)
    end
    emu.print_error(string.format("WHO54 t=%.2f XSP=%08X stack: %s",
      m.time:as_double(), s, table.concat(out, " ")))
  end
end)
_G.wn = emu.add_machine_frame_notifier(function () if m.time:as_double() >= STOP then m:exit() end end)
