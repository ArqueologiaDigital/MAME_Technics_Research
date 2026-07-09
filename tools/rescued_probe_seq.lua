-- press buttons sequentially in one boot, snapshot after each
local B = { {"SEG0C",0x02,17.0}, {"SEG0E",0x02,19.0}, {"SEG0D",0x02,21.0} }
local function setbtn(p,mk,v) for _,f in pairs(manager.machine.ioport.ports[":"..p].fields) do if f.mask==mk then f:set_value(v) end end end
emu.register_frame_done(function()
  local m=manager.machine; local t=m.time.seconds
  for _,b in ipairs(B) do
    if not b.p and t>=b[3] then b.p=true; setbtn(b[1],b[2],1) end
    if not b.s and t>=b[3]+1.4 then b.s=true; m.video:snapshot(); setbtn(b[1],b[2],0) end
  end
end)
