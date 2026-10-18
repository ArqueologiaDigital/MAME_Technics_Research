-- menu_shots.lua -- KN6000/KN6500: does text render on the play screen and on the first-level
-- menus?  Boots to t = BOOT s, saves a state, then for each button: load the state, snapshot
-- the baseline once, press the button for 90 frames, release, wait, snapshot.  Prints one
-- "SHOT n <label>" line per snapshot so the PNGs (snapshot dir/<set>/NNNN.png, in order) can
-- be matched to the screens.  Button ports/masks from kn7000-emulator/kn6000_btn_verify.lua.
local BOOT = tonumber(os.getenv("MS_BOOT") or "20")
local B = {
  {"cpanel:CPR_SEG6", 0x40, "PROGRAM-MENU"},
  {"cpanel:CPR_SEG0", 0x01, "SOUND-PIANO"},
  {"cpanel:CPL_SEG8", 0x08, "HELP"},
  {"cpanel:CPR_SEG6", 0x80, "DISK"},
  {"cpanel:CPL_SEG9", 0x40, "DEMO"},
  {"cpanel:CPL_SEG0", 0x08, "RHYTHM-POP"},
}
local shot = 0
local function snap(label) shot = shot + 1; manager.machine.video:snapshot(); print(string.format("SHOT %d %s", shot, label)) end
local function setbtn(p, mk, v)
  local port = manager.machine.ioport.ports[":" .. p]
  if not port then print("NO PORT " .. p) return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end
local i, phase, fc = 1, "boot", 0
_G.ms_sub = emu.add_machine_frame_notifier(function()
  local m = manager.machine; fc = fc + 1
  if phase == "boot" then
    if m.time.seconds >= BOOT then m:save("ms_home"); phase = "home"; fc = 0 end
  elseif phase == "home" then
    if fc >= 60 then snap("PLAY-SCREEN"); phase = "load"; fc = 0 end
  elseif phase == "load" then m:load("ms_home"); phase = "settle"; fc = 0
  elseif phase == "settle" then if fc >= 30 then setbtn(B[i][1], B[i][2], 1); phase = "hold"; fc = 0 end
  elseif phase == "hold" then
    if fc >= 90 then setbtn(B[i][1], B[i][2], 0); phase = "wait"; fc = 0 end
  elseif phase == "wait" then
    if fc >= 120 then snap(B[i][3]); i = i + 1
      if i > #B then m:exit() else phase = "load"; fc = 0 end end
  end
end)
