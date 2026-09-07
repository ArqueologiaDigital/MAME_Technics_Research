-- Decisive: can IC6/IC5 I-RAM EVER fill at runtime?  Clear the per-unit preamble
-- latch (0xF354+2u) so P7Unit_SendPreambleOnce re-sends the kernel program, force a
-- full reload, and watch I-RAM (corpus) AND C-RAM (capture-live control) on all 3.
local mac=manager.machine
local sp=mac.devices[":cpu2"].spaces["program"]
local function inz(d) local ir=mac.devices[":dsp"..d].spaces["iram"];local i=0
  for w=0,383 do for k=0,4 do if ir:read_u8(w*5+k)~=0 then i=i+1;break end end end return i end
local function cnz(d) local cr=mac.devices[":dsp"..d].spaces["cram"];local c=0
  for x=0,255 do if (cr:read_u32(x)&0xffffff)~=0 then c=c+1 end end return c end
local function snap(t) print(string.format("[%-14s] IC6 I=%d C=%d | IC5 I=%d C=%d | IC30 I=%d C=%d | preamble F354=%d F356=%d F358=%d",
  t, inz(0),cnz(0), inz(1),cnz(1), inz(2),cnz(2), sp:read_u8(0xF354),sp:read_u8(0xF356),sp:read_u8(0xF358))) end

local acts={};local function A(f,fn) acts[#acts+1]={f=f,fn=fn} end
A(900, function() snap("baseline") end)
A(950, function() print("-> clear preamble latches F354/F356/F358=0")
  sp:write_u8(0xF354,0);sp:write_u8(0xF355,0);sp:write_u8(0xF356,0);sp:write_u8(0xF357,0);sp:write_u8(0xF358,0);sp:write_u8(0xF359,0) end)
A(1000, function() print("-> set u0=9,u1=13,u2=20 + flag|=0x0E + group toggle")
  sp:write_u8(0x7E7E,9);sp:write_u8(0x7E98,13);sp:write_u8(0x7EB2,20)
  local g=sp:read_u8(0xF35D); sp:write_u8(0xF361,(g==0) and 1 or 0)
  sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x0E) end)
A(1200, function() snap("after reload1") end)
A(1260, function() print("-> clear latches again + u0=1,u1=1,u2=1 + flag|=0x0E")
  sp:write_u8(0xF354,0);sp:write_u8(0xF356,0);sp:write_u8(0xF358,0)
  sp:write_u8(0x7E7E,1);sp:write_u8(0x7E98,1);sp:write_u8(0x7EB2,1); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x0E) end)
A(1460, function() snap("after reload2") end)
A(1520, function() print("PRE DONE") end)

_G._f=0
_G._h=emu.add_machine_frame_notifier(function() _G._f=_G._f+1
  for _,a in ipairs(acts) do if a.f==_G._f then a.fn() end end end)
