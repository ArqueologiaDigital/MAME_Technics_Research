-- Capture the ACTUAL C-RAM coefficient VALUES the firmware streams per effect, so the
-- statically-decoded coefficient ROLES can be checked against real fixed-point numbers.
-- (Static analysis could only see that coefficients are runtime data; this reads them.)
--
-- Effect selection is driven by UNIT 2 (IC30, the program DSP); that reload streams the
-- coefficients into IC6 (unit0) and IC5 (unit1), the coefficient DSPs.  So we sweep unit 2's
-- twin inbox + change flag (the exact bytes CPU1's link handler writes), wait for the live
-- program to catch up, and dump IC6/IC5 C-RAM as signed 24-bit values scaled to a fraction
-- (/2^23).  We print only when the RESOLVED RECORD changes, to dedup the 128->~55 map.
-- Record R corresponds to disasm/eff{R}.dsm (rec 4 = PARAMETRIC EQ, 26.. = reverbs, etc.).
--
-- MEASURED note (2026-09-09): the boot C-RAM of IC6 already shows Q0.23 coefficients in
-- [-1,1) laid out in 6-cell biquad groups (b1,b0,b2,-a1,-a2,makeup) with +/- pairs and a
-- recurring make-up term -- confirming the coefficient format and the 6-cell section (sect.15).
--
-- RUN (WSA1R_ENABLE_DSP=1):  ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \
--       -autoboot_script tools/rigs/wsa1_dsp_cram_values.lua -seconds_to_run 200

local mac = manager.machine
local sp  = mac.devices[":cpu2"].spaces["program"]
local TWIN2, FLAG2, LIVE2, REC2 = 0x7EB2, 0x08, 0x85A2, 0x85BA     -- UNIT 2 drives the reload
local function s24(v) v = v & 0xffffff; return (v >= 0x800000) and (v - 0x1000000) or v end
local function dump(dev)
  local cr = mac.devices[dev].spaces["cram"]
  local out = {}
  for x=0,255 do local v = cr:read_u32(x) & 0xffffff
    if v ~= 0 then out[#out+1] = string.format("%d:%.3f", x, s24(v)/8388608.0) end end
  return out
end

local PROGS = {}
for n=0,60 do PROGS[#PROGS+1]=n end
local seen = {}
local pi, st, wt, N = 1, "boot", 0, 0
_G._f = 0
_G._h = emu.add_machine_frame_notifier(function()
  _G._f = _G._f + 1
  if st=="boot" then if _G._f<900 then return end st="poke"; return end
  if st=="poke" then
    if pi>#PROGS then print("CRAM_VALUES DONE"); mac:exit(); return end
    N = PROGS[pi]
    sp:write_u8(TWIN2, N); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|FLAG2)
    wt=_G._f+300; st="wait"; return end
  if st=="wait" then
    if sp:read_u8(LIVE2)==N or _G._f>=wt then wt=_G._f+30; st="settle" end; return end
  if st=="settle" then
    if _G._f<wt then return end
    local rec = sp:read_u8(REC2)
    if not seen[rec] then
      seen[rec]=true
      local v6 = dump(":dsp0"); local v5 = dump(":dsp1")
      print(string.format("rec %3d (prog %3d)  IC6=%d IC5=%d | IC6: %s",
        rec, N, #v6, #v5, table.concat(v6," ")))
    end
    pi=pi+1; st="poke" end
end)
