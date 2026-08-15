-- probe_late.lua -- sweep all eight SOUND GROUP buttons, snapshotting after each.
-- rig-machine: kn7000
--
-- Presses PIANO, GUITAR, STRINGS & VOCAL, BRASS, FLUTE, SAX & REED, MALLET & ORCH PERC and
-- WORLD PERC on :cpanel:CPR_SEG2 in turn from t=20 s, holding each 0.4 s and snapshotting 0.6 s
-- after release. One run gives eight labelled captures, so a mis-mapped bit shows up as two
-- buttons producing the same screen.
--
--   ./tools/rig.sh probe_late kn7000 -s 40
--
-- Prints PRESS/SNAP per button with its bit number; exits after the last.
-- ⚠ Fields are matched by NAME, so it silently does nothing if a PORT_NAME changes -- check for
--   eight PRESS lines before trusting a null.

local M=manager.machine
local function field(pt,nm) local p=M.ioport.ports[pt]; if not p then return nil end
  for k,f in pairs(p.fields) do if f.name==nm then return f end end return nil end
local function tap(t,n) local f=field(t,n); if f then f:set_value(1) end end
local function rel(t,n) local f=field(t,n); if f then f:set_value(0) end end
local names2={"PIANO","GUITAR","STRINGS & VOCAL","BRASS","FLUTE","SAX & REED","MALLET & ORCH PERC","WORLD PERC"}
local seq={}; local t=20.0
local function add(nm,lbl)
  seq[#seq+1]={t=t,fn=function() tap(":cpanel:CPR_SEG2",nm); emu.print_error("PRESS "..lbl) end}; t=t+0.4
  seq[#seq+1]={t=t,fn=function() rel(":cpanel:CPR_SEG2",nm) end}; t=t+0.6
  seq[#seq+1]={t=t,fn=function() M.video:snapshot(); emu.print_error("SNAP "..lbl) end}; t=t+0.7
end
for b=1,8 do add(names2[b],"bit"..(b-1).."="..names2[b]) end
seq[#seq+1]={t=t,fn=function() M:exit() end}
local i=1
emu.register_periodic(function() local now=M.time:as_double()
  while i<=#seq and now>=seq[i].t do seq[i].fn(); i=i+1 end end)
