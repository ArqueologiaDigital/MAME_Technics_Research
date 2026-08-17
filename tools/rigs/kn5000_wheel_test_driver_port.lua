-- KN5000 tempo-wheel test, DRIVER-OWNED PORT variant.
--
-- QUESTION ANSWERED: does the tempo wheel still step one BPM per detent when
-- the ENCODER port lives in the DRIVER (":ENCODER", INPUT_PORTS_START(kn5000))
-- and the scan reads it with a plain `m_encoder->read()` instead of the
-- overlay's raw `field.live().value`?
--
-- Why it matters: `read()` returns the PORT defvalue, which ioport_manager
-- refreshes only once per emulated frame (ioport.cpp: frame_update ->
-- ioport_port::update_defvalue).  The 7 ms scan therefore sees a target that
-- can be up to ~16 ms stale.  The argument that this only adds latency (the
-- scan walks one detent per tick toward a monotonically-converging target)
-- needs a measurement, not an argument.
--
-- This is the sibling of kn5000_wheel_test.lua, which drives ":cpanel:ENCODER"
-- (the kn7000_mame overlay, where the port is owned by kn5000_cpanel_device).
-- Keep both: they exercise two different port owners AND two different reads.
--
-- SIGNAL READ: BPM word at main-CPU DRAM 0xFC62, low 9 bits, by read-polling
-- (write taps are blind in this core).
-- PASS: AFTER CW bpm == BASELINE + 24, AFTER CCW bpm == BASELINE - 24, and the
--       HOLD samples are identical to the sample before them (no drift).
--
-- RUN:
--   ./mamekn5000 kn5000 -rompath <roms> -autoboot_script tools/rigs/kn5000_wheel_test_driver_port.lua \
--                -autoboot_delay 0 -skip_gameinfo
local mac  = manager.machine
local prog = mac.devices[":maincpu"].spaces["program"]

local function bpm() return prog:read_u16(0xFC62) & 0x1FF end
local function log(s) emu.print_error("[WHEEL] "..s) end

-- Grab the ENCODER adjuster field from the DRIVER-level port.
local encfield = nil
local port = mac.ioport.ports[":ENCODER"]
if port == nil then
  log("FATAL: no :ENCODER port -- is the port still owned by :cpanel?")
  for tag, _ in pairs(mac.ioport.ports) do log("  port: "..tag) end
  mac:exit()
  return
end
for _, f in pairs(port.fields) do encfield = f end
log("encoder field = "..(encfield and encfield.name or "NIL"))

local st = 0
local cur = 50           -- matches PORT_ADJUSTER(50, ...)
local base = nil
local function setenc(v)
  cur = v
  encfield.user_value = v  -- writes ioport_field::live().value, as the UI slider does
end

_G._wheel = emu.add_machine_frame_notifier(function()
  local mt = mac.time
  local t  = mt.seconds + mt.attoseconds/1e18
  local seq = {
    {24.0, function() base = bpm(); log("BASELINE bpm="..base); mac.video:snapshot() end},
    {24.2, function() log("--- CW sweep start bpm="..bpm()) end},
  }
  local step = seq[st+1]
  if step and t > step[1] then st = st + 1; step[2]() end

  -- CW 24.2 .. 26.2: 24 detents up.
  if t > 24.2 and t < 26.2 and cur < 74 and (mt.attoseconds // 1e16) % 4 == 0 then
    setenc(cur + 1)
  end
  if st == 2 and t > 26.6 then
    log("AFTER CW bpm="..bpm().." field="..cur.." (expect "..(base+24)..")")
    mac.video:snapshot(); st = 3
  end
  if st == 3 and t > 27.2 then
    log("HOLD (should be stable) bpm="..bpm()); st = 4
    log("--- CCW sweep start")
  end
  -- CCW 27.2 .. 29.2: 48 detents down (net -24 from baseline).
  if t > 27.2 and t < 29.2 and cur > 26 and (mt.attoseconds // 1e16) % 4 == 0 then
    setenc(cur - 1)
  end
  if st == 4 and t > 29.6 then
    log("AFTER CCW bpm="..bpm().." field="..cur.." (expect "..(base-24)..")")
    mac.video:snapshot(); st = 5
  end
  if st == 5 and t > 30.2 then
    log("HOLD2 (stable) bpm="..bpm()); st = 6; mac:exit()
  end
end)
