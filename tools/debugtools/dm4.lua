-- dm4.lua -- DEBUG MODE effects 5 (HELP text page number window), 1 (PART SETTING), 2 (APC REVERB
-- SETTING) and a search for the button that opens APC SELECT (title 0xED, effect 4).
-- DM_ON=1: DEBUG MODE set ON with col 2 UP on DEBUG TOOLS; DM_ON=0: left OFF (negative control).
-- Signals: u16 0x5009E726 help page; u16 0x5006B5CE current part / u16 0x5006B5D0 part-list limit
-- (PART SETTING); u32 0x50007874..80 APC waits; title from u32 0x5000099C[1].
local R = dofile(os.getenv("RT_DIR") .. "/rt_lib.lua")
local L, LOG, P = R.L, R.LOG, R.P
local ON = os.getenv("DM_ON") == "1"
local function title() return P:read_u32(0x5000099C + 4) end
local function helpno(tag)
  LOG(("[%s] help page u16 0x5009E726=%d  %s"):format(tag, P:read_u16(0x5009E726), R.screens()))
end
local function part(tag)
  LOG(("[%s] part u16 0x5006B5CE=%d limit u16 0x5006B5D0=0x%X flag u32 0x5006B5C8=%d  %s"):format(tag,
      P:read_u16(0x5006B5CE), P:read_u16(0x5006B5D0), P:read_u32(0x5006B5C8), R.screens()))
end
local function apc(tag)
  LOG(("[%s] APC waits 0x50007874=%d 0x50007878=%d 0x5000787C=%d 0x50007880=%d  %s"):format(tag,
      P:read_u32(0x50007874), P:read_u32(0x50007878), P:read_u32(0x5000787C), P:read_u32(0x50007880), R.screens()))
end

local function main()
  R.settle()
  R.patch_gate()
  R.to_debug_tools("01")
  if ON then R.tap(2, 1) end
  R.dm(ON and "DM set ON" or "DM left OFF")
  R.press("EXIT (")
  L.waitf(180)

  -- B. HELP text page
  R.press("HELP"); L.waitf(240)
  R.press("LCDR 4"); L.waitf(240)            -- OK (English)
  R.press("PROGRAM MENUS"); L.waitf(300)      -- HELP : PROGRAM MENU (title 0x12D)
  R.press("LCDL 1"); L.waitf(300)             -- SOUND -> help text page?
  helpno("help text SOUND")
  R.snap("02_help_text.png")
  R.tap(16, 1); L.waitf(240); helpno("col 16 UP");  R.snap("03_help_col16_up.png")
  R.tap(16, 1); L.waitf(240); helpno("col 16 UP 2"); R.snap("04_help_col16_up2.png")
  R.tap(16, -1); L.waitf(240); helpno("col 16 DOWN")
  R.press("HELP"); L.waitf(240)
  LOG("after HELP off " .. R.screens())

  -- C. SOUND MENU > PART SETTING, APC REVERB SETTING
  R.press("PROGRAM MENUS"); L.waitf(180)
  R.press("LCDL 1"); L.waitf(240)             -- SOUND
  R.press("LCDL 1"); L.waitf(300)             -- PART SETTING
  part("PART SETTING")
  R.snap("05_part_setting.png")
  R.press("EXIT ("); L.waitf(240)
  R.press("LCDL 5"); L.waitf(300)             -- APC REVERB SETTING
  LOG("APC REVERB SETTING " .. R.screens())
  R.snap("06_apc_reverb.png")
  R.press("EXIT ("); L.waitf(240)
  R.press("PROGRAM MENUS"); L.waitf(240)
  LOG("back home? " .. R.screens())

  -- D. which button opens APC SELECT (0xED)?
  for _, b in ipairs({"AUTO MODE", "PLAY CHORD OFF/ON", "ARRANGER OFF/ON", "MUSIC STYLIST"}) do
    local t0 = title()
    R.hold(b, 40); L.waitf(240)
    local t1 = title()
    LOG(("button %s: title %08X -> %08X"):format(b, t0, t1))
    R.snap("07_btn_" .. b:gsub("[^%w]", "_") .. ".png")
    if t1 == 0x000F00ED then
      apc("APC SELECT open")
      for _, c in ipairs({8, 9, 10, 11}) do R.tap(c, 1); apc(("col %d UP"):format(c)) end
      R.snap("08_apc_select_after_up.png")
      for _, c in ipairs({8, 9, 10, 11}) do R.tap(c, -1); apc(("col %d DOWN"):format(c)) end
      break
    end
    if t1 ~= t0 then R.press("EXIT ("); L.waitf(240) end
  end

  LOG("done")
  L.mach:exit()
end
L.run(main)
