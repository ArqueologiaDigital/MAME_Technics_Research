-- KN5000 tempo-wheel driver-path test.
-- Drives the :cpanel:ENCODER adjuster field (the DRIVER path: cpanel reads the raw
-- adjuster and deposits the scan-table entry at DRAM 0x8E94), and observes the BPM
-- word at DRAM 0xFC62 by READ-POLLING (write-taps are blind in this core).
local mac  = manager.machine
local prog = mac.devices[":maincpu"].spaces["program"]
local SNAPDIR = os.getenv("SNAPDIR") or "."

local function bpm() return prog:read_u16(0xFC62) & 0x1FF end
local function log(s) emu.print_error("[WHEEL] "..s) end

-- Grab the ENCODER adjuster field.
local encfield = nil
local port = mac.ioport.ports[":cpanel:ENCODER"]
for _, f in pairs(port.fields) do encfield = f end
log("encoder field = "..(encfield and encfield.name or "NIL"))

local st = 0
local cur = 50           -- current commanded field value (matches PORT_ADJUSTER default)
local function setenc(v)
  cur = v
  -- Match the layout widget (slider_lib add_rotary_knob): it sets field.user_value,
  -- which is what live().value tracks for an IPT_ADJUSTER. This is the DRIVER path.
  encfield.user_value = v
end

_G._wheel = emu.add_machine_frame_notifier(function()
  local mt = mac.time
  local t  = mt.seconds + mt.attoseconds/1e18
  local seq = {
    {24.0, function() log("BASELINE bpm="..bpm()); mac.video:snapshot() end},
    -- CW sweep: raise field one step every ~2 frames.
    {24.2, function() log("--- CW sweep start bpm="..bpm()) end},
  }
  local step = seq[st+1]
  if step and t > step[1] then st = st + 1; step[2]() end

  -- CW phase 24.2 .. 26.2: ramp field up to 74 (24 detents).
  if t > 24.2 and t < 26.2 and cur < 74 and (mt.attoseconds // 1e16) % 4 == 0 then
    setenc(cur + 1)
  end
  if st == 2 and t > 26.6 then
    log("AFTER CW bpm="..bpm().." field="..cur); mac.video:snapshot(); st = 3
  end
  if st == 3 and t > 27.2 then
    log("HOLD (should be stable) bpm="..bpm()); st = 4
    log("--- CCW sweep start")
  end
  -- CCW phase 27.2 .. 29.2: ramp field down to 26 (48 detents net down).
  if t > 27.2 and t < 29.2 and cur > 26 and (mt.attoseconds // 1e16) % 4 == 0 then
    setenc(cur - 1)
  end
  if st == 4 and t > 29.6 then
    log("AFTER CCW bpm="..bpm().." field="..cur); mac.video:snapshot(); st = 5
  end
  if st == 5 and t > 30.2 then
    log("HOLD2 (stable) bpm="..bpm()); st = 6; mac:exit()
  end
end)
