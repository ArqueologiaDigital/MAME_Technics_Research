-- Does a GROUP reload (P7Units_ReloadForGroup) upload I-RAM programs to all 3 DSPs?
-- Group state: 0x00F361 (requested) vs 0x00F35D (current); service task reloads all 3 on diff.
local mac=manager.machine
local sp=mac.devices[":cpu2"].spaces["program"]
local iwords={}
local function add() for d=0,2 do local ir=mac.devices[":dsp"..d].spaces["iram"]
  for w=0,383 do local nz=false local s={} for k=0,4 do local v=ir:read_u8(w*5+k);s[k+1]=v;if v~=0 then nz=true end end
   if nz then iwords[string.format("%02X%02X%02X%02X%02X",s[1],s[2],s[3],s[4],s[5])]=true end end end end
local function cnt(t) local n=0 for _ in pairs(t) do n=n+1 end return n end
local function inz(d) local ir=mac.devices[":dsp"..d].spaces["iram"];local i=0
  for w=0,383 do for k=0,4 do if ir:read_u8(w*5+k)~=0 then i=i+1;break end end end return i end
local function snap(t) add()
  print(string.format("[%-12s] F35D=%d F361=%d flag=%02X | IC6 I=%d IC5 I=%d IC30 I=%d | distinct-I=%d",
    t, sp:read_u8(0xF35D), sp:read_u8(0xF361), sp:read_u8(0x7ECC), inz(0),inz(1),inz(2), cnt(iwords))) end

local acts={};local function A(f,fn) acts[#acts+1]={f=f,fn=fn} end
A(900, function() snap("baseline") end)
A(960, function() local g=sp:read_u8(0xF35D); local ng=(g==0) and 1 or 0
  print("-> group toggle: F361="..ng.." + flag|=0x02"); sp:write_u8(0xF361,ng); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x02) end)
A(1140, function() snap("after grp1") end)
A(1200, function() local g=sp:read_u8(0xF35D); local ng=(g==0) and 1 or 0
  print("-> group toggle back: F361="..ng.." + flag|=0x02"); sp:write_u8(0xF361,ng); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x02) end)
A(1380, function() snap("after grp2") end)
-- also try COMBI-style: set all 3 unit flags + a unit program change together
A(1440, function() print("-> u0=9,u1=9,u2=9 + flag|=0x0E")
  sp:write_u8(0x7E7E,9); sp:write_u8(0x7E98,9); sp:write_u8(0x7EB2,9); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x0E) end)
A(1620, function() snap("after u012=9") end)
A(1680, function()
  print(string.format("FINAL distinct-I=%d",cnt(iwords)))
  local ks={} for k in pairs(iwords) do ks[#ks+1]=k end table.sort(ks)
  for _,k in ipairs(ks) do print("IWORD "..k) end
  print("GRP DONE") end)

_G._f=0
_G._h=emu.add_machine_frame_notifier(function() _G._f=_G._f+1
  for _,a in ipairs(acts) do if a.f==_G._f then a.fn() end end end)
