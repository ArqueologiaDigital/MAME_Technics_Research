-- QUESTION: CPU1 spins at 0xF8E671-0xF8E681 in the extraction build but passes
-- through it in the overlay build.  That loop is
--     f8e671 bit 7,(0x8a)      ; wait for the flag to clear
--     f8e676 jr Z,0xf8e69e     ; clear -> success
--     f8e678 ld BC,(0x80)      ; tick counter
--     f8e67b sub BC,HL
--     f8e67d cp BC,0x01f4      ; 500
--     f8e681 jr LE,0xf8e671
-- so it exits only when (0x8a).7 clears or the 16-bit tick at (0x80) advances
-- past 500.  This samples both, per second, on CPU1's program space.
local m = manager.machine
local sp = m.devices[":cpu1"].spaces["program"]
local STOP = tonumber(os.getenv("STOP_AT") or "20")
local nxt = 1
_G.wsa1_sw = emu.add_machine_frame_notifier(function ()
  local t = m.time:as_double()
  if t < nxt then return end
  nxt = nxt + 1
  emu.print_error(string.format(
    "t=%5.1f pc1=%06X  tick(0x80)=%04X  flag(0x8a)=%02X  6007d9=%02X 6007da=%02X 6007dc=%02X 6007e1=%02X  7e=%02X 7f=%02X",
    t, m.devices[":cpu1"].state["CURPC"].value,
    sp:read_u16(0x80), sp:read_u8(0x8a),
    sp:read_u8(0x6007d9), sp:read_u8(0x6007da), sp:read_u8(0x6007dc), sp:read_u8(0x6007e1),
    sp:read_u8(0x7e), sp:read_u8(0x7f)))
  if t >= STOP then m:exit() end
end)
