-- KN5000 tempo-wheel DETENT-LOSS rate test.
--
-- QUESTION ANSWERED: is "one BPM step per detent" true at every drag speed, or
-- does the 7 ms encoder scan out-run the firmware's main-loop poll and overwrite
-- a scan-table entry at 0x8E94 before it is consumed?
--
-- The HLE deposits [0x19, delta, 0xFF, 0xFF] at DRAM 0x8E94 and the firmware
-- clears the list (LD (0x8E94),0xFF at ROM 0xFC6C54) after consuming it.  If a
-- second detent is deposited before the poll runs, the first is LOST silently.
--
-- METHOD: two identical 20-detent sweeps at different rates, each followed by a
-- settle window; count BPM delta at 0xFC62 (low 9 bits).
--   PHASE A  1 detent every 12 frames (~200 ms) -- far slower than the main loop
--   PHASE B  1 detent every frame     (~16.7 ms) -- a normal fast drag
-- PASS: both phases move the tempo by exactly 20 BPM.
-- FAIL (detent loss): |BPM delta| < 20 in either phase.
--
-- RUN:
--   ./kn5000 kn5000 -rompath <roms> -window -seconds_to_run 45 -skip_gameinfo \
--       -nothrottle -autoboot_delay 0 \
--       -autoboot_script tools/rigs/kn5000_wheel_rate_test.lua
--
-- Port tag: ":ENCODER" when the port is driver-owned (the upstream PR shape),
-- ":cpanel:ENCODER" when it is owned by kn5000_cpanel_device (kn7000_mame).
local mac  = manager.machine
local prog = mac.devices[":maincpu"].spaces["program"]

local function bpm() return prog:read_u16(0xFC62) & 0x1FF end
local function log(s) emu.print_error("[RATE] "..s) end

local port = mac.ioport.ports[":ENCODER"] or mac.ioport.ports[":cpanel:ENCODER"]
if port == nil then log("FATAL: no ENCODER port"); mac:exit(); return end
local encfield = nil
for _, f in pairs(port.fields) do encfield = f end
log("field = "..(encfield and encfield.name or "NIL"))

-- IMPORTANT: MAME PERSISTS the adjuster in cfg/kn5000.cfg
-- (<port tag=":ENCODER" type="ADJUSTER" ... value="NN"/>), so the knob does NOT
-- start at 50 on a second run.  Read the real current value instead of assuming,
-- and delete cfg/kn5000.cfg before a run that must start from the default.
-- Frames between detents in PHASE A. Override with SLOW_DIV=<n> in the env.
local SLOW_DIV = tonumber(os.getenv("SLOW_DIV")) or 12
local frame   = 0
local cur     = encfield.user_value
local phase   = 0
local emitted = 0
local mark    = 0

_G._rate = emu.add_machine_frame_notifier(function()
  frame = frame + 1
  local mt = mac.time
  local t  = mt.seconds + mt.attoseconds/1e18
  if t < 24.0 then return end     -- wait for the HOME screen

  -- PHASE A: 20 detents up, one every SLOW_DIV frames.
  if phase == 0 then
    mark = bpm(); log("PHASE A start bpm="..mark.." field="..cur)
    phase = 1; emitted = 0
  elseif phase == 1 then
    if emitted < 20 then
      if frame % SLOW_DIV == 0 then cur = cur + 1; encfield.user_value = cur; emitted = emitted + 1 end
    elseif frame % SLOW_DIV == 0 then
      local d = bpm() - mark
      log("PHASE A  slow(1/"..SLOW_DIV.."frames)  detents=20  bpm delta="..d.." (expect +20)  bpm="..bpm())
      mark = bpm(); phase = 2; emitted = 0
    end

  -- PHASE B: 20 detents up, one every frame (~16.7 ms apart).
  elseif phase == 2 then
    if emitted < 20 then
      cur = cur + 1; encfield.user_value = cur; emitted = emitted + 1
    else
      phase = 3; mark = mark; emitted = 0
    end
  elseif phase == 3 then
    emitted = emitted + 1
    if emitted > 90 then   -- 1.5 s settle so every queued detent lands
      local d = bpm() - mark
      log("PHASE B  fast(1/frame)     detents=20  bpm delta="..d.." (expect +20)  bpm="..bpm())
      log("final field="..cur)
      phase = 4
      mac:exit()
    end
  end
end)
