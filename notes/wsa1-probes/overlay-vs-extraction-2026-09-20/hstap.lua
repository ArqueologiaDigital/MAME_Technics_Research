-- Watch the link handshake pins around the first CPU1->CPU2 block transfer.
local mac = manager.machine
local c1 = mac.devices[":cpu1"]
local c2 = mac.devices[":cpu2"]
local s1 = c1.spaces["program"]
local s2 = c2.spaces["program"]
armed = false
n1 = 0
n2 = 0
nl = 0
local function t() return mac.time.seconds + mac.time.attoseconds/1e18 end
lw = s1:install_write_tap(0x7c0000, 0x7c0001, "lw", function(off, data, mask)
  nl = nl + 1
  if nl >= 4 and not armed then armed = true end   -- skip CPU2's boot C0/A1/A1
  if nl < 400 then print(string.format("HS %8.5f LINKW %02X pc=%06X", t(), data & 0xff, c1.state["PC"].value)) end
end)
lr = s2:install_read_tap(0x100000, 0x100001, "lr", function(off, data, mask)
  if nl < 400 then print(string.format("HS %8.5f LINKR %02X pc=%06X", t(), data & 0xff, c2.state["PC"].value)) end
end)
p7r = s1:install_read_tap(0x12, 0x13, "p7r", function(off, data, mask)
  if armed and n1 < 250 then n1 = n1 + 1
    if (mask & 0xff00) ~= 0 then print(string.format("HS %8.5f C1 P7 rd=%02X pc=%06X", t(), (data >> 8) & 0xff, c1.state["PC"].value)) end end
end)
p7w = s1:install_write_tap(0x12, 0x13, "p7w", function(off, data, mask)
  if armed and n1 < 250 then n1 = n1 + 1
    if (mask & 0xff00) ~= 0 then print(string.format("HS %8.5f C1 P7 WR=%02X pc=%06X", t(), (data >> 8) & 0xff, c1.state["PC"].value)) end end
end)
paw = s2:install_write_tap(0x1e, 0x1f, "paw", function(off, data, mask)
  if armed and n2 < 250 then n2 = n2 + 1
    if (mask & 0x00ff) ~= 0 then print(string.format("HS %8.5f C2 PA WR=%02X pc=%06X", t(), data & 0xff, c2.state["PC"].value)) end end
end)
par = s2:install_read_tap(0x1e, 0x1f, "par", function(off, data, mask)
  if armed and n2 < 250 then n2 = n2 + 1
    if (mask & 0x00ff) ~= 0 then print(string.format("HS %8.5f C2 PA rd=%02X pc=%06X", t(), data & 0xff, c2.state["PC"].value)) end end
end)
print("HSTAP armed")
