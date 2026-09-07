-- Which firmware routines run on an effect change?  Read-taps on CPU2 code addresses
-- fire on instruction fetch.  Count hits for ResolveProgramsAndReload (0xFA5535),
-- sub_FA3A3C (0xFA3A3C, the body reload), and P7Units_ServiceTask (0xFA5177).
local mac=manager.machine; local sp=mac.devices[":cpu2"].spaces["program"]
local hits={resolve=0, body=0, task=0, emitparams=0}
-- word-aligned tap ranges covering each entry byte
_G._taps={
  sp:install_read_tap(0xFA5534,0xFA5535,"resolve",function(o,d,k) hits.resolve=hits.resolve+1 return d end),
  sp:install_read_tap(0xFA3A3C,0xFA3A3D,"body",   function(o,d,k) hits.body=hits.body+1 return d end),
  sp:install_read_tap(0xFA5176,0xFA5177,"task",   function(o,d,k) hits.task=hits.task+1 return d end),
  sp:install_read_tap(0xFA3CD6,0xFA3CD7,"emit",   function(o,d,k) hits.emitparams=hits.emitparams+1 return d end),
}
local LIVE={[0]=0x856E,[1]=0x8588,[2]=0x85A2}; local TWIN={[0]=0x7E7E,[1]=0x7E98,[2]=0x7EB2}
local REC={[0]=0x8586,[1]=0x85A0,[2]=0x85BA}; local SHAD={[0]=0x85D4,[1]=0x85EE,[2]=0x8608}; local FLAG={[0]=0x02,[1]=0x04,[2]=0x08}
local function h() return string.format("task=%d resolve=%d body=%d emit=%d",hits.task,hits.resolve,hits.body,hits.emitparams) end
local function inz(d) local ir=mac.devices[":dsp"..d].spaces["iram"];local n=0
  for w=0,383 do for k=0,4 do if ir:read_u8(w*5+k)~=0 then n=n+1;break end end end return n end
local acts={};local function A(f,fn) acts[#acts+1]={f=f,fn=fn} end
A(900, function() print("BASELINE hits: "..h().."  IC30 I="..inz(2)) end)
A(950, function() print("-> flag ONLY (no program change): u0 flag|=0x02"); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x02) end)
A(1080,function() print("after flag-only: "..h()) end)
A(1140,function() print("-> u0 program 1->20 (live+twin) + flag"); sp:write_u8(LIVE[0],20);sp:write_u8(TWIN[0],20);sp:write_u8(0x7ECC,sp:read_u8(0x7ECC)|0x02) end)
A(1320,function() print("after u0=20: "..h().."  live="..sp:read_u8(LIVE[0]).." rec="..sp:read_u8(REC[0]).." shadow="..sp:read_u8(SHAD[0]).."  IC6 I="..inz(0).." IC30 I="..inz(2)) end)
A(1400,function() print("BODY-TAP DONE") end)
_G._f=0
_G._h=emu.add_machine_frame_notifier(function() _G._f=_G._f+1
  for _,a in ipairs(acts) do if a.f==_G._f then a.fn() end end end)
