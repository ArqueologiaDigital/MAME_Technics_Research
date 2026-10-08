-- floppy_kn7000.lua -- does the KN7000 read a floppy? Boots with a FAT12 disk in the
-- drive, presses DISK MENU (cpanel CPR_SEG1 bit 0x04) at t=26 s and the LOAD soft button
-- (LCDR 1, CPR_SEG5 bit 0x10) at t=29 s, snapshots the load screen at t=38 s, and counts
-- FDC register accesses and DACK data bytes.
--
-- Copy of research-scratch/kn7000-pr16250-fixes/floppy_kn7000.lua with the taps held in globals
-- (a tap held only by a local is garbage-collected and silently stops counting -- the original
-- reported 0 FDC accesses even through boot, where the FDC is known to be polled), and with the
-- counts reported separately for boot and for the window after DISK MENU is pressed.
local mac = manager.machine
local prog = mac.devices[":maincpu"].spaces["program"]
local function log(s) emu.print_error(string.format("[flop][%6.2f] ", mac.time:as_double()) .. s) end
regs, dack, regs_at_menu, dack_at_menu = 0, 0, 0, 0
flop_t1 = prog:install_read_tap(0x98020000, 0x9802000f, "fdcr", function(o, d, m) regs = regs + 1; return d end)
flop_t2 = prog:install_write_tap(0x98020000, 0x9802000f, "fdcw", function(o, d, m) regs = regs + 1; return d end)
flop_t3 = prog:install_read_tap(0x98010000, 0x98010003, "dack", function(o, d, m) dack = dack + 1; return d end)
local done = {}
flop_tick = emu.register_periodic(function()
  local t = mac.time:as_double()
  local f = mac.ioport.ports[":cpanel:CPR_SEG1"]:field(0x04)
  if t > 26.0 and not done.a then done.a = true; regs_at_menu, dack_at_menu = regs, dack; f:set_value(1); log(string.format("DISK MENU press (boot so far: FDC %d, DACK %d)", regs, dack)) end
  if t > 26.4 and not done.b then done.b = true; f:set_value(0) end
  local l = mac.ioport.ports[":cpanel:CPR_SEG5"]:field(0x10)
  if t > 29.0 and not done.l then done.l = true; l:set_value(1); log("LOAD press") end
  if t > 29.4 and not done.m then done.m = true; l:set_value(0) end
  if t > 38.0 and not done.c then done.c = true; mac.video:snapshot()
    log(string.format("FDC register accesses %d, DACK data reads %d (after DISK MENU: FDC %d, DACK %d)", regs, dack, regs - regs_at_menu, dack - dack_at_menu)); mac:exit() end
end)
log("armed")
