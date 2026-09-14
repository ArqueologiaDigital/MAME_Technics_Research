local mach = manager.machine
local prog = mach.devices[":cpu1"].spaces["program"]
local n = 0
local tap = prog:install_read_tap(0xFA5496, 0xFA5497, "rx", function(o,d,m) n = n + 1; return d end)
_G._t = tap
local done = false
_G._f = emu.register_frame_done(function()
  local t = mach.time.seconds + mach.time.attoseconds/1e18
  if t >= 8.5 and not done then
    done = true
    emu.print_error(string.format("### MIDI_RX_Byte entered : %d", n))
    emu.print_error(string.format("### framing-error count (0x0931) : %d", prog:read_u8(0x0931)))
    emu.print_error(string.format("### parser status (0x9E) : 0x%02X", prog:read_u8(0x009E)))
    emu.print_error(string.format("### SysEx state (0xA9)   : 0x%02X", prog:read_u8(0x00A9)))
    emu.print_error(string.format("### running status (0x9A): 0x%02X", prog:read_u8(0x009A)))
  end
end)
