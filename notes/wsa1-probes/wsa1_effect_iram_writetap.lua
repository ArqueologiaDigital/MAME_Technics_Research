-- Does host_w WRITE any DSP I-RAM on an effect change?  Write-taps on each DSP's iram
-- and cram spaces count actual writes (a count-of-nonzero can't see same-value writes).
local mac=manager.machine
local iw={[0]=0,[1]=0,[2]=0}; local cw={[0]=0,[1]=0,[2]=0}
_G._taps={}
for d=0,2 do
  local dev=mac.devices[":dsp"..d]
  _G._taps[#_G._taps+1]=dev.spaces["iram"]:install_write_tap(0x0000,0x077F,"iw"..d,(function(dd) return function(o,data,k) iw[dd]=iw[dd]+1 return data end end)(d))
  _G._taps[#_G._taps+1]=dev.spaces["cram"]:install_write_tap(0x0000,0x03FF,"cw"..d,(function(dd) return function(o,data,k) cw[dd]=cw[dd]+1 return data end end)(d))
end
local sp=mac.devices[":cpu2"].spaces["program"]
local function h() return string.format("IRAM writes[%d/%d/%d] CRAM writes[%d/%d/%d]",iw[0],iw[1],iw[2],cw[0],cw[1],cw[2]) end
local acts={};local function A(f,fn) acts[#acts+1]={f=f,fn=fn} end
A(900, function() print("BASELINE "..h()) end)
A(950, function() iw[0]=0;iw[1]=0;iw[2]=0;cw[0]=0;cw[1]=0;cw[2]=0; print("(counters zeroed)")
  print("-> u0 program 1->20"); sp:write_u8(0x856E,20);sp:write_u8(0x7E7E,20);sp:write_u8(0x7ECC,sp:read_u8(0x7ECC)|0x02) end)
A(1130,function() print("after u0=20 (delta since zero): "..h()) end)
A(1180,function() iw[0]=0;iw[1]=0;iw[2]=0;cw[0]=0;cw[1]=0;cw[2]=0
  print("-> u1 program ->9"); sp:write_u8(0x8588,9);sp:write_u8(0x7E98,9);sp:write_u8(0x7ECC,sp:read_u8(0x7ECC)|0x04) end)
A(1360,function() print("after u1=9 (delta): "..h()) end)
A(1420,function() print("WTAP DONE") end)
_G._f=0
_G._h=emu.add_machine_frame_notifier(function() _G._f=_G._f+1
  for _,a in ipairs(acts) do if a.f==_G._f then a.fn() end end end)
