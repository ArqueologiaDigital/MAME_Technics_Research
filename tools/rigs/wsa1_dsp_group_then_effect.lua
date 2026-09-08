-- Decisive group-reload test: the resolve (P7Units_ResolveProgramsAndReload) that reads
-- 0xF361->0xF35D and calls P7Units_ReloadForGroup runs on an EFFECT-change flag, not on the
-- group bit alone.  So the faithful trigger is: set the group value (0xF361), THEN cause a
-- confirmed effect change.  When the resolve then finds 0xF35D != shadow 0xF35E it must call
-- ReloadForGroup and update 0xF35E -- so a flip of 0xF35E to the new group is proof the
-- reload path ran.  We watch that flip AND count I-RAM/C-RAM writes.
--
-- RUN (WSA1R_ENABLE_DSP=1):  ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \
--       -autoboot_script tools/rigs/wsa1_dsp_group_then_effect.lua -seconds_to_run 90

local mac=manager.machine
local sp=mac.devices[":cpu2"].spaces["program"]
local NAME={[0]="IC6",[1]="IC5",[2]="IC30"}
local LIVE={[0]=0x856E,[1]=0x8588,[2]=0x85A2}
local iw={[0]=0,[1]=0,[2]=0}; local cw={[0]=0,[1]=0,[2]=0}; local iad={[0]={},[1]={},[2]={}}
_G._t={}
for d=0,2 do
  local ir=mac.devices[":dsp"..d].spaces["iram"]
  _G._t[#_G._t+1]=ir:install_write_tap(0,ir.address_mask,"i"..d,function(o,dt) iw[d]=iw[d]+1;iad[d][o//5]=true;return dt end)
  local cr=mac.devices[":dsp"..d].spaces["cram"]
  _G._t[#_G._t+1]=cr:install_write_tap(0,cr.address_mask,"c"..d,function(o,dt) cw[d]=cw[d]+1;return dt end)
end
local function reset() for d=0,2 do iw[d]=0;cw[d]=0;iad[d]={} end end
local function rng(d) local a,b=1e9,-1 for w in pairs(iad[d]) do if w<a then a=w end if w>b then b=w end end return b<0 and "-" or (a.."-"..b) end
local function rep(tag) for d=0,2 do print(string.format("  %-12s %-4s I-RAM=%d(%s) C-RAM=%d",tag,NAME[d],iw[d],rng(d),cw[d])) end end

-- phases: set group value, then a confirmed effect change; twice (group 1 then 0)
local ph={
  {grp=1, eff=30}, {grp=0, eff=40},
}
local pi,st,wt,eN=1,"boot",0,0
_G._f=0
_G._h=emu.add_machine_frame_notifier(function()
  _G._f=_G._f+1
  if st=="boot" then if _G._f<900 then return end
    print(string.format("BOOT IC30 I-RAM=%d(%s)|IC6 C=%d IC5 C=%d|F361=%d F35D=%d F35E=%d",
      iw[2],rng(2),cw[0],cw[1],sp:read_u8(0xF361),sp:read_u8(0xF35D),sp:read_u8(0xF35E)))
    reset(); st="setgrp"; return end
  if st=="setgrp" then
    if pi>#ph then print("GROUP_THEN_EFFECT DONE"); mac:exit(); return end
    sp:write_u8(0xF361, ph[pi].grp); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x01)
    print(string.format("[phase %d] set F361=%d (+7ECC.0)", pi, ph[pi].grp))
    wt=_G._f+120; st="settle"; return end
  if st=="settle" then if _G._f<wt then return end
    reset(); eN=ph[pi].eff
    sp:write_u8(0x7EB2, eN); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x08)
    print(string.format("[phase %d] effect-change unit2 -> %d (invokes resolve)", pi, eN))
    wt=_G._f+500; st="wait"; return end
  if st=="wait" then
    local landed = sp:read_u8(LIVE[2])==eN
    if landed or _G._f>=wt then
      print(string.format("[phase %d] landed=%s  F361=%d F35D=%d F35E=%d  <- F35E flip => ReloadForGroup ran",
        pi, tostring(landed), sp:read_u8(0xF361), sp:read_u8(0xF35D), sp:read_u8(0xF35E)))
      rep("phase"..pi); reset(); pi=pi+1; st="setgrp" end
  end
end)
