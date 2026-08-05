-- Same as kn5000_demo_watch.lua but forces the tone generator into SINE mode.
-- No early exit: the demo is left playing until the host timeout.
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local sp   = cpu.spaces["program"]
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end
local u8 = function(a) return sp:read_u8(a) end
local function setbtn(tag, mk, v)
  local port = mach.ioport.ports[":cpanel:" .. tag]; if not port then return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end

local function snap(tag)
  emu.print_info(string.format(
    "### [%s] t=%.1f  style=%02X group=%02X bank=%02X sect=%02X | watchdog=%02X transport=%02X",
    tag, T(), u8(0x32e5), u8(0x32e6), u8(0x3285), u8(0x3305), u8(0x32ed), u8(0x0420)))
end

local phase, base, tick = "boot", 0, 0
_G._nav = emu.register_frame_done(function()
 pcall(function()
  local t = T()
  if phase=="boot" then if t>=12.0 then setbtn("CPL_SEG3",0x01,1); phase="d1"; base=t end
  elseif phase=="d1" then if t>=base+0.3 then setbtn("CPL_SEG3",0x01,0); phase="d2"; base=t end
  elseif phase=="d2" then if t>=base+1.5 then setbtn("CPL_SEG9",0x02,1); phase="d3"; base=t end
  elseif phase=="d3" then if t>=base+0.3 then setbtn("CPL_SEG9",0x02,0); phase="d4"; base=t end
  elseif phase=="d4" then
    if t>=base+1.5 then setbtn("CPL_SEG10",0x01,1); phase="d5"; base=t end
  elseif phase=="d5" then
    if t>=base+0.3 then setbtn("CPL_SEG10",0x01,0); phase="obs"; base=t
      emu.print_info("### DEMO ENGAGED - watch and listen") end
  elseif phase=="obs" then
    if t >= base + tick*2 then
      emu.print_info(string.format("### t=%.1f beat=%02X transport=%02X wd=%02X 332c=%02X 33d4=%02X songptr=%02X%02X",
        T(), u8(0x0417), u8(0x0420), u8(0x32ed), u8(0x332c), u8(0x33d4), u8(0x0426), u8(0x0425)))
      tick = tick + 1
    end
  end
 end)
end)
-- force TGMODE = 1 (sine)
local tg = mach.ioport.ports[":TGMODE"]
if tg then
  for _, f in pairs(tg.fields) do f:set_value(1) end
  emu.print_info("### TGMODE forced to SINE")
else
  emu.print_info("### ERROR: :TGMODE port not found")
end
emu.print_info("### demo watch loaded (SINE mode)")
