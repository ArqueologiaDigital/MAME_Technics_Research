local M = manager.machine
local ports = M.ioport.ports
local function field(porttag, name)
  local p = ports[porttag]; if not p then return nil end
  for k,f in pairs(p.fields) do if f.name==name then return f end end
  return nil
end
local function tap(tag,name) local f=field(tag,name); if f then f:set_value(1) end end
local function rel(tag,name) local f=field(tag,name); if f then f:set_value(0) end end

-- Probe every bit of the two SOUND GROUP segments. Stay on the SOUND screen so each
-- press just switches the header, which names the actually-fired sound group.
local names1 = {"ORGAN & ACCORDION","ORCHESTRAL PAD","SYNTH","BASS","DIGITAL DRAWBAR","ACCORDION REGISTER","GM SPECIAL","DRUM KITS"}
local names2 = {"PIANO","GUITAR","STRINGS & VOCAL","BRASS","FLUTE","SAX & REED","MALLET & ORCH PERC","WORLD PERC"}

local seq = {}
local t = 8.0
local function add(tag,name,label)
  seq[#seq+1] = {t=t, fn=function() tap(tag,name); emu.print_error("PRESS "..label) end}; t=t+0.4
  seq[#seq+1] = {t=t, fn=function() rel(tag,name) end}; t=t+0.5
  seq[#seq+1] = {t=t, fn=function() M.video:snapshot(); emu.print_error("SNAP "..label) end}; t=t+0.6
end
for b=1,8 do add(":cpanel:CPR_SEG2", names2[b], "SEG2.bit"..(b-1).."="..names2[b]) end
for b=1,8 do add(":cpanel:CPR_SEG1", names1[b], "SEG1.bit"..(b-1).."="..names1[b]) end
seq[#seq+1]={t=t, fn=function() emu.print_error("DONE"); M:exit() end}

local idx=1
emu.register_periodic(function()
  local now=M.time:as_double()
  while idx<=#seq and now>=seq[idx].t do seq[idx].fn(); idx=idx+1 end
end)
