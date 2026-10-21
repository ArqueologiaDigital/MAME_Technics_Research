-- g3_state.lua -- G3: does the effects DSP keep running after a save state is loaded in a new session?
-- Signal: DM 0xC003, where the panel reverb (unit 0, rec5x) stores I6 every frame; it changes every frame
-- while the kernel runs and stands still when it does not. Also the SHARC's PC.
--   G3_MODE=save : samples DM 0xC003 ten times over the second before G3_AT (control: it must move),
--                  saves state "g3" at G3_AT, exits one second later.
--   G3_MODE=load : run with -state g3; samples DM 0xC003 ten times over the first second after the load.
-- Prints one line "G3 <mode> t=<s> distinct=<n of 10> values=... pc=..." to stderr.
local mac = manager.machine
local dsp = mac.devices[":dsp"]
local dm = dsp.spaces["data"]
local mode = os.getenv("G3_MODE") or "save"
local at = tonumber(os.getenv("G3_AT") or "30")
local function now() return mac.time.seconds + mac.time.attoseconds / 1e18 end
local S = { vals = {}, pcs = {}, start = nil, saved = false }
_G.G3 = S
local function sample()
  S.vals[#S.vals + 1] = dm:read_u32(0xC003)
  S.pcs[#S.pcs + 1] = dsp.state["PC"].value
end
local function report(t)
  local seen, n = {}, 0
  for _, v in ipairs(S.vals) do if not seen[v] then seen[v] = true; n = n + 1 end end
  local vs, ps = {}, {}
  for i, v in ipairs(S.vals) do vs[i] = string.format("%X", v); ps[i] = string.format("%X", S.pcs[i]) end
  emu.print_error(string.format("G3 %s t=%.3f distinct=%d of %d values=%s pc=%s", mode, t, n, #S.vals,
    table.concat(vs, ","), table.concat(ps, ",")))
end
S.h = emu.register_periodic(function()
  local t = now()
  if mode == "save" then
    if t >= at - 1 and t < at and #S.vals < 10 and t >= (at - 1) + #S.vals * 0.1 then sample() end
    if t >= at and not S.saved then report(t); mac:save("g3"); S.saved = true end
    if t >= at + 1 then mac:exit() end
  else
    if not S.start then S.start = t end
    if #S.vals < 10 and t >= S.start + 0.05 + #S.vals * 0.1 then sample() end
    if #S.vals >= 10 then report(t); mac:exit() end
  end
end)
