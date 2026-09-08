-- Write-tap version of the group-select probe: count I-RAM and C-RAM WRITE EVENTS per DSP
-- during (a) an effect change and (b) a group toggle, so a re-upload of IDENTICAL data is
-- visible (the state-diff rig wsa1_dsp_group_toggle.lua cannot see identical re-writes).
--
-- Boot writes the kernel to IC30 words 48..110 (load 0x30..0x6E).  Bodies, if uploaded,
-- would write words >110.  This measures whether either trigger emits ANY I-RAM writes.
--
-- RUN (WSA1R_ENABLE_DSP=1 build):
--   ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \
--       -autoboot_script tools/rigs/wsa1_dsp_group_writetap.lua -seconds_to_run 60

local mac = manager.machine
local sp  = mac.devices[":cpu2"].spaces["program"]
local NAME = {[0]="IC6",[1]="IC5",[2]="IC30"}
local iw = {[0]=0,[1]=0,[2]=0}     -- I-RAM write count
local cw = {[0]=0,[1]=0,[2]=0}     -- C-RAM write count
local iaddr = {[0]={},[1]={},[2]={}}
_G._taps = {}
for d=0,2 do
  local ir = mac.devices[":dsp"..d].spaces["iram"]
  _G._taps[#_G._taps+1] = ir:install_write_tap(0, ir.address_mask, "iw"..d, function(off,data,mask)
    iw[d]=iw[d]+1; iaddr[d][off//5]=true; return data end)
  local cr = mac.devices[":dsp"..d].spaces["cram"]
  _G._taps[#_G._taps+1] = cr:install_write_tap(0, cr.address_mask, "cw"..d, function(off,data,mask)
    cw[d]=cw[d]+1; return data end)
end
local function reset() for d=0,2 do iw[d]=0;cw[d]=0;iaddr[d]={} end end
local function rng(d) local mn,mx=1e9,-1 for w in pairs(iaddr[d]) do if w<mn then mn=w end if w>mx then mx=w end end
  return (mx<0) and "-" or (mn.."-"..mx) end
local function report(tag)
  for d=0,2 do print(string.format("  %-6s %-4s: I-RAM writes=%-5d (words %s)  C-RAM writes=%d",
    tag, NAME[d], iw[d], rng(d), cw[d])) end
end

local FG361,FECC = 0xF361,0x7ECC
local seq = {
  {"effch-u2", function() sp:write_u8(0x7EB2, 7); sp:write_u8(FECC, sp:read_u8(FECC)|0x08) end},
  {"effch-u0", function() sp:write_u8(0x7E7E, 7); sp:write_u8(FECC, sp:read_u8(FECC)|0x02) end},
  {"group->1", function() sp:write_u8(FG361,1); sp:write_u8(FECC, sp:read_u8(FECC)|0x01) end},
  {"group->0", function() sp:write_u8(FG361,0); sp:write_u8(FECC, sp:read_u8(FECC)|0x01) end},
  {"grp1+eff", function() sp:write_u8(0x7EB2,9); sp:write_u8(FG361,1); sp:write_u8(FECC, sp:read_u8(FECC)|0x09) end},
}
local si, state, wait_to = 1, "boot", 0
_G._f=0
_G._h = emu.add_machine_frame_notifier(function()
  _G._f=_G._f+1
  if state=="boot" then
    if _G._f<900 then return end
    print(string.format("BOOT: IC30 I-RAM writes=%d (words %s) C-RAM=%d | IC6 C-RAM=%d | IC5 C-RAM=%d",
      iw[2], rng(2), cw[2], cw[0], cw[1]))
    print(string.format("BOOT: 0xF361=%d 0xF35D=%d", sp:read_u8(FG361), sp:read_u8(0xF35D)))
    reset(); state="fire"
  elseif state=="fire" then
    if si>#seq then print("WRITETAP DONE"); mac:exit(); return end
    print(string.format("[%s] firing (0xF361=%d)", seq[si][1], sp:read_u8(FG361)))
    seq[si][2]()
    wait_to=_G._f+250; state="wait"
  elseif state=="wait" then
    if _G._f<wait_to then return end
    report(seq[si][1])
    reset(); si=si+1; state="fire"
  end
end)
