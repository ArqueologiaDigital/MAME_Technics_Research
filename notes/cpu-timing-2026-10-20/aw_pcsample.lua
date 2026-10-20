-- aw_pcsample.lua -- where the main CPU's time goes while Another World runs (KN7APP.BIN through the loader).
-- Runs Another World's own speed script (AW_SPEED_LUA: kn5000-anotherworld kn7000/probes/cnv/awcnv_speed.lua)
-- and, once per video frame, samples the PC; every emulated second it prints one line:
--   awpc: t=<s> game=<samples in the converter area 0x502B8000-0x502E7FFF> fw=<program flash>
--         lib=<library 0x4C...> other=<rest> insn=<TINSN per s> mem=<TMEM quarter cycles per s>
-- (insn and mem read - on a binary without the timing model's counters). Run with run_perf.sh in place of
-- awcnv_speed.lua: probes/cnv/run_perf.sh OUT <this file>, with AW_SPEED_LUA set.
local M = manager.machine
local cpu = M.devices[":maincpu"]
dofile(assert(os.getenv("AW_SPEED_LUA"), "set AW_SPEED_LUA"))
local function st(n) local e = cpu.state[n]; return e and e.value or nil end
local bins = {game = 0, fw = 0, lib = 0, other = 0}
local next_t, last_i, last_m = 1, st("TINSN"), st("TMEM")
_G.AWPC = emu.add_machine_frame_notifier(function()
  local pc = cpu.state["PC"].value
  local k = (pc >= 0x502B8000 and pc < 0x502E8000) and "game" or (pc >= 0x48400000 and pc < 0x48800000) and "fw"
    or (pc >= 0x4C000000 and pc < 0x4D000000) and "lib" or "other"
  bins[k] = bins[k] + 1
  local t = M.time:as_double()
  if t >= next_t then
    local i, m = st("TINSN"), st("TMEM")
    emu.print_error(string.format("awpc: t=%d game=%d fw=%d lib=%d other=%d insn=%s mem=%s", next_t, bins.game, bins.fw,
      bins.lib, bins.other, i and tostring(i - last_i) or "-", m and tostring(m - last_m) or "-"))
    last_i, last_m = i, m
    bins = {game = 0, fw = 0, lib = 0, other = 0}
    next_t = next_t + 1
  end
end)
