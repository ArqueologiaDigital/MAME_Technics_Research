-- As hs2, plus CPU 2's DMA vector registers (DMA0V..DMA3V at SFR 0x7C..0x7F).
local mac = manager.machine
local c1 = mac.devices[":cpu1"]
local c2 = mac.devices[":cpu2"]
local s1 = c1.spaces["program"]
local s2 = c2.spaces["program"]
n = 0
local function t() return mac.time.seconds + mac.time.attoseconds/1e18 end
local function emit(s) n = n + 1 if n < 600 then print("HS "..s) end end
lw = s1:install_write_tap(0x7c0000, 0x7c0001, "lw", function(off, data, mask)
  emit(string.format("%9.6f LINKW %02X pc=%06X", t(), data & 0xff, c1.state["PC"].value)) end)
lr = s2:install_read_tap(0x100000, 0x100001, "lr", function(off, data, mask)
  emit(string.format("%9.6f LINKR %02X pc=%06X", t(), data & 0xff, c2.state["PC"].value)) end)
dv = s2:install_write_tap(0x7c, 0x7f, "dv", function(off, data, mask)
  for b = 0, 1 do
    local sh = b * 8
    if (mask >> sh) & 0xff ~= 0 then
      emit(string.format("%9.6f C2 DMA%dV=%02X pc=%06X", t(), (off - 0x7c) + b, (data >> sh) & 0xff, c2.state["PC"].value))
    end
  end end)
print("HS3 armed")
