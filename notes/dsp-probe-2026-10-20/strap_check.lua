-- strap_check.lua -- what does the emulated KN7000 answer at the board strap 0x98070000, and what does the
-- firmware make of it? At t = 10 s: the halfword (Felipe's unit reads 0xF8F7, DSP probe pass 9), its fields
-- (bits 2:1 board class, bit 0 TgStrapProbeSideB, bits 7:4, bits 11:10 hardware subtype, bit 12 rear switch).
-- Then exits.
local sp = manager.machine.devices[":maincpu"].spaces["program"]
_G.STRAP = emu.add_machine_frame_notifier(function()
  if manager.machine.time:as_double() < 10 then return end
  local v = sp:read_u16(0x98070000)
  local sub = ({[0] = 5, 1, 2, 3})[(v >> 10) & 3]
  emu.print_error(string.format("STRAP 0x%04X: board class bits %d%d, bit0 %d, bits7:4 %X, subtype bits %d%d -> %d, bit12 %d%s",
    v, (v >> 2) & 1, (v >> 1) & 1, v & 1, (v >> 4) & 15, (v >> 11) & 1, (v >> 10) & 1, sub, (v >> 12) & 1,
    v == 0xF8F7 and "  = the unit" or "  (the unit: 0xF8F7)"))
  manager.machine:exit()
end)
