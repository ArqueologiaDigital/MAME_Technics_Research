-- A/B, no rebuild: make the WORKING build behave like the extraction's CORE for
-- the 16-bit timers.  Upstream MAME's tmp95c061 never sets INTET54/INTET76, so
-- INTTR4..INTTR7 can never be raised.  CPU1's prom_a enables INTTR4 with
-- `ld (0x75),0x03` at 0xF827CE (SFR 0x75 = INTET54, level 3); holding that
-- register at 0 makes INTTR4 undispatchable, which is what upstream gives.
-- Control = the identical run without this script (screen fills at t=21).
local m = manager.machine
local sp = m.devices[":cpu1"].spaces["program"]
local STOP = tonumber(os.getenv("STOP_AT") or "21")
_G.k4 = emu.add_machine_frame_notifier(function ()
  sp:write_u8(0x75, 0x00)
  if m.time:as_double() >= STOP then
    emu.print_error(string.format("AB: INTET54 held, reads back %02X at t=%.1f",
      sp:read_u8(0x75), m.time:as_double()))
    m.video:snapshot()
    m:exit()
  end
end)
