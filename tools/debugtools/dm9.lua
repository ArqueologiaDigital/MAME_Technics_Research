-- dm9.lua -- who zeroes DEBUG MODE (u32 0x5015080C) on a reset: the firmware or MAME?
-- DEBUG MODE is set ON with the real toggle (col 2 UP on DEBUG TOOLS); a write tap on
-- 0x5015080C..0x5015080F logs every write with the CPU PC; then soft_reset(). If the zero comes
-- from the crt0 .bss clear loop (0x48410027..0x4841003C) the firmware clears it at every boot.
-- MAME re-runs the autoboot script after soft_reset(); a global flag turns the second run into a
-- 30 s wait + final read (append mode).
if DM9_PHASE then
  local f = io.open(os.getenv("DG_OUT"), "a")
  local P = manager.machine.devices[":maincpu"].spaces["program"]
  local n = 0
  DM9_N2 = emu.add_machine_frame_notifier(function()
    n = n + 1
    if n == 60 * 30 then
      f:write(("after soft reset (+30 s, t=%.2f): DM u32 0x5015080C=%d; writes seen by the tap: %d\n"):format(
        manager.machine.time.seconds, P:read_u32(0x5015080C), DM9_WRITES or -1))
      f:close()
    elseif n == 60 * 31 then
      manager.machine:exit()
    end
  end)
  return
end
DM9_PHASE = 1
local R = dofile(os.getenv("RT_DIR") .. "/rt_lib.lua")
local L, LOG, P = R.L, R.LOG, R.P
local cpu = manager.machine.devices[":maincpu"]
DM9_WRITES = 0
local function main()
  R.settle()
  R.patch_gate()
  R.to_debug_tools("C1")
  DM9_TAP = P:install_write_tap(0x5015080C, 0x5015080F, "dm9tap", function(offset, data, mask)
    DM9_WRITES = DM9_WRITES + 1
    if DM9_WRITES <= 20 then
      local s = ("TAP write 0x%08X data %08X mask %08X pc %08X t=%.4f"):format(offset, data, mask,
          cpu.state["PC"].value, manager.machine.time.seconds)
      local f = io.open(os.getenv("DG_OUT"), "a"); f:write(s .. "\n"); f:close()
    end
  end)
  R.tap(2, 1)
  R.dm("C: DM ON via toggle")
  LOG("C: soft reset now")
  L.logf:close(); L.logf = nil
  manager.machine:soft_reset()
end
L.run(main)
