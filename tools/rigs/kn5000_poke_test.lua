-- Direct 0x8E94 injection probe (reproduce the proven injection from the findings).
local mac  = manager.machine
local prog = mac.devices[":maincpu"].spaces["program"]
local function bpm() return prog:read_u16(0xFC62) & 0x1FF end
local function log(s) emu.print_error("[POKE] "..s) end
local st = 0
_G._poke = emu.add_machine_frame_notifier(function()
  local mt = mac.time
  local t  = mt.seconds + mt.attoseconds/1e18
  if st == 0 and t > 24 then st = 1; log("BASELINE bpm="..bpm()); mac.video:snapshot() end
  -- Inject +3 (should drive BPM DOWN per the sign-inverted curve) continuously 24.2..26.
  if t > 24.2 and t < 26.0 then
    prog:write_u8(0x8E94, 0x19)
    prog:write_u8(0x8E95, 0x03)
    prog:write_u8(0x8E96, 0xFF)
    prog:write_u8(0x8E97, 0xFF)
  end
  if st == 1 and t > 26.3 then st = 2; log("AFTER +3 inject bpm="..bpm()); mac.video:snapshot() end
  -- Inject -3 (should drive BPM UP) 26.5..28.3
  if t > 26.5 and t < 28.3 then
    prog:write_u8(0x8E94, 0x19)
    prog:write_u8(0x8E95, 0xFD)  -- -3
    prog:write_u8(0x8E96, 0xFF)
    prog:write_u8(0x8E97, 0xFF)
  end
  if st == 2 and t > 28.6 then st = 3; log("AFTER -3 inject bpm="..bpm()); mac.video:snapshot(); mac:exit() end
end)
