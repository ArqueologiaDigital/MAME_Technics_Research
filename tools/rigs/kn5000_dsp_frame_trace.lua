-- kn5000_dsp_frame_trace.lua : capture a LIVE per-word frame trace of the uPD6383GF
-- running the PARAMETRIC EQ program, to confront it with the HLE biquad oracle
-- (kn5000-roms-disasm dsp/hle/lle_trace_diff.py).  What that diff decides: the
-- hi12 "+=" accumulator op (the running-sum test) and the D-RAM operand origin
-- m_dp (the dp column at the biquad's class-A words -- the number Q1/origincap
-- left as a per-effect host poke, EQ = 0x19).
--
-- This reuses the MEASURED panel navigation of tools/kn5000_dsp_origincap.lua
-- (SOUND -> DSP EFFECT editor -> saturate DOWN to CHORUS -> step UP to the type),
-- and adds the two things a frame trace needs that the origin capture did not:
--   (1) it turns the EMULATION gate DSPCFG on (bit 0 = "decoded ISA only, silent"),
--       so run_frame() actually executes the words -- the firmware's own DSP-EFFECT
--       ON (ENABLE) is separate and still pressed;
--   (2) it DWELLS on the selected effect for many seconds, so the core's frame
--       trace (armed by env UPD6383_TRACE_FRAME, a frame count) fires while the
--       chosen program is the one running.  The device dumps the TIME-ORDERED
--       FRAME TRACE to the error log at exit (device_stop -> dump_frame_report).
--
-- Env:
--   TYPEIDX : DSP-EFFECT TYPE index (0=CHORUS .. 15=PARAMETRIC EQ .. 37).  Default 15.
--   DWELL   : seconds to hold on the effect before exit (default 10).
-- Run (from the build tree, with the DSP-enabled binary):
--   UPD6383_TRACE_FRAME=1850000 ./kn7000 kn5000 -rompath ./roms -skip_gameinfo \
--       -nothrottle -window -nomaximize -log -autoboot_script tools/rigs/kn5000_dsp_frame_trace.lua
--   then grep error.log for "TIME-ORDERED FRAME TRACE".
local TYPEIDX = tonumber(os.getenv("TYPEIDX") or "15")
local DWELL   = tonumber(os.getenv("DWELL") or "10")
local mach = manager.machine
local sp = mach.devices[":maincpu"].spaces["program"]

local function setbtn(tag, mk, v)
  local port = mach.ioport.ports[":cpanel:" .. tag]
  if not port then emu.print_info("### NO PORT "..tag); return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end

-- (1) turn the emulation-side DSP gate on: DSPCFG bit0 = "On (decoded ISA only - silent)".
local function dspcfg_on()
  local port = mach.ioport.ports[":DSPCFG"]
  if not port then emu.print_info("### NO DSPCFG PORT (build without KN5000_ENABLE_DSP1=1?)"); return end
  for _, f in pairs(port.fields) do if f.mask == 0x03 then f:set_value(0x01) end end
  emu.print_info("### DSPCFG set to 0x01 (decoded ISA, silent)")
end

local function title()
  local s=""
  for i=0,17 do local c=sp:read_u8(0x30AE5+i); if c>=32 and c<127 then s=s..string.char(c) else s=s.." " end end
  return (s:gsub("%s+$",""))
end
local function report(tag)
  emu.print_info(string.format("### %s title='%s' page=0x%02X", tag, title(), sp:read_u8(0x8D38)))
end

local steps = {}
local function add(dt, fn) steps[#steps+1] = {dt, fn} end

add(0.0, function() dspcfg_on(); emu.print_info("### boot settle done") end)
add(0.4, function() setbtn("CPR_SEG3", 0x04, 1) end)     -- DSP EFFECT toggle (firmware ON)
add(0.3, function() setbtn("CPR_SEG3", 0x04, 0); report("after DSP-EFFECT toggle") end)
add(0.8, function() setbtn("CPR_SEG10", 0x04, 1) end)    -- SOUND menu
add(0.4, function() setbtn("CPR_SEG10", 0x04, 0) end)
add(1.5, function() setbtn("CPL_SEG7", 0x02, 1) end)     -- DSP EFFECT editor
add(0.4, function() setbtn("CPL_SEG7", 0x02, 0) end)
add(1.5, function() report("editor opened") end)
for i=1,40 do
  add(0.10, function() setbtn("CPL_SEG10", 0x10, 1) end) -- DOWN -> saturate at CHORUS
  add(0.10, function() setbtn("CPL_SEG10", 0x10, 0) end)
end
add(1.2, function() report("saturated DOWN -> CHORUS") end)
for i=1,TYPEIDX do
  add(0.12, function() setbtn("CPL_SEG10", 0x20, 1) end) -- UP -> target type
  add(0.12, function() setbtn("CPL_SEG10", 0x20, 0) end)
end
add(1.5, function() report("landed on target"); mach.video:snapshot() end)
-- DWELL on the effect so the frame trace (armed by UPD6383_TRACE_FRAME) fires here.
add(DWELL, function() report("dwell complete"); mach.video:snapshot() end)
add(0.5, function() emu.print_info("### exiting -> frame trace + capture flush"); mach:exit() end)

local phase, next_t = 0, nil
_G._n = emu.register_frame_done(function()
  local ok,e = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds/1e18
    if phase == 0 then
      if t >= 19.0 then phase = 1; next_t = t + steps[1][1] end
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
emu.print_info(string.format("### frame_trace rig loaded TYPEIDX=%d DWELL=%.1f steps=%d", TYPEIDX, DWELL, #steps))
