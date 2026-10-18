-- kn6000_pres_insert.lua -- KN6000: does a feature-presentation floppy (ca6fp0N.img) load and
-- play when inserted on the DEMONSTRATION screen, as on the instrument ("press DEMO, then insert
-- the disk")?  Boots with no disk, presses DEMO (cpanel:CPL_SEG9 0x40) at t = 20 s, inserts the
-- image named by $PRES_IMG into :fdc:0:35hd at t = 24 s, then snapshots every 5 s for 60 s.
-- FORCE_DSKCHG=1 also forces the 82077 DIR disk-change bit (0x9802000E bit 7) clear after the
-- insert. Signal: the snapshots stop being identical (a presentation screen appears).
-- 2026-10-18: no change in either the overlay (kn7000-emulator) or the mame-pr build, with or
-- without FORCE_DSKCHG.
-- Run: kn7000 kn6000 -rompath ROMS -window -nothrottle -snapshot_directory OUT \
--        -autoboot_script kn6000_pres_insert.lua     (env PRES_IMG=/path/ca6fp01.img; use a copy)
local IMG = os.getenv("PRES_IMG")
local FORCE = os.getenv("FORCE_DSKCHG") == "1"
local phase, fc, shots = "boot", 0, 0
local function setbtn(p, mk, v)
  for _, f in pairs(manager.machine.ioport.ports[":" .. p].fields) do if f.mask == mk then f:set_value(v) end end
end
local function snap(l) shots = shots + 1; manager.machine.video:snapshot()
  print(string.format("SHOT %d t=%.1f %s", shots, manager.machine.time.seconds, l)) end
_G.p_sub = emu.add_machine_frame_notifier(function()
  local m = manager.machine; fc = fc + 1
  if phase == "boot" then
    if m.time.seconds >= 20 then setbtn("cpanel:CPL_SEG9", 0x40, 1); phase = "demo"; fc = 0 end
  elseif phase == "demo" then
    if fc == 30 then setbtn("cpanel:CPL_SEG9", 0x40, 0) end
    if fc >= 240 then snap("DEMO screen")
      print("LOAD " .. tostring(m.images[":fdc:0:35hd"]:load(IMG)))
      if FORCE then
        _G.dtap = m.devices[":maincpu"].spaces["program"]:install_read_tap(0x9802000c, 0x9802000f, "dskchg",
          function(off, data, mask) if (mask & 0x00ff0000) ~= 0 then return data & ~0x00800000 end end)
        print("DSKCHG forced clear")
      end
      phase = "run"; fc = 0 end
  elseif phase == "run" then
    if fc % 300 == 0 then snap("after insert") end
    if fc >= 3600 then m:exit() end
  end
end)
