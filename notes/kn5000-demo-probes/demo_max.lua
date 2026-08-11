-- Per-frame maxima, so a 0.3 s burst cannot be missed by coarse sampling.
-- Signals from notes/kn5000-demo-playback-stall.md.
local mach = manager.machine
local sp = mach.devices[":maincpu"].spaces["program"]
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end
local function u8(a) return sp:read_u8(a) end
local function setbtn(tag, mk, v)
  local p = mach.ioport.ports[":"..tag] or mach.ioport.ports[":cpanel:"..tag]
  if not p then emu.print_info("### MISSING "..tag) return end
  for _,f in pairs(p.fields) do if f.mask==mk then f:set_value(v) end end
end
local phase, base, tick = "boot", 0, 0
local mx = {subtick=0, transport=0, accmode=0, play8d38=0, ssf=0, wd=0}
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
    local v = {subtick=u8(0x0417), transport=u8(0x0420), accmode=u8(0x22FC),
               play8d38=u8(0x8D38), ssf=u8(0x251D8), wd=u8(0x32ed)}
    for k,x in pairs(v) do if x > mx[k] then mx[k] = x end end
    if t >= base + tick*5 then
      emu.print_info(string.format(
        "### t=%.0f now subtick=%02X | MAX subtick=%02X transport=%02X accmode=%02X 8d38=%02X ssf=%02X",
        t, v.subtick, mx.subtick, mx.transport, mx.accmode, mx.play8d38, mx.ssf))
      manager.machine.video:snapshot()
      tick = tick + 1
    end
  end
 end)
end)
