-- aw_power.lua -- one SP7001 session with the Another World card in the slot, ended by POWER OFF.
-- env: AW_PRESS (1 = press SD CARD LOAD at 12 s, which starts the game; unset = leave the instrument alone, the
--      control run), POWER_AT (s, default 60), IC23_VALID (address of BackupSramValidGet's byte; sp7001 0x5006CC90)
-- Prints at boot+POWER_AT, just before POWER OFF: the VM's part id (0x4407102A; 0x3E80-0x3E89 = a game part is
-- running), the firmware's IC23 verdict from this boot, and the stored and computed checksums (as ic23_probe.lua).
local mac = manager.machine
local sp = mac.devices[":maincpu"].spaces["program"]
local POWER_AT = tonumber(os.getenv("POWER_AT") or "60")
local VALID = os.getenv("IC23_VALID")
local SD
for _, p in pairs(mac.ioport.ports) do for name, f in pairs(p.fields) do
  if name:upper():find("SD CARD") then SD = f end end end
local pressed, released, done = false, false, false
_G.AWP = emu.add_machine_frame_notifier(function()
  local t = mac.time:as_double()
  local want = os.getenv("AW_PRESS")    -- an empty value means no (Lua treats "" as true)
  if want and want ~= "" and SD and not pressed and t > 12 then SD:set_value(1); pressed = true end
  if pressed and not released and t > 12.4 then SD:set_value(0); released = true end
  if done or t < POWER_AT then return end
  done = true
  local sum = 0
  for i = 4, 0x7A0, 4 do sum = (sum + sp:read_u32(0x84000000 + i)) & 0xffffffff end
  emu.print_error(string.format("PROBE t=%.1f part=%04x valid=%s stored=%08x computed=%08x",
    t, sp:read_u16(0x4407102A), VALID and string.format("%02x", sp:read_u8(tonumber(VALID))) or "n/a",
    sp:read_u32(0x84030174), (~sum) & 0xffffffff))
  for _, f in pairs(mac.ioport.ports[":POWER"].fields) do f:set_value(1) end
end)
