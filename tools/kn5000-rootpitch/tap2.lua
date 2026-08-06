-- Same nav, but shadow EVERY per-voice register and dump the whole set at each note-on.
-- Question: does any register the HLE does not decode (+0x080, +0x0C0, +0x1C0, group 5/6/9/10)
-- carry the chunk's ROOT OCTAVE -- the one datum the pitch decode is missing?
local mach = manager.machine
local sub  = mach.devices[":subcpu"]
local sp   = sub.spaces["program"]
local cpu  = mach.devices[":maincpu"]
local msp  = cpu.spaces["program"]
local f    = io.open(os.getenv("TAPOUT") or "/tmp/kon2.log", "w")
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end

local GMAP = {[0]=0,[1]=1,[4]=2,[5]=3,[6]=4,[8]=5,[9]=6,[10]=7}
local latch, R, nk = 0, {}, 0
for ch = 0, 63 do R[ch] = {} end

_G._tgtap = sp:install_write_tap(0x100000, 0x100003, "tgtap2", function(offset, data, mask)
  local o = offset % 4
  if o == 0 then latch = data & 0xFFFF; return data end
  if o ~= 2 then return data end
  local a  = latch
  local grp = (a >> 8) & 0xFF
  local ch  = a & 0x3F
  local bk  = (a >> 6) & 3
  local gi  = GMAP[grp]
  if gi == nil then
    f:write(string.format("UNK %.6f %02d grp=%02X bk=%d %04X\n", T(), ch, grp, bk, data & 0xFFFF))
    return data
  end
  local ri = gi * 4 + bk
  if grp == 0 and bk == 0 and (data & 0xFF00) == 0x8100 then
    nk = nk + 1
    local s = {}
    for i = 0, 31 do s[#s+1] = string.format("%04X", R[ch][i] or 0) end
    f:write(string.format("KON %.6f %02d %s\n", T(), ch, table.concat(s, " ")))
  else
    R[ch][ri] = data & 0xFFFF
  end
  return data
end)

local phase, base, sec = "boot", 0, 0
local function setbtn(tag, mk, v)
  local port = mach.ioport.ports[":cpanel:" .. tag]; if not port then return end
  for _, fl in pairs(port.fields) do if fl.mask == mk then fl:set_value(v) end end
end
_G._nav = emu.register_frame_done(function()
 pcall(function()
  local t = T()
  if t >= sec then sec = sec + 5
    emu.print_info(string.format("### t=%d kon=%d transport=%02X", math.floor(t), nk, msp:read_u8(0x0420)))
    f:flush() end
  if phase=="boot" then if t>=12.0 then setbtn("CPL_SEG3",0x01,1); phase="d1"; base=t end
  elseif phase=="d1" then if t>=base+0.3 then setbtn("CPL_SEG3",0x01,0); phase="d2"; base=t end
  elseif phase=="d2" then if t>=base+1.5 then setbtn("CPL_SEG9",0x02,1); phase="d3"; base=t end
  elseif phase=="d3" then if t>=base+0.3 then setbtn("CPL_SEG9",0x02,0); phase="d4"; base=t end
  elseif phase=="d4" then if t>=base+1.5 then setbtn("CPL_SEG10",0x01,1); phase="d5"; base=t end
  elseif phase=="d5" then if t>=base+0.3 then setbtn("CPL_SEG10",0x01,0); phase="obs"; base=t
      emu.print_info("### DEMO ENGAGED") end
  end
 end)
end)
emu.print_info("### tap2.lua loaded")
