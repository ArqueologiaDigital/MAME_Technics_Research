-- Focused: does changing IC30 (unit2) effect upload NEW I-RAM program words (corpus)?
-- Proper handshake: poke twin+flag, wait until live==N (or timeout), then snapshot.
local mac = manager.machine
local sp  = mac.devices[":cpu2"].spaces["program"]
local TWIN2,LIVE2,REC2,FLAG2 = 0x7EB2,0x85A2,0x85BA,0x08
local iwords={}
local function add() for d=0,2 do local ir=mac.devices[":dsp"..d].spaces["iram"]
  for w=0,383 do local nz=false local s={} for k=0,4 do local v=ir:read_u8(w*5+k); s[k+1]=v; if v~=0 then nz=true end end
    if nz then iwords[string.format("%02X%02X%02X%02X%02X",s[1],s[2],s[3],s[4],s[5])]=true end end end end
local function cnt(t) local n=0 for _ in pairs(t) do n=n+1 end return n end
local function inz(d) local ir=mac.devices[":dsp"..d].spaces["iram"]; local i=0
  for w=0,383 do for k=0,4 do if ir:read_u8(w*5+k)~=0 then i=i+1;break end end end return i end

local EFFS={5,9,13,20,30,40,50,1,8,60,70,80,90,100,110,120}
local i_eff=1
local state="boot"    -- boot -> (poke -> wait -> snap) loop -> done
local wait_to=0
_G._f=0
_G._h=emu.add_machine_frame_notifier(function()
  _G._f=_G._f+1
  if state=="boot" then
    if _G._f<900 then return end
    add(); print(string.format("BASELINE distinct-I=%d IC30 I=%d IC6 I=%d IC5 I=%d",cnt(iwords),inz(2),inz(0),inz(1)))
    state="poke"
  elseif state=="poke" then
    if i_eff>#EFFS then
      print(string.format("FINAL distinct-I=%d  (dumping words)",cnt(iwords)))
      local ks={} for k in pairs(iwords) do ks[#ks+1]=k end table.sort(ks)
      for _,k in ipairs(ks) do print("IWORD "..k) end
      print("U2 DONE"); state="done"; return
    end
    local n=EFFS[i_eff]; sp:write_u8(TWIN2,n); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|FLAG2)
    wait_to=_G._f+220; state="wait"
  elseif state=="wait" then
    local n=EFFS[i_eff]
    if sp:read_u8(LIVE2)==n or _G._f>=wait_to then
      -- settle a bit more then snapshot
      if _G._f>=wait_to or sp:read_u8(LIVE2)==n then
        add()
        print(string.format("u2 eff=%-3d -> live=%d rec=%d distinct-I=%d IC30 I=%d IC6 I=%d IC5 I=%d %s",
          n, sp:read_u8(LIVE2), sp:read_u8(REC2), cnt(iwords), inz(2), inz(0), inz(1),
          (sp:read_u8(LIVE2)~=n) and "(TIMEOUT)" or ""))
        i_eff=i_eff+1; state="settle"; wait_to=_G._f+40
      end
    end
  elseif state=="settle" then
    if _G._f>=wait_to then state="poke" end
  end
end)
