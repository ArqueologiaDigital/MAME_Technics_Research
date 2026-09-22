-- pm_verify_shot.lua -- prove the PANEL MEMORY assembly actually renders and changes state.
--
-- Question it answers: "does the traced artwork reach the screen, does the right wedge darken
-- when its bit is pressed, and does the LED window at that wedge's inner end light up?"
-- MAME parses a layout at machine start, not in -validate, so a render is the only proof.
--
--   cd ~/compartilhado/kn7000-emulator
--   timeout -k 5 180 ./run.sh -window -nothrottle -snapsize 2000x1500 -snapview Compact \
--       -snapshot_directory ./snap/pm -autoboot_script tools/pm_verify_shot.lua -autoboot_delay 1
--
-- 0000.png is idle, 0001.png is with PANEL MEMORY 1 (CPR_SEG0 0x02) and SET (CPR_SEG7 0x40) held.
-- Expected in 0001: the wedge labelled 1 (the 157.5 deg slot) in its pressed cream #b3aa96, its
-- LED arc bright green, and the SET cap in its pressed slate -- everything else unchanged.
--
-- Full-resolution panel grabs: idle, then with PANEL MEMORY 1 + SET held so the pressed
-- artwork and any lamp that follows are visible. Held in globals so nothing is collected.
local stage = 0
_G.pm_fields = {}
_G.pm_step = function()
  local t = manager.machine.time
  local s = t.seconds + t.attoseconds / 1e18
  if stage == 0 and s > 12 then
    stage = 1
    for tag, port in pairs(manager.machine.ioport.ports) do
      if tag:find("CPR_SEG") then
        for fname, f in pairs(port.fields) do
          print(string.format("[pm] port %s mask 0x%02x %s", tag, f.mask, fname))
        end
      end
    end
    manager.machine.video:snapshot()
    print("[pm] idle snapshot at " .. s)
  elseif stage == 1 and s > 12.5 then
    stage = 2
    local want = { ["CPR_SEG0"] = 0x02, ["CPR_SEG7"] = 0x40 }   -- PANEL MEMORY 1, SET
    for tag, port in pairs(manager.machine.ioport.ports) do
      for seg, mask in pairs(want) do
        if tag:find(seg .. "$") then
          for _, f in pairs(port.fields) do
            if f.mask == mask then
              f:set_value(1); table.insert(_G.pm_fields, f)
              print("[pm] holding " .. tag .. " mask " .. mask)
            end
          end
        end
      end
    end
  elseif stage == 2 and s > 14 then
    stage = 3
    manager.machine.video:snapshot()
    print("[pm] pressed snapshot at " .. s)
    manager.machine:exit()
  end
end
emu.register_periodic(_G.pm_step)
