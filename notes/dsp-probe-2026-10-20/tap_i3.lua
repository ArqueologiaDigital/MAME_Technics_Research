-- tap_i3.lua -- when does the DSP kernel's ring-3 pointer I3 leave its ring in MAME? (run with -nodrc)
-- The kernel writes IOSTAT (DM 0x2F) twice a frame: FLAG4 high at 0x807E as the frame starts, low at 0x809B as it
-- ends (rec04). A write tap there samples I3 at both points. Once B3 is set (0x656F0), I3 should stay in
-- [B3, B3 + L3) (L3 0x4650): on the chip MSGR2, a copy of I3, does. Prints the first samples where it does not, with
-- the PC, the frame count and the previous sample, then exits (or at TAP_SECONDS, default 5).
local dsp = manager.machine.devices[":dsp"]
local st = dsp.state
local function r(n) return st[n] and st[n].value or -1 end
local frames, prev, bad = 0, nil, 0
_G.TAPI3 = dsp.spaces["data"]:install_write_tap(0x2F, 0x2F, "iostat", function(offset, data, mask)
  frames = frames + 1
  local i3, b3, l3 = r("I3"), r("B3"), r("L3")
  local inring = b3 ~= 0 and i3 >= b3 and i3 < b3 + l3
  if b3 ~= 0 and not inring and bad < 6 then
    bad = bad + 1
    emu.print_error(string.format("I3TAP t=%.6f write %d (IOSTAT <- %X) PC %05X  I3 %X (prev sample %s)  B3 %X L3 %X M3 %X R4 %X",
      manager.machine.time:as_double(), frames, data, r("PC"), i3, prev and string.format("%X", prev) or "-", b3, l3, r("M3"), r("R4")))
  end
  prev = i3
  return data
end)
local stop = tonumber(os.getenv("TAP_SECONDS") or "5")
_G.TAPI3END = emu.add_machine_frame_notifier(function()
  if manager.machine.time:as_double() >= stop or bad >= 6 then
    emu.print_error(string.format("I3TAP end: %d IOSTAT writes, %d out-of-ring samples shown", frames, bad))
    manager.machine:exit()
  end
end)
