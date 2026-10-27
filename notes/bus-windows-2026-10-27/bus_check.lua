-- bus_check.lua: do the KN7000's chip-select windows read in MAME as the owner's unit reads them? (ROM survey passes 4
-- and 5, Pinball PFT18; OVERLAY-GAPS G7, G10). At 30 s of emulated time, after the boot: open bus reads 0xFFFFFFFF;
-- each copy of a chip reads as the chip; IC19's 2 MB at 0x97800000, summed as little-endian halfwords the service ROM
-- test's way (0x4849FD9E), gives 0x21D8. Prints PASS/FAIL per line and exits.
--   cd ~/compartilhado/kn7000-emulator && ./kn7000 kn7000 -bios v13 -rompath ./roms -skip_gameinfo -window \
--     -nothrottle -autoboot_script <this file>
local M = manager.machine
local sp = M.devices[":maincpu"].spaces["program"]
local done = false
local fails = 0
local function check(what, ok)
  print(string.format("bus_check: %s %s", ok and "PASS" or "FAIL", what))
  if not ok then fails = fails + 1 end
end
local function same(a, b, n)  -- n words equal at a and b
  for i = 0, n - 1 do if sp:read_u32(a + 4 * i) ~= sp:read_u32(b + 4 * i) then return false end end
  return true
end
local function ff(a, n)
  for i = 0, n - 1 do if sp:read_u32(a + 4 * i) ~= 0xFFFFFFFF then return false end end
  return true
end
BUS_CHECK = emu.add_machine_frame_notifier(function()  -- (kept: a dropped subscription is collected and never runs)
  if done or M.time:as_double() < 30 then return end
  done = true
  check("CS0 0x40800000 open bus", ff(0x40800000, 64))
  check("CS0 0x41000000 empty slot open bus", ff(0x41000000, 64))
  check("CS3 library at +256 KB, +1 MB, +63.75 MB", same(0x4C000100, 0x4C040100, 64) and same(0x4C000100, 0x4C100100, 64) and same(0x8C000100, 0x8FFC0100, 64))
  check("CS4 work RAM at +4 MB and through 0x93C00000", same(0x50000010, 0x50400010, 64) and same(0x50000010, 0x93C00010, 64))
  check("CS5 0x54000000, 0x55000000, 0x94000000 open bus", ff(0x54000000, 64) and ff(0x55000000, 64) and ff(0x94000000, 64))
  check("CS5 empty slots 0x56000000, 0x57000000 open bus", ff(0x56000000, 64) and ff(0x57000000, 64))
  check("IC21 at 0x54800000, 0x54A00000, 0x56800000, 0x56E00000, 0x94800000 as at 0x96800000",
    same(0x96800000, 0x54800000, 256) and same(0x96800000, 0x54A00000, 256) and same(0x96800000, 0x56800000, 256)
    and same(0x96800000, 0x56E00000, 256) and same(0x96800000, 0x94800000, 256))
  check("IC19 at 0x55800000, 0x55E00000, 0x95800000, 0x97800000 as at 0x57800000",
    same(0x57800000, 0x55800000, 256) and same(0x57800000, 0x55E00000, 256) and same(0x57800000, 0x95800000, 256)
    and same(0x57800000, 0x97800000, 256))
  local sum = 0
  for a = 0x97800000, 0x979FFFFE, 2 do sum = (sum + sp:read_u16(a)) & 0xFFFF end
  check(string.format("IC19 ROM test sum at 0x97800000 = 0x%04X (want 0x21D8)", sum), sum == 0x21D8)
  print(string.format("bus_check: %d failed", fails))
  M:exit()
end)
