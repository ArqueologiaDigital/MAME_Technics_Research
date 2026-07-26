-- MUST-NOT-REGRESS: a HELD key must sustain for as long as it is down, and the firmware
-- must never reclaim it. Holds C4 for 12 s and logs every gate/free on group0/bank0.
local mach = manager.machine
local prog = mach.devices[":subcpu"].spaces["program"]
local f = io.open(os.getenv("LIFEOUT") or "/tmp/hold.log", "w")
local function L(s) f:write(s.."\n"); f:flush() end
local reg = 0
_G._r1 = prog:install_write_tap(0x100000, 0x100001, "a", function(o,d,m) reg=d&0xffff; return nil end)
_G._r2 = prog:install_write_tap(0x100002, 0x100003, "d", function(o,d,m)
  local a = reg & 0xffff
  if (a>>8)==0 and ((a>>6)&3)==0 then
    local dd = d & 0xffff
    if (dd&0xff00)==0x8100 or dd==0x7e00 then
      L(string.format("%.6f ch%02d %04X", mach.time:as_double(), a&0x3f, dd))
    end
  end
  return nil end)
local PRESS, REL, DONE = 20.0, 32.0, 34.0
local st = 0
local function key(v)
  local p = mach.ioport.ports[":KEY2"]; if not p then return end
  local fl = p.fields["C4"]; if fl then fl:set_value(v) end
end
emu.register_periodic(function()
  local t = mach.time:as_double()
  if t>=PRESS and t<REL then key(1); if st==0 then st=1; L("PRESS "..t) end
  elseif t>=REL then key(0); if st==1 then st=2; L("RELEASE "..t) end end
  if st==2 and t>=DONE then L("DONE"); mach:exit() end
end)
L("hold12 armed")
