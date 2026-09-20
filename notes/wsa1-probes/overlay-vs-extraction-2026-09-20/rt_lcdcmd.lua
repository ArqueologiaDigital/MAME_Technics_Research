-- QUESTION: what display-control commands does the firmware send the SED1330,
-- and do the two builds send the same ones?  Logs every command byte written to
-- 0x790001 with the parameter bytes that follow it on 0x790000.  MWRITE (0x42)
-- is collapsed to a count so the bulk pixel traffic does not drown the trace.
local m = manager.machine
local sp = m.devices[":cpu1"].spaces["program"]
local STOP = tonumber(os.getenv("STOP_AT") or "8")
local cur, params, nmw = nil, {}, 0
local function flush()
  if cur == nil then return end
  if cur == 0x42 then
    emu.print_error(string.format("LCD t=%7.2f MWRITE  %d bytes", manager.machine.time:as_double(), nmw))
  else
    emu.print_error(string.format("LCD t=%7.2f cmd %02X  params %s", manager.machine.time:as_double(), cur, table.concat(params, " ")))
  end
  cur, params, nmw = nil, {}, 0
end
_G.ct = sp:install_write_tap(0x790000, 0x790001, "lcd", function (offset, data, mask)
  -- the tap reports the WORD base for both ports; the byte lane tells them
  -- apart: mask 0xFF00 = 0x790001 (command), mask 0x00FF = 0x790000 (data).
  local cmdlane = (mask & 0xff00) ~= 0
  local b = cmdlane and ((data >> 8) & 0xff) or (data & 0xff)
  if cmdlane then                       -- command port
    flush(); cur = b; params = {}; nmw = 0
  else                                  -- data port
    if cur == 0x42 then nmw = nmw + 1
    elseif #params < 10 then params[#params+1] = string.format("%02X", b) end
  end
end)
_G.cn = emu.add_machine_frame_notifier(function ()
  if m.time:as_double() >= STOP then flush(); m.video:snapshot(); m:exit() end
end)
