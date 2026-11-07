-- ic21_peek.lua -- does the CPU read IC21's CUSTOM bank in the file's byte order?
-- kn7000_custom_data.rom loads at chip offset 0x20000 = CPU 0x96820000; the file starts "IK" 01 01 08 02 16 02.
-- Prints the first 8 bytes the CPU reads there (byte reads, so no endianness of ours in it) at frame 2, before the
-- firmware writes the bank, and at IC21_LATE (default frame 2400, 40 s, the play screen): "IK" = right, "KI" = swapped.
-- IC21_FILE (the .rom): at the late peek, also how many of the bank's 0x1E0000 bytes the CPU reads equal the file's.
-- Run with a fresh -nvram_directory: IC21 is an nvram device and loads the ROM only when it has no saved image.
local late = tonumber(os.getenv("IC21_LATE") or "2400")
local sp = manager.machine.devices[":maincpu"].spaces["program"]
local function peek(tag)
  local b = {}
  for i = 0, 7 do b[#b + 1] = string.format("%02X", sp:read_u8(0x96820000 + i)) end
  local s = string.char(sp:read_u8(0x96820000), sp:read_u8(0x96820001))
  print(string.format("ic21_peek: %s frame %d: %s  (\"%s\")", tag, manager.machine.screens[":screen"]:frame_number(),
        table.concat(b, " "), s:gsub("[^%g]", ".")))
end
local n = 0
ic21_sub = emu.add_machine_frame_notifier(function()
  n = n + 1
  if n == 2 then peek("early") end
  if n == late then
    peek("late")
    local f = os.getenv("IC21_FILE")
    if f then
      local d = io.open(f, "rb"):read("a")
      local same = 0
      for i = 1, #d do if sp:read_u8(0x96820000 + i - 1) == d:byte(i) then same = same + 1 end end
      print(string.format("ic21_peek: late: %d of %d bytes = the file's (%.2f%%)", same, #d, 100 * same / #d))
    end
    manager.machine:exit()
  end
end)
