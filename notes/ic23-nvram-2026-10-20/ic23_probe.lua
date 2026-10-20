-- ic23_probe.lua -- at t = $IC23_AT seconds (default 44), print what the KN7000 firmware thinks of IC23, then quit.
--   valid    the byte BackupSramValidGet returns (0x5006CC80 in 941/935; -bios v16 or v15 only, else "n/a"):
--            0 = the header checksum matched at boot, -1 (0xff) = it did not
--   stored   the u32 at 0x84030174, where the firmware stamps the checksum
--   computed what the firmware computes: SumU32Words(0x84000000, 0x7A0), BackupSramChecksumVerify 0x484D78C3 in
--            941. Its loop runs the index from 0x1E8 down to 1, so it sums the u32 words at offsets 4..0x7A0
--            (the word at offset 0 is not included, the one at 0x7A0 is), then takes the one's complement
--   mirror   whether 0x44040000.. reads the same 4 KB as 0x44000000.. (the 256 KB repeat), and whether
--            0x84000000 reads the same as 0x44000000
-- Then, if $IC23_POWER is set, it presses the machine's POWER OFF (the driver pulses NMI, lets the firmware's
-- power-down run, and exits); otherwise it quits MAME directly, as closing the window does.
local mac = manager.machine
local sp = mac.devices[":maincpu"].spaces["program"]
local AT = tonumber(os.getenv("IC23_AT") or "44")
local VALID = os.getenv("IC23_VALID")   -- address of the validity byte, or unset
-- $IC23_PRESS = "PORT MASK" (e.g. "CPR_SEG9 08", BRASS): hold that panel button for 0.3 s at AT - 10 s, a real
-- change to the live panel settings (the checksummed header)
local PRESS = os.getenv("IC23_PRESS")
local pf
if PRESS and PRESS ~= "" then
  local tag, mask = PRESS:match("(%S+)%s+(%x+)")
  local port = mac.ioport.ports[":cpanel:" .. tag]
  if port then for _, f in pairs(port.fields) do if f.mask == tonumber(mask, 16) then pf = f end end end
end
local pstate = 0
local fired = false   -- a notifier keeps firing until it is garbage-collected, so guard it
_G.IC23P = emu.add_machine_frame_notifier(function()
  local now = mac.time:as_double()
  if pf and pstate == 0 and now >= AT - 10 then pf:set_value(1); pstate = 1; emu.print_error("PROBE pressed " .. PRESS) end
  if pf and pstate == 1 and now >= AT - 9.7 then pf:set_value(0); pstate = 2 end
  if fired or now < AT then return end
  fired = true
  local sum = 0
  for i = 4, 0x7A0, 4 do sum = (sum + sp:read_u32(0x84000000 + i)) & 0xffffffff end
  local computed = (~sum) & 0xffffffff
  local stored = sp:read_u32(0x84030174)
  local rep, alias = true, true
  for i = 0, 0xfff, 4 do
    if sp:read_u32(0x44040000 + i) ~= sp:read_u32(0x44000000 + i) then rep = false end
    if sp:read_u32(0x84000000 + i) ~= sp:read_u32(0x44000000 + i) then alias = false end
  end
  local v = VALID and string.format("%02x", sp:read_u8(tonumber(VALID))) or "n/a"
  emu.print_error(string.format("PROBE t=%.1f valid=%s stored=%08x computed=%08x match=%s repeat256k=%s alias84=%s",
    mac.time:as_double(), v, stored, computed, tostring(stored == computed), tostring(rep), tostring(alias)))
  local port = mac.ioport.ports[":POWER"]
  local power = os.getenv("IC23_POWER")   -- an empty value means no (Lua treats "" as true)
  if power and power ~= "" and port then
    for _, f in pairs(port.fields) do f:set_value(1) end
    emu.print_error("PROBE pressed POWER OFF")
    -- watch the power-down: the handler's last act is setting bit 3 of the GPIO latch 0x36008004 (the power
    -- latch); the stamp it wrote just before is at 0x84030174. The driver exits 100 ms after the press.
    local t0 = mac.time:as_double()
    local seen = false
    _G.IC23W = emu.add_machine_frame_notifier(function()
      local g = sp:read_u16(0x36008004)
      if not seen and (g & 0x08) ~= 0 then
        seen = true
        emu.print_error(string.format("PROBE power latch set after %.1f ms, stamp at 0x84030174 = %08x",
          (mac.time:as_double() - t0) * 1000, sp:read_u32(0x84030174)))
      end
    end)
  else
    mac:exit()
  end
end)
