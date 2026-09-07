local mac=manager.machine; local sp=mac.devices[":cpu2"].spaces["program"]
local TWIN,LIVE,FLAG=0x7E7E,0x856E,0x02
local cvals={}; local iw={}
local function accum() local cr=mac.devices[":dsp0"].spaces["cram"]
  for x=0,255 do local v=cr:read_u32(x)&0xffffff; if v~=0 then cvals[v]=true end end
  local ir=mac.devices[":dsp0"].spaces["iram"]
  for w=0,383 do local nz=false local s={} for k=0,4 do local b=ir:read_u8(w*5+k);s[k+1]=b;if b~=0 then nz=true end end
   if nz then iw[string.format("%02X%02X%02X%02X%02X",s[1],s[2],s[3],s[4],s[5])]=true end end end
local function cnt(t) local n=0 for _ in pairs(t) do n=n+1 end return n end
local function cellnz() local cr=mac.devices[":dsp0"].spaces["cram"]; local c=0
  for x=0,255 do if (cr:read_u32(x)&0xffffff)~=0 then c=c+1 end end return c end
local EFFS={} for n=1,55 do EFFS[#EFFS+1]=n end   -- programs 1..55 cover all real records
local i,state,wto,bootC,bootcell=1,"boot",0,0,0
_G._f=0
_G._h=emu.add_machine_frame_notifier(function() _G._f=_G._f+1
  if state=="boot" then if _G._f<900 then return end
    accum(); bootC=cnt(cvals); bootcell=cellnz()
    print(string.format("BASELINE IC6 C-RAM distinct-values=%d cells=%d I-words=%d",bootC,bootcell,cnt(iw))); state="poke"
  elseif state=="poke" then
    if i>#EFFS then
      print(string.format("IC6 SWEEP: C-RAM distinct-values %d->%d (+%d), cells now=%d, I-words %d (unchanged=%s)",
        bootC,cnt(cvals),cnt(cvals)-bootC,cellnz(),cnt(iw), (cnt(iw)==0) and "yes(0)" or tostring(cnt(iw))))
      print("IC6FAST DONE"); state="done"; return end
    sp:write_u8(TWIN,EFFS[i]); sp:write_u8(0x7ECC,sp:read_u8(0x7ECC)|FLAG); wto=_G._f+45; state="wait"
  elseif state=="wait" then
    if sp:read_u8(LIVE)==EFFS[i] or _G._f>=wto then accum(); i=i+1; state="settle"; wto=_G._f+6 end
  elseif state=="settle" then if _G._f>=wto then state="poke" end end
end)
