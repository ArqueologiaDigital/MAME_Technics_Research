-- KN6000 panel verification: press a few buttons whose silk name predicts a VISIBLE effect,
-- snapshotting a baseline before each press so the change is attributable.
local B={
 {"cpanel:CPR_SEG6",0x08,"START-STOP"},        -- normSeg 0x10 b3 = START/STOP
 {"cpanel:CPR_SEG6",0x80,"DISK"},              -- normSeg 0x10 b7 = DISK
 {"cpanel:CPR_SEG6",0x40,"PROGRAM-MENU"},      -- normSeg 0x10 b6 = PROGRAM MENU
 {"cpanel:CPL_SEG8",0x08,"HELP"},              -- normSeg 0x08 b3 = HELP
 {"cpanel:CPL_SEG9",0x40,"DEMO"},              -- normSeg 0x09 b6 = DEMO
 {"cpanel:CPL_SEG0",0x08,"RHYTHM-POP"},        -- normSeg 0x00 b3 = POP (rhythm group)
 {"cpanel:CPR_SEG0",0x01,"SOUND-PIANO"},       -- normSeg 0x0A b0 = PIANO (sound group)
 {"cpanel:CPR_SEG9",0x02,"PANEL-MEMORY-2"},    -- normSeg 0x13 b1 = PANEL MEMORY 2
}
local i=1; local phase="boot"; local fc=0
local function setbtn(p,mk,v)
  local port=manager.machine.ioport.ports[":"..p]
  if not port then print("NO PORT "..p) return end
  for _,f in pairs(port.fields) do if f.mask==mk then f:set_value(v) end end
end
emu.register_frame_done(function()
  local m=manager.machine; fc=fc+1
  if phase=="boot" then
    if m.time.seconds>=20 then m:save("k6home"); phase="load"; fc=0 end
  elseif phase=="load" then m:load("k6home"); phase="settle"; fc=0
  elseif phase=="settle" then
    if fc>=70 then m.video:snapshot(); print("BASELINE before "..B[i][3]); phase="press"; fc=0 end
  elseif phase=="press" then
    setbtn(B[i][1],B[i][2],1); phase="hold"; fc=0
  elseif phase=="hold" then
    if fc>=90 then
      setbtn(B[i][1],B[i][2],0); m.video:snapshot(); print("AFTER "..B[i][3])
      i=i+1; if i>#B then m:exit() else phase="load"; fc=0 end
    end
  end
end)
