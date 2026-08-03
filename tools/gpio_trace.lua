-- gpio_trace.lua -- dynamic GPIO / I/O access tracer for the KN7000 (MAME autoboot script).
--
-- Purpose: find which port/latch bits a firmware routine touches by watching the CPU access
-- them live. Built to hunt the USB co-processor bit-bang link (notes/FINDINGS-usb-subsystem.md),
-- but useful for any bit-banged peripheral.
--
-- Usage:
--   cd kn7000-emulator
--   ./run.sh -window -skip_gameinfo -autoboot_script <this> -seconds_to_run 45
-- Results print to the log as "GPIOTRACE <addr>|<pc>|<R|W> x<count>" between BEGIN/END markers.
-- Grep the run output for GPIOTRACE and aggregate.
--
-- Two lessons baked in:
--   * emu.add_machine_frame_notifier / install_*_tap return subscription objects that MUST be
--     retained (here in _G) or Lua's GC silently kills them after ~120 frames.
--   * MAME Lua sandboxes io.open; route output through emu.print_info (-> osd_printf_info,
--     which the run log captures).
--
-- Tunables:
local ARM_FRAME  = 900     -- start recording AFTER this frame (skip boot-time GPIO init)
local DUMP_FRAME = 2400    -- dump and exit at this frame
local RANGES = {           -- {start, end} address ranges to tap (main-CPU program space)
  {0x36008000, 0x360080ff},  -- external GPIO latches (SD CS, panel, heartbeat, ... and USB?)
  -- add on-chip port ranges here if a bit-bang is found outside the external latches, e.g.:
  -- {0x34000000, 0x340000ff}, {0x34000300, 0x340007ff},
}

local cpu = manager.machine.devices[":maincpu"]
local sp  = cpu.spaces["program"]
local agg, armed = {}, false

local function pcval()
  local ok, v = pcall(function() return cpu.state["CURPC"].value end)
  return ok and v or 0
end
local function rec(addr, rw)
  if not armed then return end
  local k = string.format("%08X|%08X|%s", addr, pcval(), rw)
  agg[k] = (agg[k] or 0) + 1
end

_G.__gpio_taps = {}
for _, r in ipairs(RANGES) do
  table.insert(_G.__gpio_taps, sp:install_read_tap (r[1], r[2], "gtr", function(o,d,m) rec(o, "R") end))
  table.insert(_G.__gpio_taps, sp:install_write_tap(r[1], r[2], "gtw", function(o,d,m) rec(o, "W") end))
end

local n = 0
_G.__gpio_sub = emu.add_machine_frame_notifier(function()
  n = n + 1
  if n == ARM_FRAME then armed = true end
  if n == DUMP_FRAME then
    local keys = {}
    for k in pairs(agg) do keys[#keys+1] = k end
    table.sort(keys)
    emu.print_info("GPIOTRACE BEGIN " .. #keys)
    for _, k in ipairs(keys) do emu.print_info("GPIOTRACE " .. k .. " x" .. agg[k]) end
    emu.print_info("GPIOTRACE END")
    manager.machine:exit()
  end
end)
