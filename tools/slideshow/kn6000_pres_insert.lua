-- kn6000_pres_insert.lua -- KN6000: does a feature-presentation floppy (ca6fp0N.img) load and
-- play when inserted on the DEMONSTRATION screen, as on the instrument ("press DEMO, then insert
-- the disk")?  Boots with no disk, presses DEMO (cpanel:CPL_SEG9 0x40) at t = 20 s, inserts the
-- image named by $PRES_IMG into :fdc:0:35hd at t = 24 s, then snapshots every 5 s for 60 s.
-- FORCE_DSKCHG=1 also forces the 82077 DIR disk-change bit (0x9802000E bit 7) clear after the
-- insert. Signal: the snapshots stop being identical (a presentation screen appears).
-- 2026-10-18: no change in either the overlay (kn7000-emulator) or the mame-pr build, with or
-- without FORCE_DSKCHG. Later on 2026-10-18 the rig also logs the firmware's view of the drive:
--   STATE  writes to 0x50004AB8, the KN6000 disk monitor's state (0xFF unknown, 0 empty, 1 disk in;
--          0x4851299D posts the disk-in event 0x10708000 on the 0 -> 1 step);
--   INDEX  the first few INDEX-ISR stamps (0x48512866 sets byte 0x50005B4C = 1 per group-0x1E IRQ);
--   DMA    a count of DMA channel-0 starts (writes to 0x32000800 with low nibble 0xF), i.e. sector
--          transfers; printed with each snapshot.
-- PRES_RUN (default 60) sets how many seconds (60 frames each) to run after the insert; 0 = keep
-- running until the window is closed. PRES_SNAP=0 takes no snapshots. For watching it by hand:
--   PRES_RUN=0 PRES_SNAP=0 PRES_IMG=... ./run.sh kn6000 -window -autoboot_script kn6000_pres_insert.lua
-- Run: kn7000 kn6000 -rompath ROMS -window -nothrottle -snapshot_directory OUT \
--        -autoboot_script kn6000_pres_insert.lua     (env PRES_IMG=/path/ca6fp01.img; use a copy)
local IMG = os.getenv("PRES_IMG")
local FORCE = os.getenv("FORCE_DSKCHG") == "1"
local RUN = tonumber(os.getenv("PRES_RUN") or "60")     -- seconds to keep running after the insert
local SNAP = os.getenv("PRES_SNAP") ~= "0"
-- PRES_PRESS="secs:PORT:MASK,..." presses cpanel PORT bit MASK for 0.5 s at secs after the insert,
-- e.g. "60:CPR_SEG3:0x40,90:CPR_SEG6:0x08" = LCDR 5 (the presentation's title button), START/STOP
local PRESSES = {}
for t, p, mk in (os.getenv("PRES_PRESS") or ""):gmatch("([%d.]+):([%w_]+):(0?x?%x+)") do
  PRESSES[#PRESSES + 1] = { at = tonumber(t) * 60, port = "cpanel:" .. p, mask = tonumber(mk) }
end
local phase, fc, shots = "boot", 0, 0
local dma_starts, index_seen = 0, 0
local sp = manager.machine.devices[":maincpu"].spaces["program"]
_G.t_state = sp:install_write_tap(0x50004ab8, 0x50004abb, "state", function(off, data, mask)
  if (mask & 0xff) ~= 0 then
    print(string.format("STATE t=%.2f 0x50004AB8 <- %02X", manager.machine.time.seconds, data & 0xff)) end end)
_G.t_index = sp:install_write_tap(0x50005b4c, 0x50005b4f, "index", function(off, data, mask)
  if (mask & 0xff) ~= 0 and (data & 0xff) == 1 then index_seen = index_seen + 1
    if index_seen <= 3 then print(string.format("INDEX t=%.2f isr stamp #%d", manager.machine.time.seconds, index_seen)) end end end)
_G.t_dma = sp:install_write_tap(0x32000800, 0x32000803, "dma", function(off, data, mask)
  if (data & 0x0f) == 0x0f then dma_starts = dma_starts + 1 end end)
local function setbtn(p, mk, v)
  for _, f in pairs(manager.machine.ioport.ports[":" .. p].fields) do if f.mask == mk then f:set_value(v) end end
end
local function snap(l) shots = shots + 1; if SNAP then manager.machine.video:snapshot() end
  print(string.format("SHOT %d t=%.1f %s  (dma starts %d, index stamps %d)", shots,
    manager.machine.time.seconds, l, dma_starts, index_seen)) end
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
    for _, pr in ipairs(PRESSES) do
      if fc == pr.at then setbtn(pr.port, pr.mask, 1); print(string.format("PRESS t=%.1f %s 0x%02X", m.time.seconds, pr.port, pr.mask)) end
      if fc == pr.at + 30 then setbtn(pr.port, pr.mask, 0) end
    end
    if fc % 300 == 0 then snap("after insert") end
    if RUN > 0 and fc >= RUN * 60 then m:exit() end
  end
end)
