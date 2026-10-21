-- passage.lua -- the G19 noise passage: held notes with the panel REVERB in its boot state, then toggled, then back.
-- rig-machine: kn7000 (-bios v13, program 893)
--
-- QUESTIONS IT SERVES (notes/dsp-noise-2026-10-21/README.md):
--   * the same short, deterministic passage for every recording (-wavwrite: the computed stream; or a live capture);
--   * how fast the emulation runs in each part of it (wall time per emulated second, from emu.osd_ticks());
--   * does the firmware's "DSP dead" flag stay 0 (893: 0x500066D8).
--
-- Timeline (emulated seconds, T0 = NP_T0, default 26; the firmware is at its play screen by then):
--   T0+0..3   C4 held                       part "A1" (REVERB as at boot; its LED is logged)
--   T0+4..7   C4 E4 G4 held                 part "A2"
--   T0+10     REVERB pressed (0.3 s)
--   T0+12..15 C4 held                       part "B1" (REVERB toggled)
--   T0+16..19 C4 E4 G4 held                 part "B2"
--   T0+22     REVERB pressed again (back to the boot state)
--   T0+24     exit
-- Every emulated second it logs "SPEED t=<s> wall=<s> pct=<emulated/wall %> video_pct=<MAME's own figure>", and at
-- each event "EV t=<s> <what> reverb_led=<0/1> chorus_led=<0/1> dead=<byte>". Log: $NP_OUT/passage.txt.
local M = manager.machine
local OUT = assert(os.getenv("NP_OUT"), "set NP_OUT")
local T0 = tonumber(os.getenv("NP_T0") or "26")
local DEAD = tonumber(os.getenv("NP_DEAD") or "0x500066D8")
local sp = M.devices[":maincpu"].spaces["program"]
local log = assert(io.open(OUT .. "/passage.txt", "w"))
local function now() return M.time.seconds + M.time.attoseconds / 1e18 end
local function W(fmt, ...) log:write(string.format(fmt, ...) .. "\n"); log:flush() end
local function field(port, mask)
  local p = M.ioport.ports[":cpanel:" .. port] or M.ioport.ports[":" .. port]
  for _, f in pairs(p.fields) do if f.mask == mask then return f end end
  error("no field " .. port .. " " .. mask)
end
local C4, E4, G4 = field("KEYS1", 0x0100), field("KEYS1", 0x1000), field("KEYS1", 0x8000)
local REV = field("CPR_SEG3", 0x04)
local function led(n) return math.floor(M.output:get_value(n) or 0) end
local function ev(what)
  W("EV t=%.3f %s reverb_led=%d chorus_led=%d dead=%02X", now(), what, led("cpr_led27"), led("cpr_led29"),
    sp:read_u8(DEAD))
end
local steps = {
  { 0.0, function() C4:set_value(1); ev("A1 on (C4)") end },
  { 3.0, function() C4:set_value(0); ev("A1 off") end },
  { 4.0, function() C4:set_value(1); E4:set_value(1); G4:set_value(1); ev("A2 on (C4 E4 G4)") end },
  { 7.0, function() C4:set_value(0); E4:set_value(0); G4:set_value(0); ev("A2 off") end },
  { 10.0, function() REV:set_value(1); ev("REVERB press") end },
  { 10.3, function() REV:set_value(0) end },
  { 12.0, function() C4:set_value(1); ev("B1 on (C4)") end },
  { 15.0, function() C4:set_value(0); ev("B1 off") end },
  { 16.0, function() C4:set_value(1); E4:set_value(1); G4:set_value(1); ev("B2 on (C4 E4 G4)") end },
  { 19.0, function() C4:set_value(0); E4:set_value(0); G4:set_value(0); ev("B2 off") end },
  { 22.0, function() REV:set_value(1); ev("REVERB press (back)") end },
  { 22.3, function() REV:set_value(0) end },
  { 24.0, function() ev("end"); log:close(); M:exit() end },
}
-- NP_EXTRA: another script to load (a tap); it may set _G.NP_EXTRA_SECOND(s, W), called once per emulated second.
if os.getenv("NP_EXTRA") then dofile(os.getenv("NP_EXTRA")) end
local nexts, tps = 1, emu.osd_ticks_per_second()
local last_s, last_tick = nil, nil
_G.NP = emu.add_machine_frame_notifier(function()
  local t = now()
  local s = math.floor(t)
  if last_s == nil then last_s, last_tick = s, emu.osd_ticks()
  elseif s > last_s then
    local tk = emu.osd_ticks()
    local wall = (tk - last_tick) / tps
    W("SPEED t=%d wall=%.3f pct=%.1f video_pct=%.1f", s, wall, 100.0 * (s - last_s) / wall,
      100.0 * M.video.speed_percent)
    last_s, last_tick = s, tk
    if _G.NP_EXTRA_SECOND then _G.NP_EXTRA_SECOND(s, W) end
  end
  while nexts <= #steps and t >= T0 + steps[nexts][1] do steps[nexts][2](); nexts = nexts + 1 end
end)
