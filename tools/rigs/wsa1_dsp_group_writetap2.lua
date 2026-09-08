-- Rigorous write-tap probe: confirm each trigger LANDED (handshake) before counting DSP
-- writes.  Distinguishes "the path uploads nothing" from "my poke never fired".
--   effect change: wait until live program byte (0x856E+0x1A*unit) == poked value.
--   group change : wait until 0xF35D == poked 0xF361 (resolve ran) and note 0xF35E (shadow).
-- Counts I-RAM and C-RAM WRITE EVENTS per DSP for each confirmed trigger.
--
-- RUN (WSA1R_ENABLE_DSP=1):  ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \
--       -autoboot_script tools/rigs/wsa1_dsp_group_writetap2.lua -seconds_to_run 90

local mac = manager.machine
local sp  = mac.devices[":cpu2"].spaces["program"]
local NAME = {[0]="IC6",[1]="IC5",[2]="IC30"}
local LIVE = {[0]=0x856E,[1]=0x8588,[2]=0x85A2}
local iw={[0]=0,[1]=0,[2]=0}; local cw={[0]=0,[1]=0,[2]=0}; local iad={[0]={},[1]={},[2]={}}
_G._t={}
for d=0,2 do
  local ir=mac.devices[":dsp"..d].spaces["iram"]
  _G._t[#_G._t+1]=ir:install_write_tap(0,ir.address_mask,"i"..d,function(o,dt) iw[d]=iw[d]+1; iad[d][o//5]=true; return dt end)
  local cr=mac.devices[":dsp"..d].spaces["cram"]
  _G._t[#_G._t+1]=cr:install_write_tap(0,cr.address_mask,"c"..d,function(o,dt) cw[d]=cw[d]+1; return dt end)
end
local function reset() for d=0,2 do iw[d]=0;cw[d]=0;iad[d]={} end end
local function rng(d) local a,b=1e9,-1 for w in pairs(iad[d]) do if w<a then a=w end if w>b then b=w end end return b<0 and "-" or (a.."-"..b) end
local function rep(tag) for d=0,2 do print(string.format("  %-10s %-4s I-RAM=%d(%s) C-RAM=%d",tag,NAME[d],iw[d],rng(d),cw[d])) end end

-- steps: {name, fire(), landed()->bool}
local steps = {
  {"effch-u2->20", function() sp:write_u8(0x7EB2,20); sp:write_u8(0x7ECC,sp:read_u8(0x7ECC)|0x08) end,
                   function() return sp:read_u8(LIVE[2])==20 end},
  {"effch-u0->20", function() sp:write_u8(0x7E7E,20); sp:write_u8(0x7ECC,sp:read_u8(0x7ECC)|0x02) end,
                   function() return sp:read_u8(LIVE[0])==20 end},
  {"group->1",     function() sp:write_u8(0xF361,1); sp:write_u8(0x7ECC,sp:read_u8(0x7ECC)|0x01) end,
                   function() return sp:read_u8(0xF35D)==1 end},
  {"group->0",     function() sp:write_u8(0xF361,0); sp:write_u8(0x7ECC,sp:read_u8(0x7ECC)|0x01) end,
                   function() return sp:read_u8(0xF35D)==0 end},
}
local si,st,wt=1,"boot",0
_G._f=0
_G._h=emu.add_machine_frame_notifier(function()
  _G._f=_G._f+1
  if st=="boot" then if _G._f<900 then return end
    print(string.format("BOOT IC30 I-RAM=%d(%s) | IC6 C-RAM=%d IC5 C-RAM=%d | F361=%d F35D=%d F35E=%d",
      iw[2],rng(2),cw[0],cw[1],sp:read_u8(0xF361),sp:read_u8(0xF35D),sp:read_u8(0xF35E)))
    reset(); st="fire"; return end
  if st=="fire" then
    if si>#steps then print("WRITETAP2 DONE"); mac:exit(); return end
    steps[si][2](); wt=_G._f+400; st="wait"; return end
  if st=="wait" then
    local landed=steps[si][3]()
    if landed or _G._f>=wt then
      print(string.format("[%s] landed=%s (F35D=%d F35E=%d)", steps[si][1], tostring(landed),
        sp:read_u8(0xF35D), sp:read_u8(0xF35E)))
      rep(steps[si][1]); reset(); si=si+1; st="fire" end
  end
end)
