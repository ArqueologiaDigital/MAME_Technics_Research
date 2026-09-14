-- verify_in_emu.lua -- prove the monitor patch is live inside the RUNNING machine, and that
-- its claim path actually executes on the emulated TLCS-900.
--
--   cd $BUILD && ./kn7000 wsa1r -rompath <patched> -skip_gameinfo -window \
--        -autoboot_script tools/wsa1r-sysex-monitor/verify_in_emu.lua
--
-- Two checks:
--   1 READ-BACK.  The four hook bytes at 0xFA586E must be `1b 46 a2 fb' (jp 0xFBA246) and the
--     monitor's first bytes at 0xFBA246 must be the bit test.  This proves the image the machine
--     is executing is the patched one -- not the file on disk, the bytes in the CPU's map.
--   2 CLAIM PATH.  Simulate one accepted SysEx data byte: set the firmware's own state byte
--     (0xA9) = 0x01 ("identifier accepted"), put our marker 0x7D in E, point PC at the monitor
--     and let it run.  If (0xA9) bit 5 comes back SET, `.Lclaim' executed -- i.e. the monitor
--     recognised its marker and claimed the message.
--     ⚠ This is a UNIT test: it drives the routine directly rather than through the UART, so it
--     proves the monitor's logic and NOT the MIDI plumbing.  End-to-end needs a MIDI source.
local mach = manager.machine
local cpu  = mach.devices[":cpu1"]
local prog = cpu.spaces["program"]

local function hex(addr, n)
  local t = {}
  for i = 0, n - 1 do t[#t+1] = string.format("%02X", prog:read_u8(addr + i)) end
  return table.concat(t, " ")
end

local phase, t0 = 0, nil
_G._v = emu.register_frame_done(function()
  local ok, err = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds / 1e18
    if phase == 0 then
      if t < 4.0 then return end          -- let the firmware settle first
      emu.print_error("### 1 READ-BACK")
      emu.print_error(string.format("###   hook 0xFA586E : %s   (expect 1B 46 A2 FB)", hex(0xFA586E, 4)))
      emu.print_error(string.format("###   mon  0xFBA246 : %s", hex(0xFBA246, 5)))
      emu.print_error(string.format("###   tbl  0xFBA236 : %s   (expect F0 7E 7D 7F 01 00 F7)", hex(0xFBA236, 7)))
      phase, t0 = 1, t
    elseif phase == 1 and t >= t0 + 0.5 then
      emu.print_error("### 2 CLAIM PATH")
      prog:write_u8(0x00A9, 0x01)                       -- identifier accepted, bit 5 clear
      emu.print_error(string.format("###   (0xA9) before = 0x%02X", prog:read_u8(0x00A9)))
      -- ⚠ TLCS-900 registers are BANK-QUALIFIED in MAME's state interface: XWA0..XWA3,
      -- XBC0.., XDE0.., XHL0.. -- there is no plain "DE", and asking for one is a nil index
      -- (v1 did exactly that).  Which bank is live depends on RFP, so set them all.
      for b = 0, 3 do
        local k = "XDE" .. b
        if cpu.state[k] then cpu.state[k].value = 0x0000007D end
      end
      cpu.state["PC"].value = 0xFBA246                  -- enter the monitor
      phase, t0 = 2, t
    elseif phase == 2 and t >= t0 + 0.05 then
      local a9 = prog:read_u8(0x00A9)
      emu.print_error(string.format("###   (0xA9) after  = 0x%02X   bit5=%s",
          a9, ((a9 & 0x20) ~= 0) and "SET -- the monitor CLAIMED the message ✅"
                                  or  "clear -- claim path did NOT run ⛔"))
      emu.print_error("### done")
      mach:exit()
      phase = 3
    end
  end)
  if not ok then emu.print_error("### LUA ERR " .. tostring(err)) end
end)
emu.print_error("### verify_in_emu loaded")
