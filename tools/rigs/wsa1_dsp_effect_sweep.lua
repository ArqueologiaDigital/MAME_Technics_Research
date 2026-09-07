-- Sweep the WSA1R DSP effects at runtime and measure how much of each DSP's on-chip
-- memory the effect set exercises (WSA1R_ENABLE_DSP=1 build).
--
-- QUESTION THIS ANSWERS: does selecting each effect at runtime fill more of the three
-- uPD6383GF DSPs' I-RAM (microcode) and C-RAM (coefficients) than the boot load alone?
--
-- HOW IT DRIVES EFFECTS (deterministic, no menu navigation): each unit's effect is
-- byte +0 of its CPU-2 unit block; CPU 1 delivers it over link channel 1 into the
-- "twin" inbox, and P7Units_ServiceTask resolves+reloads on a change flag.  This rig
-- writes the twin program byte and sets the change flag directly -- the exact RAM
-- CPU 1's link handler writes (Link_Ch1_WriteParamBlock subcmd 0x81/0x82/0x83), so the
-- ensuing upload is 100% real firmware (P7Stream_Run).  Addresses (prom_c, MEASURED,
-- wf_6046d59e-9fc): twin 0x7E7E/0x7E98/0x7EB2 (+0x1A*unit), change flag 0x7ECC
-- (bit 1<<(unit+1)), live program 0x856E/0x8588/0x85A2, resolved record 0x8586/0x85A0/0x85BA.
--
-- WHAT IT MEASURES: per DSP, the UNION of distinct C-RAM 24-bit coefficient values and
-- distinct I-RAM 40-bit words seen across the whole effect sweep, vs the boot baseline.
--
-- MEASURED 2026-09-07 (this rig + exhaustive 0..127 sweep):
--   * BOOT split of the three DSPs' roles is fixed: IC30 = the PROGRAM DSP (I-RAM
--     kernel, 63 words / 45 distinct; C-RAM empty); IC6 / IC5 = COEFFICIENT DSPs
--     (C-RAM 79 / 54 cells; no I-RAM).
--   * Sweeping IC6 (unit0) across the 55 real effects grows its C-RAM from 37 -> 47
--     distinct 24-bit values (79 -> 91 cells) -- effect selection DOES re-upload
--     coefficients.  IC5 behaves the same way.
--   * Sweeping IC30 (unit2) across ALL 128 programs (55 distinct resolved records)
--     changes NEITHER its I-RAM (stays 45 distinct words) NOR its C-RAM (stays 0).
--   * I-RAM is BYTE-IDENTICAL on all three DSPs across every effect, every group
--     reload, every combi, and a preamble-latch clear.
-- => Runtime effect selection is COEFFICIENT-DRIVEN.  The I-RAM microprogram is a
--    single resident kernel and is NOT re-programmed per effect, so effect selection
--    fills more C-RAM but does NOT exercise more of the 918-word static I-RAM corpus.
--    Only 45 distinct I-RAM words are ever resident at runtime; this REFUTES the note
--    that "the rest of IC30's I-RAM loads when effects are selected".
--
-- RUN (needs a WSA1R_ENABLE_DSP=1 build):
--   ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \
--       -autoboot_script tools/rigs/wsa1_dsp_effect_sweep.lua -seconds_to_run 150

local mac  = manager.machine
local sp   = mac.devices[":cpu2"].spaces["program"]
local TWIN = {[0]=0x7E7E,[1]=0x7E98,[2]=0x7EB2}
local LIVE = {[0]=0x856E,[1]=0x8588,[2]=0x85A2}
local REC  = {[0]=0x8586,[1]=0x85A0,[2]=0x85BA}
local FLAG = {[0]=0x02,   [1]=0x04,   [2]=0x08}
local NAME = {[0]="IC6",  [1]="IC5",  [2]="IC30"}

-- per-DSP coverage sets
local cvals = {[0]={},[1]={},[2]={}}   -- distinct C-RAM 24-bit values
local iwords= {[0]={},[1]={},[2]={}}   -- distinct I-RAM 40-bit words
local function accum(d)
  local cr = mac.devices[":dsp"..d].spaces["cram"]
  for x=0,255 do local v=cr:read_u32(x)&0xffffff; if v~=0 then cvals[d][v]=true end end
  local ir = mac.devices[":dsp"..d].spaces["iram"]
  for w=0,383 do local nz=false local s={} for k=0,4 do local b=ir:read_u8(w*5+k); s[k+1]=b; if b~=0 then nz=true end end
    if nz then iwords[d][string.format("%02X%02X%02X%02X%02X",s[1],s[2],s[3],s[4],s[5])]=true end end
end
local function cnt(t) local n=0 for _ in pairs(t) do n=n+1 end return n end

local UNITS = {2,0,1}          -- IC30 first (the program DSP), then IC6, IC5
local ui, N = 1, 0
local state, wait_to = "boot", 0
local bootC, bootI = {}, {}

_G._f = 0
_G._h = emu.add_machine_frame_notifier(function()
  _G._f = _G._f + 1
  if state == "boot" then
    if _G._f < 900 then return end
    for d=0,2 do accum(d) end
    for d=0,2 do bootC[d]=cnt(cvals[d]); bootI[d]=cnt(iwords[d]) end
    print(string.format("BASELINE  IC6 C=%d I=%d | IC5 C=%d I=%d | IC30 C=%d I=%d",
      bootC[0],bootI[0], bootC[1],bootI[1], bootC[2],bootI[2]))
    state = "poke"
  elseif state == "poke" then
    if N > 127 then
      local u = UNITS[ui]
      print(string.format("UNIT %s done: C-RAM distinct %d->%d (+%d), I-RAM distinct %d->%d (+%d)",
        NAME[u], bootC[u], cnt(cvals[u]), cnt(cvals[u])-bootC[u], bootI[u], cnt(iwords[u]), cnt(iwords[u])-bootI[u]))
      ui = ui + 1; N = 0
      if ui > #UNITS then
        print("=== SWEEP COMPLETE ===")
        for _,d in ipairs({0,1,2}) do
          print(string.format("%-4s  C-RAM distinct values: boot %d -> swept %d   I-RAM distinct words: boot %d -> swept %d",
            NAME[d], bootC[d], cnt(cvals[d]), bootI[d], cnt(iwords[d]))) end
        print("EFFECT_SWEEP DONE"); state="done"; return
      end
    end
    local u = UNITS[ui]
    sp:write_u8(TWIN[u], N); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC) | FLAG[u])
    wait_to = _G._f + 100; state = "wait"
  elseif state == "wait" then
    local u = UNITS[ui]
    if sp:read_u8(LIVE[u]) == N or _G._f >= wait_to then
      accum(u); N = N + 1; state = "settle"; wait_to = _G._f + 12
    end
  elseif state == "settle" then
    if _G._f >= wait_to then state = "poke" end
  end
end)
