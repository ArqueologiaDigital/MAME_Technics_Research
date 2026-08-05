-- Long-capture nav for the KN5000 Feature Demo.
-- Same button sequence as sine_early.lua (engage at t=12), but:
--   * it does NOT touch :TGMODE (set_value TOGGLES a PORT_CONFNAME field) -- the render
--     mode comes from the private -cfg_directory and is only VERIFIED here;
--   * it prints TGMODE every second so the capture carries its own provenance.
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local sp   = cpu.spaces["program"]
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end
local u8 = function(a) return sp:read_u8(a) end
local function setbtn(tag, mk, v)
  local port = mach.ioport.ports[":cpanel:" .. tag]; if not port then return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end

local tgport = mach.ioport.ports[":TGMODE"]
local arport = mach.ioport.ports[":AREA"]
emu.print_info(string.format("### PORTS AT LOAD: TGMODE=%s AREA=%s",
  tgport and string.format("0x%02X", tgport:read()) or "MISSING",
  arport and string.format("0x%02X", arport:read()) or "MISSING"))

local phase, base, tick, sec = "boot", 0, 0, 0
_G._nav = emu.register_frame_done(function()
 pcall(function()
  local t = T()
  if t >= sec then
    sec = sec + 1
    emu.print_info(string.format("### TG t=%d TGMODE=0x%02X AREA=0x%02X", math.floor(t),
      tgport and tgport:read() or 255, arport and arport:read() or 255))
  end
  if phase=="boot" then if t>=12.0 then setbtn("CPL_SEG3",0x01,1); phase="d1"; base=t end
  elseif phase=="d1" then if t>=base+0.3 then setbtn("CPL_SEG3",0x01,0); phase="d2"; base=t end
  elseif phase=="d2" then if t>=base+1.5 then setbtn("CPL_SEG9",0x02,1); phase="d3"; base=t end
  elseif phase=="d3" then if t>=base+0.3 then setbtn("CPL_SEG9",0x02,0); phase="d4"; base=t end
  elseif phase=="d4" then
    if t>=base+1.5 then setbtn("CPL_SEG10",0x01,1); phase="d5"; base=t end
  elseif phase=="d5" then
    if t>=base+0.3 then setbtn("CPL_SEG10",0x01,0); phase="obs"; base=t
      emu.print_info("### DEMO ENGAGED") end
  elseif phase=="obs" then
    if t >= base + tick*2 then
      emu.print_info(string.format("### t=%.1f beat=%02X transport=%02X wd=%02X 332c=%02X 33d4=%02X songptr=%02X%02X",
        T(), u8(0x0417), u8(0x0420), u8(0x32ed), u8(0x332c), u8(0x33d4), u8(0x0426), u8(0x0425)))
      tick = tick + 1
    end
  end
 end)
end)
emu.print_info("### oracle_long.lua loaded")
