-- kn5000_dsp_frame_trace.lua : capture a LIVE per-word frame trace of the uPD6383GF
-- WHILE NOTES ARE PLAYING, to confront it with the HLE biquad oracle
-- (kn5000-roms-disasm dsp/hle/lle_trace_diff.py).  What that diff decides: the
-- hi12 "+=" accumulator op (the running-sum test) and, on the biquad, the D-RAM
-- operand origin m_dp.
--
-- The core dumps its TIME-ORDERED FRAME TRACE to the error log at exit
-- (device_stop -> dump_frame_report), and arms it once m_frames_run (DSP-ON frames,
-- ~44100/s) passes env UPD6383_TRACE_FRAME.  For the trace to carry signal:
--   * DSPCFG bit0 is turned on (the emulation gate; "decoded ISA, silent"), so
--     run_frame() actually executes the words;
--   * ★ RULE 12: a chord is HELD on the internal keybed, so real audio flows into
--     the DSP (the tonegen feeds di[] the whole mix) -- otherwise every product is
--     zero and the running-sum test proves nothing.
-- The default effect (program 0) already runs at boot with its coefficients routed,
-- so NO panel navigation is needed for the accumulator-op decode.  Set NAV=1 to also
-- walk SOUND -> DSP EFFECT editor and select TYPEIDX (for the EQ biquad specifically;
-- the display-poll readback is subprogram-version specific and may garble).
--
-- Env:
--   UPD6383_TRACE_FRAME : DSP-ON frame to arm at (default env, e.g. 500000 ~ 11 s of DSP).
--   NAV     : "1" to navigate to a DSP-EFFECT TYPE; default "0" (use the boot default).
--   TYPEIDX : type index when NAV=1 (0=CHORUS .. 15=PARAMETRIC EQ .. 37).  Default 15.
--   DWELL   : seconds to hold the chord before exit (default 18).
-- Run (from the build tree, DSP-enabled binary):
--   UPD6383_TRACE_FRAME=500000 ./kn7000 kn5000 -rompath ./roms -skip_gameinfo \
--       -nothrottle -window -nomaximize -log -autoboot_script tools/rigs/kn5000_dsp_frame_trace.lua
--   then grep error.log for "TIME-ORDERED FRAME TRACE".
local NAV     = (os.getenv("NAV") or "0") == "1"
local TYPEIDX = tonumber(os.getenv("TYPEIDX") or "15")
local DWELL   = tonumber(os.getenv("DWELL") or "18")
local mach = manager.machine
local sp = mach.devices[":maincpu"].spaces["program"]

local function fieldset(tag, mask, v)
  local port = mach.ioport.ports[tag]
  if not port then emu.print_info("### NO PORT "..tag); return end
  for _, f in pairs(port.fields) do if f.mask == mask then f:set_value(v) end end
end
local function setbtn(tag, mk, v) fieldset(":cpanel:" .. tag, mk, v) end
local function key(mask, v) fieldset(":KEY1", mask, v) end   -- KEY1 = C3..B3

local function dspcfg_on()
  local port = mach.ioport.ports[":DSPCFG"]
  if not port then emu.print_info("### NO DSPCFG PORT (build without KN5000_ENABLE_DSP1=1?)"); return end
  for _, f in pairs(port.fields) do if f.mask == 0x03 then f:set_value(0x01) end end
  emu.print_info("### DSPCFG = 0x01 (decoded ISA, silent)")
end

local steps = {}
local function add(dt, fn) steps[#steps+1] = {dt, fn} end

add(0.0, function() dspcfg_on() end)
if NAV then
  add(0.4, function() setbtn("CPR_SEG3", 0x04, 1) end)     -- DSP EFFECT toggle
  add(0.3, function() setbtn("CPR_SEG3", 0x04, 0) end)
  add(0.8, function() setbtn("CPR_SEG10", 0x04, 1) end)    -- SOUND menu
  add(0.4, function() setbtn("CPR_SEG10", 0x04, 0) end)
  add(1.5, function() setbtn("CPL_SEG7", 0x02, 1) end)     -- DSP EFFECT editor
  add(0.4, function() setbtn("CPL_SEG7", 0x02, 0) end)
  for i=1,40 do
    add(0.08, function() setbtn("CPL_SEG10", 0x10, 1) end) -- saturate DOWN -> CHORUS
    add(0.08, function() setbtn("CPL_SEG10", 0x10, 0) end)
  end
  for i=1,TYPEIDX do
    add(0.10, function() setbtn("CPL_SEG10", 0x20, 1) end) -- UP -> type
    add(0.10, function() setbtn("CPL_SEG10", 0x20, 0) end)
  end
  -- leave the editor so the keybed plays notes (an edit dialog can swallow keys)
  add(0.5, function() setbtn("CPR_SEG10", 0x04, 1) end)
  add(0.4, function() setbtn("CPR_SEG10", 0x04, 0) end)
end
-- ★ RULE 12: real audio into the DSP.  The DEMO song is self-driving audio (a
-- factory performance), far more reliable than scripted keybed voice allocation,
-- and drives the whole mix -> the tonegen feeds di[] non-zero -> the biquad gets
-- non-zero operands.  AUDIO=key falls back to holding a chord on the keybed.
local AUDIO = os.getenv("AUDIO") or "demo"
add(0.6, function()
  if AUDIO == "key" then
    key(0x001,1); key(0x010,1); key(0x080,1); emu.print_info("### chord held C3/E3/G3")
  else
    setbtn("CPL_SEG3", 0x01, 1); emu.print_info("### DEMO pressed")
  end
end)
add(0.4, function() if AUDIO ~= "key" then setbtn("CPL_SEG3", 0x01, 0) end end)
add(DWELL, function() mach.video:snapshot() end)
add(0.3, function() if AUDIO == "key" then key(0x001,0); key(0x010,0); key(0x080,0) end end)
add(0.5, function() emu.print_info("### exiting -> frame trace flush"); mach:exit() end)

local phase, next_t = 0, nil
_G._n = emu.register_frame_done(function()
  local ok,e = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds/1e18
    if phase == 0 then
      if t >= (tonumber(os.getenv("BOOTGATE") or "6")) then phase = 1; next_t = t + steps[1][1] end
      return
    end
    if next_t and t >= next_t then
      steps[phase][2]()
      phase = phase + 1
      if phase > #steps then next_t = nil else next_t = t + steps[phase][1] end
    end
  end)
  if not ok then emu.print_info("### CB ERR "..tostring(e)) end
end)
emu.print_info(string.format("### frame_trace rig loaded NAV=%s TYPEIDX=%d DWELL=%.1f steps=%d",
  tostring(NAV), TYPEIDX, DWELL, #steps))
