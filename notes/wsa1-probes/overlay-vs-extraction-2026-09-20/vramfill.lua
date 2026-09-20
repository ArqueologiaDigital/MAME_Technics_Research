-- Does the firmware ever write UI CONTENT into the SED1330's 32 KiB display RAM?
-- Counts non-zero bytes across 0x0000-0x7FFF every second of emulated time.
-- A rising count = the UI is being drawn; a flat 0 = the panel stays blank.
local lcdc = manager.machine.devices[":lcdc"]
local sp = nil
for name, s in pairs(lcdc.spaces) do sp = s ; print("space: "..name) end
local n = 0
vnotif = emu.add_machine_frame_notifier(function()
  n = n + 1
  if n % 60 ~= 0 then return end
  local nz = 0
  for a = 0, 0x7fff, 1 do if sp:read_u8(a) ~= 0 then nz = nz + 1 end end
  print(string.format("VRAM t=%3ds nonzero=%d", n // 60, nz))
end)
print("vramfill armed")
