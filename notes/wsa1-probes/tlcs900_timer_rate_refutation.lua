-- tlcs900_timer_rate_refutation.lua -- ADVERSARIAL re-measurement of the two
-- rate claims made for the tmp95c061 prescaler + 16-bit-timer fix (8ec12c6).
--
-- QUESTION IT ANSWERS: with the fix in, what rate do the timers ACTUALLY run
-- at, measured on the running machine rather than computed from the registers?
--
-- SIGNAL.  Every interrupt dispatch fetches its vector with RDMEML from
-- 0xFFFF00+vec.  On a 16-bit bus that is TWO tap invocations per dispatch, so
-- the true rate is (raw fetch rate)/2 -- the INTT1 column is the built-in
-- calibration: it must come out equal to the tick(0x80) rate, which the
-- firmware advances once per INTT1.
--
--   vec 0x44 = INTT1   vec 0x50 = INTTR4   vec 0x54 = INTTR5   vec 0x5C = INTTR7
--
-- PASS looks like: tick(0x80) = 488 Hz (firmware asks 28e6/2048/28 = 488.28),
-- INTTR4 = 224 Hz while TREG5 holds its boot 15625, dropping to 192 Hz once
-- prom_a's tempo setter stores 0x4735 = 18229 (= 120.00 BPM at 96 PPQN), and
-- INTTR5/INTTR7 fetch counts STAYING AT ZERO -- vectors 0x54/0x58/0x5C are
-- `jr T,self` at 0xF82D09, so any nonzero count there is a hung machine.
--
-- RUN (SX-WSA1R, cpu1):
--   cd ~/compartilhado/kn7000-emulator && DISPLAY=:0 timeout 300 ./kn7000 wsa1r \
--     -rompath ./roms -skip_gameinfo -str 45 -window \
--     -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/tlcs900_timer_rate_refutation.lua
--
-- MEASURED 2026-08-25 (binary of 18:27, carrying 8ec12c6):
--   tick(0x80)  488.0-489.0 Hz   (predicted 488.28)
--   INTT1       488.0 Hz         (976 raw / 2)
--   INTTR4      224.0 Hz  t<12s  (3.5 MHz / 15625, = 140.00 BPM)
--               192.0 Hz  t>12s  (3.5 MHz / 18229, = 120.00 BPM)
--   INTTR5, INTTR7 fetches: 0 for the whole 45 s.
-- For the KN1500 variant of this probe (device tag :maincpu) the same registers
-- at 24 MHz measured INTTR4 = 192.0 Hz = 120.00 BPM before that machine's known
-- boot failure parks it in a DI'd loop at 0xFA047F.
_G.tr4 = 0 ; _G.t1 = 0 ; _G.tr5 = 0 ; _G.tr7 = 0
local TAG = "cpu1"   -- wsa1/wsa1r; use "maincpu" for kn1500
local sp = manager.machine.devices[":" .. TAG].spaces["program"]
_G.k1 = sp:install_read_tap(0xFFFF50,0xFFFF53,"tr4",function(o,d,m) _G.tr4=_G.tr4+1 return d end)
_G.k2 = sp:install_read_tap(0xFFFF44,0xFFFF47,"t1", function(o,d,m) _G.t1 =_G.t1 +1 return d end)
_G.k3 = sp:install_read_tap(0xFFFF54,0xFFFF57,"tr5",function(o,d,m) _G.tr5=_G.tr5+1 return d end)
_G.k4 = sp:install_read_tap(0xFFFF5C,0xFFFF5F,"tr7",function(o,d,m) _G.tr7=_G.tr7+1 return d end)
_G.pt=0 ; _G.p4=0 ; _G.p1=0 ; _G.ptick=0 ; _G.n=0
_G.sub = emu.add_machine_frame_notifier(function ()
  _G.n=_G.n+1
  if (_G.n % 60) ~= 0 then return end
  local t = manager.machine.time:as_double()
  local tick = sp:read_u16(0x000080)
  local dt = t - _G.pt
  if dt > 0 and _G.pt > 0 then
    print(string.format(
      "t=%6.2f  INTTR4=%7.1f Hz  INTT1=%7.1f Hz  tick(0x80)=%7.1f Hz  beat(0x84)=%3d  INTTR5=%d INTTR7=%d",
      t, (_G.tr4-_G.p4)/dt/2, (_G.t1-_G.p1)/dt/2, (tick-_G.ptick)/dt,
      sp:read_u8(0x000084), _G.tr5, _G.tr7))
  end
  _G.pt=t ; _G.p4=_G.tr4 ; _G.p1=_G.t1 ; _G.ptick=tick
end)
