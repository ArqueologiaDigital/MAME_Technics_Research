-- Link handshake trace: every link byte, every P7/PA write, and P7/PA reads
-- only when the value CHANGES.  Taps in globals so the GC cannot drop them.
local mac = manager.machine
local c1 = mac.devices[":cpu1"]
local c2 = mac.devices[":cpu2"]
local s1 = c1.spaces["program"]
local s2 = c2.spaces["program"]
n = 0
lastp7 = -1
lastpa = -1
local function t() return mac.time.seconds + mac.time.attoseconds/1e18 end
local function emit(s) n = n + 1 if n < 900 then print("HS "..s) end end
lw = s1:install_write_tap(0x7c0000, 0x7c0001, "lw", function(off, data, mask)
  emit(string.format("%9.6f LINKW %02X pc=%06X", t(), data & 0xff, c1.state["PC"].value)) end)
lr = s2:install_read_tap(0x100000, 0x100001, "lr", function(off, data, mask)
  emit(string.format("%9.6f LINKR %02X pc=%06X", t(), data & 0xff, c2.state["PC"].value)) end)
p7r = s1:install_read_tap(0x12, 0x13, "p7r", function(off, data, mask)
  if (mask & 0xff00) ~= 0 then local v = (data >> 8) & 0xff
    if v ~= lastp7 then lastp7 = v
      emit(string.format("%9.6f C1 P7 rd=%02X pc=%06X", t(), v, c1.state["PC"].value)) end end end)
p7w = s1:install_write_tap(0x12, 0x13, "p7w", function(off, data, mask)
  if (mask & 0xff00) ~= 0 then
    emit(string.format("%9.6f C1 P7 WR=%02X pc=%06X", t(), (data >> 8) & 0xff, c1.state["PC"].value)) end end)
par = s2:install_read_tap(0x1e, 0x1f, "par", function(off, data, mask)
  if (mask & 0x00ff) ~= 0 then local v = data & 0xff
    if v ~= lastpa then lastpa = v
      emit(string.format("%9.6f C2 PA rd=%02X pc=%06X", t(), v, c2.state["PC"].value)) end end end)
paw = s2:install_write_tap(0x1e, 0x1f, "paw", function(off, data, mask)
  if (mask & 0x00ff) ~= 0 then
    emit(string.format("%9.6f C2 PA WR=%02X pc=%06X", t(), data & 0xff, c2.state["PC"].value)) end end)
print("HS2 armed")
