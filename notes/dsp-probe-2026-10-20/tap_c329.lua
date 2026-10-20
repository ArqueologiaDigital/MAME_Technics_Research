-- tap_c329.lua -- who writes the effects DSP's DM 0xC329, the first receive channel's TCB index (II), in MAME?
-- On the chip (pass 7) it holds 0xC362, the value the firmware's kernel download puts there; in the overlay it
-- reads 0 by the time the probe runs. Prints every write to DM 0xC329 with the emulated time, the value and the
-- DSP's and the main CPU's PC and the DAG registers the ring-3 scrub stub uses (run with -nodrc for an exact DSP PC) (a write the host's download makes shows the main CPU inside it), for TAP_SECONDS (default 40) of a session, then exits.
local dsp = manager.machine.devices[":dsp"]
local dm = dsp.spaces["data"]
local n = 0
_G.TAPC329 = dm:install_write_tap(0xC329, 0xC329, "c329", function(offset, data, mask)
  n = n + 1
  if n <= 50 then
    local st = dsp.state
    local function r(n) return st[n] and st[n].value or -1 end
    emu.print_error(string.format("TAP t=%.4f DM %04X <- %08X  DSP PC %05X  main CPU PC %08X  I3 %X B3 %X L3 %X M7 %X I12 %X R4 %X R7 %X R8 %X",
      manager.machine.time:as_double(), offset, data, r("PC"), manager.machine.devices[":maincpu"].state["PC"].value,
      r("I3"), r("B3"), r("L3"), r("M7"), r("I12"), r("R4"), r("R7"), r("R8")))
    if data == 0 then   -- the host-patched unit CALL slots (PM 0x8080-0x80A0): which stub each one calls now
      local pm, t = dsp.spaces["program"], {}
      for a = 0x8080, 0x80A5 do
        local w = pm:read_u64(a) & 0xFFFFFFFFFFFF
        if (w >> 32) & 0xFFFF == 0x06BE then t[#t + 1] = string.format("%04X->%04X", a, w & 0xFFFF) end
      end
      emu.print_error("TAP   CALL slots: " .. table.concat(t, " "))
    end
  end
  return data
end)
local stop = tonumber(os.getenv("TAP_SECONDS") or "40")
_G.TAPEND = emu.add_machine_frame_notifier(function()
  if manager.machine.time:as_double() >= stop then
    emu.print_error(string.format("TAP end: %d writes to DM 0xC329; it holds %08X", n, dm:read_u32(0xC329)))
    manager.machine:exit()
  end
end)
