-- kn6000_pres_trace.lua -- KN6000: where does a feature-presentation insert stop?
-- Same stimulus as kn6000_pres_insert.lua (boot, DEMO at t = 20 s, insert $PRES_IMG into
-- :fdc:0:35hd at t = 24 s), plus debugger breakpoints along the DEMONSTRATION screen's
-- disk-insert path, whose console lines are relayed to stdout:
--   EV      0x484B1DC1  message 0x1800014 reached the DEMO screen proc (0x484B1D1E); prints the
--                       event word (& 0xFFFFFF must be 0x708000) and its sub-code (1 = disk in)
--   SCREEN  0x484AD0D0  current screen id (the handler needs 0x1F000CF) ...
--   SCRCHK  0x484B1DE2  ... and the result of the screen + three not-busy checks (1 = go on)
--   MEDIA   0x484AD10E  drive/media type from 0x4854CDA4 (0 or 5 -> -7, 1 -> -8, else mount)
--   MOUNT   0x484AD12D  result of the mount 0x4854D1D5
--   MOUNTCHK 0x484B1DEC result of 0x484AD107 (the handler ignores it)
--   find:   steps inside find-first 0x48533461: fs mode byte, path parse, directory open, scan, match
--   FIND    0x4854CCD2  find-first 0x48533461 on "FEATURE .PRE" (negative = not found / error)
--   PROBE   0x4854CDBA  media probe 0x4853312E, run when the cache byte 0x500605FD holds 0xFF
--   WP      every write to that cache byte 0x500605FD, with the writing PC
--   PRECHK  0x484B1DF9  result of the "FEATURE .PRE" lookup 0x4854CCC4 (non-zero = found)
--   OPEN    0x484B1E0E  the handler posts 0x018F0026 with "FEATURE " (open the presentation)
-- Needs -debug (the script drives the debugger; -debugger none adds no debugger window, the
-- MAME window stays visible). Breakpoints are set on both the program address and its
-- library alias (program - 0x48400000 + 0x4C000000), since the KN6000 runs code from both.
-- Run: kn7000 kn6000 -rompath ROMS -window -nothrottle -debug -debugger none \
--        -snapshot_directory OUT -autoboot_script kn6000_pres_trace.lua   (env PRES_IMG=copy.img)
local IMG = os.getenv("PRES_IMG")
local phase, fc, shots, seen = "boot", 0, 0, 0
local function setbtn(p, mk, v)
  for _, f in pairs(manager.machine.ioport.ports[":" .. p].fields) do if f.mask == mk then f:set_value(v) end end
end
local function snap(l) shots = shots + 1; manager.machine.video:snapshot()
  print(string.format("SHOT %d t=%.1f %s", shots, manager.machine.time.seconds, l)) end
local BPS = {
  { 0x484b1dc1, '{printf "EV ev=%08X sub=%02X",d@(d@(sp+24)),b@(d@(sp+24)+4); g}' },
  { 0x484ad0d0, '{printf "SCREEN id=%08X",d0; g}' },
  { 0x484b1de2, '{printf "SCRCHK d0=%X",d0; g}' },
  { 0x484ad10e, '{printf "MEDIA d0=%X",d0; g}' },
  { 0x484ad12d, '{printf "MOUNT d0=%X",d0; g}' },
  { 0x4854cdba, '{printf "PROBE 0x4853312E -> d0=%X",d0; g}' },
  { 0x484b1dec, '{printf "MOUNTCHK d0=%X",d0; g}' },
  { 0x4853346a, '{printf "  find: fs mode 0x50004B5D=%X",d0; g}' },
  { 0x485334b1, '{printf "  find: parse 0x485333DF -> %X",d0; g}' },
  { 0x485334d7, '{printf "  find: open dir 0x4853008C -> %X",a0; g}' },
  { 0x48533512, '{printf "  find: scan 0x485302BD -> %X",d0; g}' },
  { 0x48533561, '{printf "  find: match 0x485335B5 -> %X",d0; g}' },
  { 0x4854ccd2, '{printf "FIND d0=%X",d0; g}' },
  { 0x484b1df9, '{printf "PRECHK d0=%X",d0; g}' },
  { 0x484b1e0e, '{printf "OPEN posted d1=%08X",d1; g}' },
}
-- armed at the insert, not at boot: the FS block pool (allocator 0x48512A37, RTOS pool 1) and
-- its frees, with the caller from MDR, to see whether the pool is exhausted
local BPS_AT_INSERT = {
  { 0x48512a37, '{printf "  alloc req %X bytes (caller %08X)",d0,mdr; g}' },
  { 0x48512a59, '{printf "  alloc -> %X",a0; g}' },
  { 0x48512a61, '{printf "  free %X (caller %08X)",a0,mdr; g}' },
}
local function relay()
  local log = manager.machine.debugger.consolelog
  while seen < #log do seen = seen + 1; print("DBG " .. log[seen]) end
end
_G.p_sub = emu.add_machine_frame_notifier(function()
  local m = manager.machine; fc = fc + 1
  relay()
  if phase == "boot" then
    if fc == 1 then
      local dbg = m.debugger
      for _, b in ipairs(BPS) do
        for _, base in ipairs({ 0, 0x03c00000 }) do   -- 0x484xxxxx and its alias 0x4C0xxxxx
          dbg:command(string.format("bp %X,1,", b[1] + base) .. b[2])
        end
      end
      -- every write to the media-type cache byte, with the writer's PC
      dbg:command('wpset 500605fd,1,w,1,{printf "WP 0x500605FD <- %02X pc=%08X",wpdata,pc; g}')
      dbg:command("g")
    end
    if m.time.seconds >= 20 then setbtn("cpanel:CPL_SEG9", 0x40, 1); phase = "demo"; fc = 0 end
  elseif phase == "demo" then
    if fc == 30 then setbtn("cpanel:CPL_SEG9", 0x40, 0) end
    if fc >= 240 then snap("DEMO screen")
      for _, b in ipairs(BPS_AT_INSERT) do
        for _, base in ipairs({ 0, 0x03c00000 }) do
          m.debugger:command(string.format("bp %X,1,", b[1] + base) .. b[2])
        end
      end
      -- the first failed allocation also dumps 64 KB of the pool's neighbourhood (cwd)
      m.debugger:command('bp 48512a59,a0==0,{printf "  alloc FAILED, dumping pool_fail.bin"; save pool_fail.bin,501c0000,10000; bpclear; g}')
      print("LOAD " .. tostring(m.images[":fdc:0:35hd"]:load(IMG)))
      phase = "run"; fc = 0 end
  elseif phase == "run" then
    if fc % 300 == 0 then snap("after insert") end
    if fc >= 1800 then m:exit() end
  end
end)
