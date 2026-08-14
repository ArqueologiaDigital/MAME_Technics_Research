_G.m=_G.m or {}; _G.m.st=0
local function press(p,mm,v) local pp=manager.machine.ioport.ports[p]; if not pp then return end; for _,f in pairs(pp.fields) do if f.mask==mm then f:set_value(v) end end end
_G.m.h=emu.add_machine_frame_notifier(function()
  local mt=manager.machine.time; local t=mt.seconds+mt.attoseconds/1e18; local st=_G.m.st
  if st==0 and t>16 then press(":KEYS1",0x0100,1); _G.m.st=1
  elseif st==1 and t>17 then press(":KEYS1",0x0100,0); _G.m.st=2 end
end)
