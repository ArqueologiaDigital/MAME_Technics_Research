-- dm1.lua -- DEBUG MODE toggle test on DEBUG TOOLS (kn7000, PROGRAM 941, gate byte poked to 0xFF).
-- Question: which balance column/direction changes u32 0x5015080C, do the companion cells the static
-- lane names (0x5006B5C8, 0x500017C0, 0x500019FC, 0x50082948) follow, and what does EXIT lead to?
-- Then PROGRAM MENUS is opened (DM still ON) to find the REVERB & EFFECT soft key for later runs.
local R = dofile(os.getenv("RT_DIR") .. "/rt_lib.lua")
local L, LOG = R.L, R.LOG

local function main()
  R.settle()
  R.snap("00_home.png")
  R.dm("home")
  R.patch_gate()
  R.to_debug_tools("01")

  local trials = {
    {1, 1, "col1 UP (expect no change)"},
    {4, 1, "col4 UP (expect no change)"},
    {2, 1, "col2 UP (expect ON)"},
    {2, 1, "col2 UP again (expect still ON)"},
    {2, -1, "col2 DOWN (expect OFF)"},
    {3, 1, "col3 UP (expect ON)"},
    {3, -1, "col3 DOWN (expect OFF)"},
    {2, 1, "col2 UP (expect ON, final)"},
  }
  for i, t in ipairs(trials) do
    R.tap(t[1], t[2])
    R.dm(("trial %d: %s"):format(i, t[3]))
    if i == 3 then R.snap("02_dm_on.png") end
    if i == 5 then R.snap("03_dm_off.png") end
  end
  R.snap("04_dm_on_final.png")

  R.press("EXIT (")
  L.waitf(180)
  R.dm("after EXIT")
  R.snap("05_after_exit.png")

  R.press("PROGRAM MENUS")
  L.waitf(180)
  R.dm("after PROGRAM MENUS")
  R.snap("06_program_menus.png")

  LOG("done")
  L.mach:exit()
end
L.run(main)
