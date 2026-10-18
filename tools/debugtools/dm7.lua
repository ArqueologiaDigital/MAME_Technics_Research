-- dm7.lua -- does DEBUG MODE survive a reset?  Set it ON with the real toggle (col 2 UP on DEBUG
-- TOOLS), soft-reset the machine, and read u32 0x5015080C after the firmware has rebooted.
-- MAME re-runs the autoboot script after soft_reset(), so a global flag makes the second run only
-- log the post-reset state (append mode) instead of starting over.
if DM7_PHASE then
  -- second execution, after the soft reset
  local f = io.open(os.getenv("DG_OUT"), "a")
  local P = manager.machine.devices[":maincpu"].spaces["program"]
  local n = 0
  DM7_N2 = emu.add_machine_frame_notifier(function()
    n = n + 1
    if n == 60 * 30 then
      f:write(("after soft reset (+30 s, t=%.2f): DM u32 0x5015080C=%d sdpartFlag 0x5006B5C8=%d apcrev 0x500019FC=%d demo 0x50082948=%d gate 0x4840000F=%02X\n"):format(
        manager.machine.time.seconds, P:read_u32(0x5015080C), P:read_u32(0x5006B5C8), P:read_u8(0x500019FC),
        P:read_u32(0x50082948), P:read_u8(0x4840000F)))
      f:close()
      manager.machine.screens[":screen"]:snapshot("C3_after_reset.png")
    elseif n == 60 * 31 then
      manager.machine:exit()
    end
  end)
  return
end
DM7_PHASE = 1
local R = dofile(os.getenv("RT_DIR") .. "/rt_lib.lua")
local L, LOG, P = R.L, R.LOG, R.P
local function main()
  R.settle()
  R.patch_gate()
  R.to_debug_tools("C1")
  R.tap(2, 1)
  R.dm("C: DM ON via toggle")
  R.snap("C2_dm_on.png")
  LOG("C: soft reset now")
  L.logf:close(); L.logf = nil
  manager.machine:soft_reset()
end
L.run(main)
