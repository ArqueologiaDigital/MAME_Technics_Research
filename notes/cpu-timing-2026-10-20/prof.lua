-- prof.lua -- the timing model's counters over a run, and a snapshot every PROF_STEP seconds.
-- Prints one line per step to stderr:
--   PROF t=<s> insn=<TINSN> mem=<TMEM> icmiss=<TICMISS> dcmiss=<TDCMISS> pc=<PC>
-- (insn..dcmiss print as - on a binary without the timing model's counters). Quits at PROF_END.
--   PROF_STEP (default 1), PROF_END (default 30), PROF_SNAP=1 also saves a snapshot each step.
local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local STEP = tonumber(os.getenv("PROF_STEP")) or 1
local END = tonumber(os.getenv("PROF_END")) or 30
local SNAP = os.getenv("PROF_SNAP") == "1"
local function st(name)
  local e = cpu.state[name]
  return e and string.format("%d", e.value) or "-"
end
local next_t = STEP
_G.PROF = emu.add_machine_frame_notifier(function()
  local t = mac.time.seconds + mac.time.attoseconds / 1e18
  if t >= next_t then
    if SNAP then mac.video:snapshot() end
    emu.print_error(string.format("PROF t=%.3f insn=%s mem=%s icmiss=%s dcmiss=%s pc=%08X",
      t, st("TINSN"), st("TMEM"), st("TICMISS"), st("TDCMISS"), cpu.state["PC"].value))
    next_t = next_t + STEP
    if t >= END then mac:exit() end
  end
end)
