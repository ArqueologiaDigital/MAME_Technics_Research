-- Does the Feature Demo transport run?  Navigation: DEMO -> LEFT 4 -> LEFT 2.
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local sp   = cpu.spaces["program"]
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end
local function u8(a) return sp:read_u8(a) end
local function setbtn(tag, mk, v)
  local p = mach.ioport.ports[":" .. tag] or mach.ioport.ports[":cpanel:" .. tag]
  if not p then emu.print_info("### MISSING PORT " .. tag) return end
  for _, f in pairs(p.fields) do if f.mask == mk then f:set_value(v) end end
end
local phase, base, tick = "boot", 0, 0
local seen_transport, max_beat = 0, 0
_G._nav = emu.register_frame_done(function()
 pcall(function()
  local t = T()
  if phase=="boot" then if t>=20.0 then setbtn("CPL_SEG3",0x01,1); phase="d1"; base=t end
  elseif phase=="d1" then if t>=base+0.3 then setbtn("CPL_SEG3",0x01,0); phase="d2"; base=t end
  elseif phase=="d2" then if t>=base+1.5 then setbtn("CPL_SEG9",0x02,1); phase="d3"; base=t end
  elseif phase=="d3" then if t>=base+0.3 then setbtn("CPL_SEG9",0x02,0); phase="d4"; base=t end
  elseif phase=="d4" then if t>=base+1.5 then setbtn("CPL_SEG10",0x01,1); phase="d5"; base=t end
  elseif phase=="d5" then if t>=base+0.3 then setbtn("CPL_SEG10",0x01,0); phase="obs"; base=t
      emu.print_info("### DEMO ENGAGED") end
  elseif phase=="obs" then
    local tr, be = u8(0x0420), u8(0x0417)
    if tr ~= 0 then seen_transport = seen_transport + 1 end
    if be > max_beat then max_beat = be end
    if t >= base + tick*2 then
      emu.print_info(string.format("### t=%.1f beat=%02X transport=%02X wd=%02X | live=%d maxbeat=%02X",
        t, be, tr, u8(0x32ed), seen_transport, max_beat))
      tick = tick + 1
    end
  end
 end)
end)
