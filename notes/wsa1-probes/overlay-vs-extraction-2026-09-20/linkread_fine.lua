-- Q: does CPU 1 ever DRAIN the inter-processor link latch, or does it read the
-- header byte once and then stall on its 500-tick timeout forever?
--   reads of 0x7C0000  = CPU 1 consuming a link byte (cpu1_link_r)
--   RAM 0x8A bit 7     = "link transfer in progress" (polled at prom_a 0xF8E671)
--   RAM 0x6007E1       = the byte the timeout path at 0xF8E694 increments
--   RAM 0x0080         = the firmware tick counter -- report per TICK, not per second,
--                        so the 16x prescaler difference does not confound the count.
local s1 = manager.machine.devices[":cpu1"].spaces["program"]
local cpu1 = manager.machine.devices[":cpu1"]
lr_reads = 0
lr_pcs = {}
lrtap = s1:install_read_tap(0x7c0000, 0x7c0001, "linkread", function(offset, data, mask)
  lr_reads = lr_reads + 1
  local pc = cpu1.state["PC"].value
  lr_pcs[pc] = (lr_pcs[pc] or 0) + 1
  return data
end)
local n = 0
lrnotif = emu.add_machine_frame_notifier(function()
  n = n + 1
  if n % 60 ~= 0 then return end
  print(string.format("LINKREAD t=%4ds tick=%d reads=%d flag8A=%02X timeouts=%d",
    n // 60, s1:read_u16(0x80), lr_reads, s1:read_u8(0x8a), s1:read_u8(0x6007e1)))
end)
lrstop = emu.add_machine_stop_notifier(function()
  print(string.format("=== FINAL tick=%d linkreads=%d flag8A=%02X timeouts=%d ===",
    s1:read_u16(0x80), lr_reads, s1:read_u8(0x8a), s1:read_u8(0x6007e1)))
  for k,v in pairs(lr_pcs) do print(string.format("  reader PC %06X  %d", k, v)) end
end)
print("linkread armed")
