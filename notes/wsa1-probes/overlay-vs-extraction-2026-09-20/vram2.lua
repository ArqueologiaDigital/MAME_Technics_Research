-- Q: does the EXTRACTION's display-RAM fill EVER reach the overlay's 5562,
-- or does it plateau at 5070 (= a real missing 492 bytes)?
-- Reads the SED1330's 32 KiB videoram every 5 emulated seconds; prints max so far.
local lcdc = manager.machine.devices[":lcdc"]
local sp = nil
for name, s in pairs(lcdc.spaces) do sp = s end
local n = 0
local best = -1
vnotif = emu.add_machine_frame_notifier(function()
  n = n + 1
  if n % 300 ~= 0 then return end
  local nz = 0
  for a = 0, 0x7fff do if sp:read_u8(a) ~= 0 then nz = nz + 1 end end
  if nz > best then best = nz end
  print(string.format("VRAM t=%4ds nonzero=%d max=%d", n // 60, nz, best))
end)
print("vram2 armed")
