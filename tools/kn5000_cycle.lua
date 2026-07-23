-- kn5000_cycle.lua : on a chosen effect-edit page, cycle the TYPE selector (UP1) through every
-- effect, logging the on-screen title (DRAM 0x30AE5) + the name-index array (RAM[0x29AC..], count
-- RAM[0x29AA]). Env PAGE selects which edit page to open:
--   DSP  -> SOUND MENU right-4 (CPL_SEG7 0x02)   [default]
--   REV  -> SOUND MENU right-2 (CPL_SEG8 0x02)   (REVERB)
--   DEF  -> SOUND MENU right-1 (CPL_SEG8 0x04)   (REVERB & EQ PRESETS)  -- adjust as needed
local PAGE = os.getenv("PAGE") or "DSP"
local NSTEPS = tonumber(os.getenv("NSTEPS") or "90")
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
local function idxdump(step)
  local cnt=sp:read_u8(0x29AA); local s=""
  for i=0,24 do s=s..sp:read_u8(0x29AC+i)..(i<24 and "," or "") end
  emu.print_info(string.format("### STEP %d title='%s' type=0x%02X cnt=%d idx=[%s]",
    step, title(), sp:read_u8(0x8D38), cnt, s))
end

-- page-open soft key
local openkeys = { DSP={"CPL_SEG7",0x02}, REV={"CPL_SEG8",0x02},
  P1={"CPL_SEG8",0x04},  -- RIGHT1 REVERB & EQ PRESETS
  EQ={"CPL_SEG8",0x01},  -- RIGHT3 EQUALIZER
  AIL={"CPL_SEG7",0x01}, -- RIGHT5 ACOUSTIC ILLUSION
}
local ok = openkeys[PAGE]
local DIRMASK = (os.getenv("DIR")=="DOWN") and 0x10 or 0x20  -- UP1=0x20, DOWN1=0x10

local phase="boot"; local base=0; local i=0
_G._n=emu.register_frame_done(function()
 local okp,e = pcall(function()
  local t=mach.time.seconds+mach.time.attoseconds/1e18
  if phase=="boot" then
    if t>=19.0 then setbtn("CPR_SEG10",0x04,1); phase="m1"; base=t end
  elseif phase=="m1" then
    if t>=base+0.4 then setbtn("CPR_SEG10",0x04,0); phase="m2"; base=t end
  elseif phase=="m2" then
    if t>=base+1.5 then setbtn(ok[1],ok[2],1); phase="m3"; base=t end
  elseif phase=="m3" then
    if t>=base+0.4 then setbtn(ok[1],ok[2],0); phase="settle"; base=t end
  elseif phase=="settle" then
    if t>=base+1.2 then idxdump(0); mach.video:snapshot(); phase="press"; base=t; i=0 end
  elseif phase=="press" then
    setbtn("CPL_SEG10", DIRMASK, 1); phase="hold"; base=t
  elseif phase=="hold" then
    if t>=base+0.25 then setbtn("CPL_SEG10", DIRMASK, 0); phase="wait"; base=t end
  elseif phase=="wait" then
    -- long settle so the LCD redraw fully catches up to RAM before we read BOTH together
    if t>=base+1.00 then
      i=i+1; idxdump(i)
      local sm=os.getenv("SNAP")
      if sm=="all" then mach.video:snapshot() elseif sm~="0" and i%15==0 then mach.video:snapshot() end
      if i>=NSTEPS then mach:exit() else phase="press"; base=t end
    end
  end
 end)
 if not okp then emu.print_info("### CB ERR "..tostring(e)) end
end)
emu.print_info("### cycle loaded PAGE="..PAGE.." NSTEPS="..NSTEPS)
