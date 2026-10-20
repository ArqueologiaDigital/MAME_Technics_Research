-- tm4_check.lua -- does the emulated KN7000 run its 1 kHz tick from TM4 as the unit does?
-- At t = 10 s and t = 20 s: TM4MD (0x34001080), TM4BR (0x34001090), a few TM4BC (0x340010A0) reads, and the
-- firmware's millisecond counter (the RTOS tick count at 0x50151BFC on 941; TM4_MSCOUNT overrides). Prints the
-- counter's rate over those 10 s of emulated time: 999.5 per s for a 2001-count period at 2 MHz. Then exits.
local sp = manager.machine.devices[":maincpu"].spaces["program"]
local MS = tonumber(os.getenv("TM4_MSCOUNT") or "0x50151BFC")
local t0, c0
_G.TM4C = emu.add_machine_frame_notifier(function()
  local t = manager.machine.time:as_double()
  if not t0 and t >= 10 then
    t0, c0 = t, sp:read_u32(MS)
    local bc = {}
    for i = 1, 4 do bc[#bc + 1] = string.format("%04X", sp:read_u16(0x340010A0)) end
    emu.print_error(string.format("TM4CHECK t=%.3f TM4MD %02X TM4BR %04X TM4BC %s ms %d", t, sp:read_u8(0x34001080),
      sp:read_u16(0x34001090), table.concat(bc, " "), c0))
  elseif t0 and t >= 20 then
    local c1 = sp:read_u32(MS)
    emu.print_error(string.format("TM4CHECK t=%.3f ms %d: %.2f per s of emulated time", t, c1, (c1 - c0) / (t - t0)))
    manager.machine:exit()
  end
end)
