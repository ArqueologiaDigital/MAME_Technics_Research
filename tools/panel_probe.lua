local B={{"SEG0C",0x01},{"SEG0C",0x02},{"SEG0C",0x04},{"SEG0C",0x08},{"SEG0C",0x10},{"SEG0C",0x20},{"SEG0C",0x40},{"SEG0D",0x01},{"SEG0D",0x02},{"SEG0D",0x04},{"SEG0D",0x08},{"SEG0D",0x10},{"SEG0D",0x20},{"SEG0D",0x40},{"SEG0D",0x80},{"SEG0E",0x01},{"SEG0E",0x02},{"SEG0E",0x04},{"SEG0E",0x08},{"SEG0E",0x10},{"SEG0E",0x20},{"SEG0E",0x40},{"SEG0F",0x01},{"SEG0F",0x02},{"SEG0F",0x04},{"SEG0F",0x08},{"SEG0F",0x10},{"SEG0F",0x20},{"SEG0F",0x40},{"SEG0F",0x80},{"SEG10",0x01},{"SEG10",0x02},{"SEG10",0x04},{"SEG10",0x08},{"SEG10",0x10},{"SEG10",0x20},{"SEG10",0x40},{"SEG10",0x80},{"SEG11",0x01},{"SEG11",0x02},{"SEG11",0x04},{"SEG11",0x08},{"SEG11",0x10},{"SEG11",0x20},{"SEG11",0x40},{"SEG11",0x80},{"SEG12",0x01},{"SEG12",0x02},{"SEG12",0x04},{"SEG12",0x08},{"SEG12",0x40},{"SEG12",0x80},{"SEG13",0x01},{"SEG13",0x02},{"SEG13",0x04},{"SEG13",0x08},{"SEG13",0x40},{"SEG13",0x80},{"SEG14",0x04},{"SEG14",0x08},{"SEG15",0x04},{"SEG15",0x08}}
local i=1; local phase="boot"; local fc=0
local function setbtn(p,mk,v) for _,f in pairs(manager.machine.ioport.ports[":"..p].fields) do if f.mask==mk then f:set_value(v) end end end
emu.register_frame_done(function()
  local m=manager.machine; fc=fc+1
  if phase=="boot" then if m.time.seconds>=17 then m:save("home"); phase="load"; fc=0 end
  elseif phase=="load" then m:load("home"); phase="wait"; fc=0
  elseif phase=="wait" then if fc>=70 then setbtn(B[i][1],B[i][2],1); phase="hold"; fc=0 end
  elseif phase=="hold" then if fc>=80 then m.video:snapshot(); setbtn(B[i][1],B[i][2],0); i=i+1; if i>#B then m:exit() else phase="load"; fc=0 end end
  end
end)
