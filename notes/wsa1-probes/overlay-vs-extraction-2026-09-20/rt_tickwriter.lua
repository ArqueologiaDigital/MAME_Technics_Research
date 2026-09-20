-- QUESTION: what increments CPU1's 488 Hz tick at RAM 0x000080, and at what
-- rate does it actually run in this build?  Taps writes to 0x80/0x81 and
-- reports the writing PCs plus the measured rate.
local m = manager.machine
local cpu = m.devices[":cpu1"]
local sp = cpu.spaces["program"]
local STOP = tonumber(os.getenv("STOP_AT") or "6")
local pcs, n = {}, 0
_G.wsa1_tw_tap = sp:install_write_tap(0x80, 0x81, "tick", function (offset, data, mask)
  local pc = cpu.state["CURPC"].value
  pcs[pc] = (pcs[pc] or 0) + 1
  n = n + 1
end)
_G.wsa1_tw = emu.add_machine_frame_notifier(function ()
  if m.time:as_double() < STOP then return end
  local a = {}
  for k,v in pairs(pcs) do a[#a+1] = {k,v} end
  table.sort(a, function (x,y) return x[2] > y[2] end)
  local s = ""
  for i=1,math.min(8,#a) do s = s .. string.format(" %06X:%d", a[i][1], a[i][2]) end
  emu.print_error(string.format("TICKWRITERS over %.1fs: total=%d rate=%.1f/s ::%s",
    m.time:as_double(), n, n/m.time:as_double(), s))
  m:exit()
end)
