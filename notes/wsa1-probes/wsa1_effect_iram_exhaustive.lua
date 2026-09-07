-- Exhaustive: sweep unit2 (IC30) program 0..127; for each resolved record, does IC30
-- I-RAM change?  Track the union of distinct I-RAM words; report every time it grows
-- and every NEW resolved record.  Airtight test of "effects exercise the I-RAM corpus".
local mac=manager.machine
local sp=mac.devices[":cpu2"].spaces["program"]
local TWIN2,LIVE2,REC2,FLAG2=0x7EB2,0x85A2,0x85BA,0x08
local iwords={}; local seenrec={}
local function add() local grew=false
  for d=0,2 do local ir=mac.devices[":dsp"..d].spaces["iram"]
   for w=0,383 do local nz=false local s={} for k=0,4 do local v=ir:read_u8(w*5+k);s[k+1]=v;if v~=0 then nz=true end end
    if nz then local key=string.format("%02X%02X%02X%02X%02X",s[1],s[2],s[3],s[4],s[5])
      if not iwords[key] then iwords[key]=true; grew=true end end end end
  return grew end
local function cnt(t) local n=0 for _ in pairs(t) do n=n+1 end return n end
local function inz(d) local ir=mac.devices[":dsp"..d].spaces["iram"];local i=0
  for w=0,383 do for k=0,4 do if ir:read_u8(w*5+k)~=0 then i=i+1;break end end end return i end

local N=0; local state="boot"; local wait_to=0; local nrec=0
_G._f=0
_G._h=emu.add_machine_frame_notifier(function()
  _G._f=_G._f+1
  if state=="boot" then
    if _G._f<900 then return end
    add(); print(string.format("BASELINE distinct-I=%d IC30 I=%d",cnt(iwords),inz(2))); state="poke"
  elseif state=="poke" then
    if N>127 then
      print(string.format("SWEEP COMPLETE: distinct real records=%d, distinct I-RAM words=%d (baseline was 45), IC30 I=%d",nrec,cnt(iwords),inz(2)))
      print("EXH DONE"); state="done"; return
    end
    sp:write_u8(TWIN2,N); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|FLAG2); wait_to=_G._f+120; state="wait"
  elseif state=="wait" then
    if sp:read_u8(LIVE2)==N or _G._f>=wait_to then
      local rec=sp:read_u8(REC2); local grew=add()
      if rec~=53 and not seenrec[rec] then seenrec[rec]=true; nrec=nrec+1
        print(string.format("N=%-3d rec=%-3d (NEW real record #%d)  distinct-I=%d %s", N,rec,nrec,cnt(iwords), grew and "*** I-RAM GREW" or "")) end
      if grew and rec==53 then print(string.format("N=%-3d rec=53 but I-RAM GREW?! distinct-I=%d",N,cnt(iwords))) end
      N=N+1; state="settle"; wait_to=_G._f+25
    end
  elseif state=="settle" then if _G._f>=wait_to then state="poke" end end
end)
