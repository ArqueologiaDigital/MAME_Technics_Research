-- libdump.lua -- dump the self-loaded sound library (0x4C000000-0x4C03FFFF) of a booted kn7000 to TR_OUT/lib.bin
-- (README.md here), for disassembly: unidasm lib.bin -arch mn10300 -basepc 0x4C000000. rig-machine: kn7000 -bios v13.
local M = manager.machine
local OUT = assert(os.getenv("TR_OUT"), "set TR_OUT")
local sp = M.devices[":maincpu"].spaces["program"]
_G.LD = emu.add_machine_frame_notifier(function()
  if M.time:as_double() < 20 then return end
  local f = assert(io.open(OUT .. "/lib.bin", "wb"))
  for a = 0x4C000000, 0x4C03FFFF, 4 do f:write(string.pack("<I4", sp:read_u32(a))) end
  f:close(); M:exit()
end)
