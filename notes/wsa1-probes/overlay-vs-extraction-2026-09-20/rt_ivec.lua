-- QUESTION: which interrupts does CPU1 actually dispatch, and how often?
-- Every TLCS900 interrupt entry does RDMEML(0xFFFF00 + vector), so a read tap
-- on the vector table is an exact per-vector dispatch census.
local m = manager.machine
local cpu = m.devices[":cpu1"]
local sp = cpu.spaces["program"]
local STOP = tonumber(os.getenv("STOP_AT") or "6")
local names = {[0x00]="INT0",[0x2c]="INT4",[0x30]="INT5",[0x34]="INT6",[0x38]="INT7",
  [0x40]="INTT0",[0x44]="INTT1",[0x48]="INTT2",[0x4c]="INTT3",[0x50]="INTTR4",[0x54]="INTTR5",
  [0x58]="INTTR6",[0x5c]="INTTR7",[0x60]="INTRX0",[0x64]="INTTX0",[0x68]="INTRX1",[0x6c]="INTTX1",
  [0x70]="INTAD",[0x74]="INTTC0",[0x78]="INTTC1",[0x7c]="INTTC2",[0x80]="INTTC3"}
local c = {}
_G.wsa1_iv_tap = sp:install_read_tap(0xffff00, 0xffff83, "ivec", function (offset, data, mask)
  local v = offset - 0xffff00
  v = v - (v % 4)
  c[v] = (c[v] or 0) + 1
end)
_G.wsa1_iv = emu.add_machine_frame_notifier(function ()
  local t = m.time:as_double()
  if t < STOP then return end
  local a = {}
  for k,v in pairs(c) do a[#a+1] = {k,v} end
  table.sort(a, function (x,y) return x[2] > y[2] end)
  for i=1,#a do
    emu.print_error(string.format("IVEC %02X %-8s  %7d dispatches  %8.1f/s",
      a[i][1], names[a[i][1]] or "?", a[i][2]/2, (a[i][2]/2)/t))
  end
  m:exit()
end)
