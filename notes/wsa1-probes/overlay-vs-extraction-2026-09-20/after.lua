local OUT = os.getenv("PCSLOG") or "/tmp/after.log"
local logf = io.open(OUT, "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local c1 = mach.devices[":cpu1"]
local sp1 = c1.spaces["program"]
local dispon = nil
local seen = {}
_G._wt = sp1:install_write_tap(0x790000, 0x790001, "lcdcmd", function(offset, data, mask)
  if offset == 0x790001 and (data & 0xff) == 0x59 and not dispon then
    dispon = mach.time.as_double()
    LOG(string.format("DISP ON at t=%.5f  (PC %06X)", dispon, c1.state["CURPC"].value))
  end
  return data
end)
local marks = {[0xF8E671]="Link_WaitBlockDone", [0xF5AA97]="SC1_WaitTicks51", [0xF5AA80]="SC1_WaitTicks6",
               [0xF8E086]="Link_SendCountedBlock_P7wait", [0xF8E0E8]="Link_SendCountedBlock_DMAspin",
               [0xF8E0BC]="Link_SendCountedBlock_P7wait2"}
_G._af = emu.add_machine_frame_notifier(function()
  local pc = c1.state["CURPC"].value
  if marks[pc] and not seen[pc] then
    seen[pc] = true
    LOG(string.format("first hit %s (%06X) at t=%.5f  (after DISP ON: %s)", marks[pc], pc, mach.time.as_double(),
      dispon and "yes" or "NO -- before"))
  end
  if mach.time.seconds >= 12 and not _G._d then _G._d = true; LOG("DONE") end
end)
LOG("after armed")
