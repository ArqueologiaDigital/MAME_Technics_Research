-- Trigger the WSA1R DSP GROUP-SELECT path (link command 0x80) and measure whether it
-- uploads I-RAM that the per-effect sweep never did (WSA1R_ENABLE_DSP=1 build).
--
-- WHY: wsa1_dsp_effect_sweep.lua drove only Link_Ch1_WriteParamBlock subcmd 0x81/0x82/0x83
-- (effect PROGRAM per unit; change flag 0x7ECC bits 1/2/3) and concluded I-RAM is never
-- re-programmed at runtime.  It never issued subcmd 0x80/0x88 -- the STREAM-GROUP selector,
-- which writes (0xF361)=payload and sets 0x7ECC bit 0.  A group change makes
-- P7Units_ResolveProgramsAndReload copy 0xF361->0xF35D and, if it differs from shadow
-- 0xF35E, call P7Units_ReloadForGroup (0xFA3802), which re-issues command-01 I-RAM loads
-- (e.g. stream 0xFCD2C6 = a load-0x30 program).  This rig drives that path the same way the
-- sweep drove the effect path -- by writing the exact RAM CPU1's link handler writes -- and
-- diffs each DSP's I-RAM before/after.
--
-- RUN (needs a WSA1R_ENABLE_DSP=1 build):
--   ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \
--       -autoboot_script tools/rigs/wsa1_dsp_group_toggle.lua -seconds_to_run 120

local mac = manager.machine
local sp  = mac.devices[":cpu2"].spaces["program"]
local NAME = {[0]="IC6",[1]="IC5",[2]="IC30"}
local FG361, FECC, F35D, F35E = 0xF361, 0x7ECC, 0xF35D, 0xF35E

-- snapshot the set of nonzero I-RAM word addresses + distinct 40-bit words for a DSP
local function snap(d)
  local ir = mac.devices[":dsp"..d].spaces["iram"]
  local addrs, words = {}, {}
  for w=0,383 do
    local nz=false local s={}
    for k=0,4 do local b=ir:read_u8(w*5+k); s[k+1]=b; if b~=0 then nz=true end end
    if nz then addrs[w]=true; words[string.format("%02X%02X%02X%02X%02X",s[1],s[2],s[3],s[4],s[5])]=true end
  end
  return addrs, words
end
local function ncnt(t) local n=0 for _ in pairs(t) do n=n+1 end return n end
local function newaddrs(base,now)  -- word addresses nonzero NOW but not at base
  local out={} for w in pairs(now) do if not base[w] then out[#out+1]=w end end table.sort(out); return out
end
local function rangestr(list)
  if #list==0 then return "(none)" end
  local parts={} local a=list[1] local p=list[1]
  for i=2,#list do if list[i]~=p+1 then parts[#parts+1]=(a==p and tostring(a) or a.."-"..p); a=list[i] end p=list[i] end
  parts[#parts+1]=(a==p and tostring(a) or a.."-"..p)
  return table.concat(parts,",")
end

local base_a, base_w = {}, {}
local state, wait_to, step = "boot", 0, 0
_G._f = 0
_G._h = emu.add_machine_frame_notifier(function()
  _G._f = _G._f + 1
  if state=="boot" then
    if _G._f < 900 then return end
    for d=0,2 do base_a[d],base_w[d]=snap(d) end
    print(string.format("BASELINE  IC6 words=%d IRAMaddrs=%d | IC5 words=%d addrs=%d | IC30 words=%d addrs=%d",
      ncnt(base_w[0]),ncnt(base_a[0]), ncnt(base_w[1]),ncnt(base_a[1]), ncnt(base_w[2]),ncnt(base_a[2])))
    print(string.format("BASELINE  0xF361=%d 0xF35D=%d 0xF35E=%d",
      sp:read_u8(FG361), sp:read_u8(F35D), sp:read_u8(F35E)))
    state="toggle"
  elseif state=="toggle" then
    -- step 0..3: try group 1,0,1,0 ; and for later steps also nudge an effect first
    local cur = sp:read_u8(FG361)
    local newg = (cur==0) and 1 or 0
    if step==2 then  -- before the 3rd toggle, also select a non-default effect on IC30(unit2) and IC6(unit0)
      sp:write_u8(0x7EB2, 5); sp:write_u8(0x7E7E, 5)
      sp:write_u8(FECC, sp:read_u8(FECC) | 0x08 | 0x02)
    end
    sp:write_u8(FG361, newg)
    sp:write_u8(FECC, sp:read_u8(FECC) | 0x01)   -- change flag bit 0 = group
    print(string.format("[step %d] poke 0xF361 %d->%d, set 0x7ECC.0  (0x7ECC now 0x%02X)",
      step, cur, newg, sp:read_u8(FECC)))
    wait_to=_G._f+200; state="wait"
  elseif state=="wait" then
    if _G._f < wait_to then return end
    print(string.format("[step %d] after: 0xF35D=%d 0xF35E=%d", step, sp:read_u8(F35D), sp:read_u8(F35E)))
    for d=0,2 do
      local a,w = snap(d)
      local na = newaddrs(base_a[d], a)
      print(string.format("  %-4s I-RAM words %d->%d  NEW word-addrs: %s",
        NAME[d], ncnt(base_w[d]), ncnt(w), rangestr(na)))
    end
    step=step+1
    if step>3 then print("GROUP_TOGGLE DONE"); state="done"; return end
    state="toggle"
  end
end)
