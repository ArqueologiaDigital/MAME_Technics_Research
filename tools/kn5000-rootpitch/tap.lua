-- Tap the IC303 register bus and log, for every NOTE-ON, the voice's wave selector
-- (+0x040) and absolute log pitch (+0x400).  Nav = oracle_long.lua (demo engaged at t=12).
-- Register-indirect: address latch at 0x100000, data at 0x100002 (kn5000.cpp:582-583).
--   per-voice addr: ch = a & 0x3F, bank = (a>>6)&3, group = a>>8
--   group0/bank0 data 0x81xx = NOTE ON;  group0/bank1 = +0x040;  group4/bank0 = +0x400
local mach = manager.machine
local sub  = mach.devices[":subcpu"]
local sp   = sub.spaces["program"]
local cpu  = mach.devices[":maincpu"]
local msp  = cpu.spaces["program"]
local OUT  = os.getenv("TAPOUT") or "/tmp/kon.log"
local f    = io.open(OUT, "w")
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end

local latch, sel, pit, nkon = 0, {}, {}, 0
_G._tgtap = sp:install_write_tap(0x100000, 0x100003, "tgtap", function(offset, data, mask)
  local o = offset % 4
  if o == 0 then
    latch = data & 0xFFFF
  elseif o == 2 then
    local a = latch
    local grp = (a >> 8) & 0xFF
    local ch  = a & 0x3F
    local bk  = (a >> 6) & 3
    if grp == 0x00 then
      if bk == 1 then
        sel[ch] = data & 0xFFFF
      elseif bk == 0 and (data & 0xFF00) == 0x8100 then
        nkon = nkon + 1
        f:write(string.format("KON %.6f %02d %04X %04X\n", T(), ch, sel[ch] or 0, pit[ch] or 0))
      end
    elseif grp == 0x04 and bk == 0 then
      pit[ch] = data & 0xFFFF
    end
  end
  return data
end)

-- nav: identical to oracle_long.lua
local phase, base, sec = "boot", 0, 0
local function setbtn(tag, mk, v)
  local port = mach.ioport.ports[":cpanel:" .. tag]; if not port then return end
  for _, fl in pairs(port.fields) do if fl.mask == mk then fl:set_value(v) end end
end
_G._nav = emu.register_frame_done(function()
 pcall(function()
  local t = T()
  if t >= sec then
    sec = sec + 5
    emu.print_info(string.format("### t=%d kon=%d beat=%02X transport=%02X", math.floor(t),
      nkon, msp:read_u8(0x0417), msp:read_u8(0x0420)))
    f:flush()
  end
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
emu.print_info("### tap.lua loaded")
