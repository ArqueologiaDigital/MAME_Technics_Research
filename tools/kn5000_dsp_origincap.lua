-- kn5000_dsp_origincap.lua : drive the KN5000 panel to select a chosen DSP-EFFECT
-- type, so the firmware pushes that effect's DSP configuration over the uC-IF and
-- the uPD6383 capture (kn5000_dsp1_upload.{bin,txt}, written at exit) contains its
-- pointer-init poke.  Companion to tools/kn5000_dsp_origincap.py.
--
-- Env:
--   TYPEIDX : DSP-EFFECT TYPE index to land on (0=CHORUS .. 15=PARAMETRIC EQ .. 37).
--             Default 15 (PARAMETRIC EQ).  The list does NOT wrap, so we first
--             press DOWN-1 40x to saturate at index 0 (CHORUS), then UP-1 TYPEIDX
--             times -- robust regardless of the boot default.
--   ENABLE  : "1" (default) toggles DSP EFFECT ON via the front panel before editing.
--
-- Navigation is MEASURED (notes/kn5000-dsp-paramlist.md):
--   SOUND menu  = CPR_SEG10 0x04 ; DSP EFFECT editor = CPL_SEG7 0x02
--   TYPE up/down = CPL_SEG10 0x20 / 0x10 ; DSP EFFECT front-panel = CPR_SEG3 0x04
local TYPEIDX = tonumber(os.getenv("TYPEIDX") or "15")
local ENABLE  = (os.getenv("ENABLE") or "1") ~= "0"
local mach = manager.machine
local sp = mach.devices[":maincpu"].spaces["program"]

local function setbtn(tag, mk, v)
  local port = mach.ioport.ports[":cpanel:" .. tag]
  if not port then emu.print_info("### NO PORT "..tag); return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end
local function title()
  local s=""
  for i=0,17 do local c=sp:read_u8(0x30AE5+i); if c>=32 and c<127 then s=s..string.char(c) else s=s.." " end end
  return (s:gsub("%s+$",""))
end
local function report(tag)
  local cnt=sp:read_u8(0x29AA); local s=""
  for i=0,24 do s=s..sp:read_u8(0x29AC+i)..(i<24 and "," or "") end
  emu.print_info(string.format("### %s title='%s' page=0x%02X type=0x%02X cnt=%d idx=[%s]",
    tag, title(), sp:read_u8(0x8D38), sp:read_u8(0x8D38), cnt, s))
end

-- queue of {t_delay_after_prev, fn}
local steps = {}
local function add(dt, fn) steps[#steps+1] = {dt, fn} end

add(0.0, function() emu.print_info("### boot settle done") end)          -- @ t0
if ENABLE then
  add(0.4, function() setbtn("CPR_SEG3", 0x04, 1) end)   -- DSP EFFECT toggle press
  add(0.3, function() setbtn("CPR_SEG3", 0x04, 0); report("after DSP-EFFECT toggle") end)
end
add(0.8, function() setbtn("CPR_SEG10", 0x04, 1) end)    -- SOUND menu press
add(0.4, function() setbtn("CPR_SEG10", 0x04, 0) end)
add(1.5, function() setbtn("CPL_SEG7", 0x02, 1) end)     -- DSP EFFECT editor (RIGHT-4)
add(0.4, function() setbtn("CPL_SEG7", 0x02, 0) end)
add(1.5, function() report("editor opened") end)
-- saturate DOWN to CHORUS (index 0)
for i=1,40 do
  add(0.10, function() setbtn("CPL_SEG10", 0x10, 1) end)
  add(0.10, function() setbtn("CPL_SEG10", 0x10, 0) end)
end
add(1.2, function() report("saturated DOWN -> CHORUS") end)
-- step UP to the target index
for i=1,TYPEIDX do
  add(0.12, function() setbtn("CPL_SEG10", 0x20, 1) end)
  add(0.12, function() setbtn("CPL_SEG10", 0x20, 0) end)
end
add(1.5, function() report("landed on target"); mach.video:snapshot() end)
add(1.0, function() report("settled"); mach.video:snapshot() end)
add(0.5, function() emu.print_info("### exiting -> capture files flush"); mach:exit() end)

local phase = 0
local next_t = nil
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
      if phase > #steps then next_t = nil
      else next_t = t + steps[phase][1] end
    end
  end)
  if not ok then emu.print_info("### CB ERR "..tostring(e)) end
end)
emu.print_info(string.format("### origincap loaded TYPEIDX=%d ENABLE=%s steps=%d", TYPEIDX, tostring(ENABLE), #steps))
