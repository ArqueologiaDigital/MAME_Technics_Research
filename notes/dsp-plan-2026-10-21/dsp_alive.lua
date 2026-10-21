-- dsp_alive.lua -- is the effects DSP's kernel running on this machine, and at what frame rate?
-- Counts the kernel's IOSTAT writes (DM 0x2F; rec04 writes it twice a frame: FLAG4 high at frame start,
-- low at frame end) over one second of emulated time starting at ALIVE_AT (default 30), and samples
-- the SHARC's PC. A running kernel gives about 88,200 writes a second (2 x 44,100); a SHARC still
-- halted in host boot gives 0. Prints one line "ALIVE <machine> ..." to stderr and exits.
local mac = manager.machine
local dsp = mac.devices[":dsp"]
local at = tonumber(os.getenv("ALIVE_AT") or "30")
local function now() return mac.time.seconds + mac.time.attoseconds / 1e18 end
local S = { n = 0, counting = false, pcs = {}, done = false }
_G.ALIVE = S
S.tap = dsp.spaces["data"]:install_write_tap(0x2F, 0x2F, "alive_iostat", function(o, d, m)
  if S.counting then S.n = S.n + 1 end
  return d
end)
S.h = emu.register_periodic(function()
  local t = now()
  if not S.counting and not S.done and t >= at then S.counting = true; S.t0 = t end
  if S.counting and #S.pcs < 8 and t >= S.t0 + #S.pcs * 0.125 then
    S.pcs[#S.pcs + 1] = string.format("%X", dsp.state["PC"].value)
  end
  if S.counting and t >= S.t0 + 1.0 then
    S.counting = false; S.done = true
    emu.print_error(string.format("ALIVE %s t0=%.3f t1=%.3f iostat_writes=%d per_s=%.1f pc=%s",
      mac.system.name, S.t0, t, S.n, S.n / (t - S.t0), table.concat(S.pcs, ",")))
    mac:exit()
  end
end)
