local B={{"cpanel:CPR_SEG0",0x01,"SOUND-PIANO"},{"cpanel:CPL_SEG0",0x08,"RHYTHM-POP"}}
local i=1; local phase="boot"; local fc=0
local function setbtn(p,mk,v)
  local port=manager.machine.ioport.ports[":"..p]
  if not port then print("NO PORT "..p) return end
  for _,f in pairs(port.fields) do if f.mask==mk then f:set_value(v) end end
end
emu.register_frame_done(function()
  local m=manager.machine; fc=fc+1
  if phase=="boot" then if m.time.seconds>=20 then m:save("k65home"); phase="load"; fc=0 end
  elseif phase=="load" then m:load("k65home"); phase="settle"; fc=0
  elseif phase=="settle" then if fc>=70 then phase="press"; fc=0 end
  elseif phase=="press" then setbtn(B[i][1],B[i][2],1); phase="hold"; fc=0
  elseif phase=="hold" then if fc>=90 then setbtn(B[i][1],B[i][2],0); m.video:snapshot(); print("KN6500 AFTER "..B[i][3]); i=i+1; if i>#B then m:exit() else phase="load"; fc=0 end end
  end
end)
