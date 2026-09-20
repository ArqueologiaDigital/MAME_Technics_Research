-- Log every byte crossing the CPU1<->CPU2 link, both directions, with time.
-- Taps held in globals (GC would otherwise drop them).
local mac = manager.machine
local c1 = mac.devices[":cpu1"]
local c2 = mac.devices[":cpu2"]
local s1 = c1.spaces["program"]
local s2 = c2.spaces["program"]
n = 0
local function t() return mac.time.seconds + mac.time.attoseconds/1e18 end
tap1r = s1:install_read_tap(0x7c0000, 0x7c0001, "l1r", function(off, data, mask)
  n = n + 1
  if n < 4000 then print(string.format("LINK %8.4f C1<- %04X pc=%06X", t(), data & 0xffff, c1.state["PC"].value)) end
end)
tap1w = s1:install_write_tap(0x7c0000, 0x7c0001, "l1w", function(off, data, mask)
  n = n + 1
  if n < 4000 then print(string.format("LINK %8.4f C1-> %04X pc=%06X", t(), data & 0xffff, c1.state["PC"].value)) end
end)
tap2r = s2:install_read_tap(0x100000, 0x100001, "l2r", function(off, data, mask)
  n = n + 1
  if n < 4000 then print(string.format("LINK %8.4f C2<- %04X pc=%06X", t(), data & 0xffff, c2.state["PC"].value)) end
end)
tap2w = s2:install_write_tap(0x100000, 0x100001, "l2w", function(off, data, mask)
  n = n + 1
  if n < 4000 then print(string.format("LINK %8.4f C2-> %04X pc=%06X", t(), data & 0xffff, c2.state["PC"].value)) end
end)
print("LINKTAP armed")
