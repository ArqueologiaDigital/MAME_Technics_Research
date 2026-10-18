-- dm2.lua -- DEBUG MODE effect 3 (EFFECT DEBUG behind the empty LCDL2 of REVERB & EFFECT) and the
-- start of the HELP route, with DEBUG MODE ON (DM_ON=1: col 2 UP on DEBUG TOOLS) or left OFF
-- (DM_ON=0: DEBUG TOOLS is opened the same way but the toggle is not touched) -- the negative control.
-- Question: does LCDL2 on REVERB & EFFECT open EFFECT DEBUG (title 0x3E) only when DEBUG MODE is ON?
local R = dofile(os.getenv("RT_DIR") .. "/rt_lib.lua")
local L, LOG = R.L, R.LOG
local ON = os.getenv("DM_ON") == "1"

local function main()
  R.settle()
  R.patch_gate()
  R.to_debug_tools("01")
  if ON then R.tap(2, 1) end
  R.dm(ON and "DM set ON" or "DM left OFF")
  R.snap("02_debug_tools_dm.png")

  R.press("EXIT (")
  L.waitf(180)
  R.dm("after EXIT")
  R.press("PROGRAM MENUS")
  L.waitf(180)
  R.press("LCDL 2")            -- PROGRAM MENUS: LCDL2 = REVERB & EFFECT
  L.waitf(240)
  R.dm("REVERB & EFFECT menu")
  R.snap("03_fxmenu.png")

  R.press("LCDL 2")            -- the blank left slot 2 (switch 0x91) on REVERB & EFFECT
  L.waitf(300)
  R.dm("after LCDL2 on REVERB & EFFECT")
  R.snap("04_after_lcdl2.png")

  R.press("EXIT (")
  L.waitf(240)
  R.dm("after EXIT from it")
  R.snap("05_after_exit.png")

  R.press("PROGRAM MENUS")     -- turn PROGRAM MENUS off again
  L.waitf(180)
  R.dm("PROGRAM MENUS off")
  R.snap("06_home.png")

  R.press("HELP")
  L.waitf(240)
  R.dm("after HELP")
  R.snap("07_help.png")

  LOG("done")
  L.mach:exit()
end
L.run(main)
