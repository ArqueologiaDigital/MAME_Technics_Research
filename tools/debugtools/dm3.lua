-- dm3.lua -- DEBUG MODE effects 4 (APC SELECT wait-time window) and 5 (HELP page-number window),
-- plus a look at the SOUND menu for effects 1-2. DM_ON=1 sets DEBUG MODE ON (col 2 UP on DEBUG
-- TOOLS); DM_ON=0 opens DEBUG TOOLS but leaves it OFF (negative control).
-- Signals: u32 0x50007874/78/7C/80 = APC wait times (OFF/1st/2nd/more 3); u16 0x5009E726 = help page.
local R = dofile(os.getenv("RT_DIR") .. "/rt_lib.lua")
local L, LOG, P = R.L, R.LOG, R.P
local ON = os.getenv("DM_ON") == "1"

local function apc(tag)
  LOG(("[%s] APC waits u32 0x50007874=%d 0x50007878=%d 0x5000787C=%d 0x50007880=%d  %s"):format(tag,
      P:read_u32(0x50007874), P:read_u32(0x50007878), P:read_u32(0x5000787C), P:read_u32(0x50007880), R.screens()))
end
local function helpno(tag)
  LOG(("[%s] help page u16 0x5009E726=%d  %s"):format(tag, P:read_u16(0x5009E726), R.screens()))
end

local function main()
  R.settle()
  R.patch_gate()
  R.to_debug_tools("01")
  if ON then R.tap(2, 1) end
  R.dm(ON and "DM set ON" or "DM left OFF")
  R.press("EXIT (")
  L.waitf(180)

  -- effect 4: APC SELECT
  R.press("AUTO MODE")
  L.waitf(240)
  R.dm("after AUTO MODE")
  apc("APC SELECT")
  R.snap("02_apc_select.png")
  for _, c in ipairs({8, 9, 10, 11}) do R.tap(c, 1); apc(("col %d UP"):format(c)) end
  R.snap("03_apc_select_after_up.png")
  for _, c in ipairs({8, 9, 10, 11}) do R.tap(c, -1); apc(("col %d DOWN"):format(c)) end
  R.press("EXIT (")
  L.waitf(180)
  R.dm("after EXIT from APC SELECT")
  R.snap("04_after_apc_exit.png")

  -- effect 5: HELP text page
  R.press("HELP")
  L.waitf(240)
  R.press("LCDR 4")           -- OK on the language screen
  L.waitf(240)
  helpno("after OK")
  R.snap("05_help_after_ok.png")
  R.press("PROGRAM MENUS")    -- ask for help on a panel button
  L.waitf(300)
  helpno("help text for PROGRAM MENUS")
  R.snap("06_help_text.png")
  R.tap(16, 1); L.waitf(200)
  helpno("col 16 UP")
  R.snap("07_help_col16_up.png")
  R.tap(16, 1); L.waitf(200)
  helpno("col 16 UP again")
  R.tap(16, -1); L.waitf(200)
  helpno("col 16 DOWN")
  R.snap("08_help_col16_down.png")
  R.press("HELP")
  L.waitf(240)
  R.dm("after HELP off")

  -- SOUND menu (effects 1, 2 need its soft-key layout)
  R.press("PROGRAM MENUS")
  L.waitf(180)
  R.press("LCDL 1")
  L.waitf(240)
  R.dm("SOUND menu")
  R.snap("09_sound_menu.png")

  LOG("done")
  L.mach:exit()
end
L.run(main)
