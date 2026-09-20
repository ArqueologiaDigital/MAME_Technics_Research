-- Is CPU 1's inter-processor transfer ever completing?
-- RAM(0x8A) bit 7 = "link transfer in progress", polled by the timeout loop at
-- prom_a 0xF8E671; RAM(0x6007E1) is the byte that loop increments on every
-- 500-tick timeout (0xF8E694); RAM(0x80) is the timer tick counter.
local s1 = manager.machine.devices[":cpu1"].spaces["program"]
local n = 0
lsnotif = emu.add_machine_frame_notifier(function()
  n = n + 1
  if n % 60 ~= 0 then return end
  print(string.format("LINKSTATE f=%4d tick=%04X flag8A=%02X timeouts6007E1=%02X other6007DC=%02X",
    n, s1:read_u16(0x80), s1:read_u8(0x8a), s1:read_u8(0x6007e1), s1:read_u8(0x6007dc)))
end)
print("linkstate armed")
