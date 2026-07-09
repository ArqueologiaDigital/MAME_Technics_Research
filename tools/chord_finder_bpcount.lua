-- chord_finder_bpcount.lua -- same navigation, PLUS firmware function-call counters.
-- REQUIRES the debug core (cpu.debug is nil without it) but NO interactive UI:
--   ./kn7000 kn7000 -rompath roms -video none -debug -debugger none \
--       -seconds_to_run 26 -autoboot_script /ABS/PATH/chord_finder_bpcount.lua -autoboot_delay 0
-- Breakpoints use an auto-"g" (go) action so the machine never halts; each hit
-- bumps a debugger temp var. Counts are printed at the end. This confirms whether
-- the ear press actually reaches the voice allocator / sequencer / note handler,
-- independent of whether any TG write is emitted.

local LOGPATH = "/home/fsanches/compartilhado/kn7000_run/chord_finder_bpcount.log"
local logf = io.open(LOGPATH, "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end

local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local io   = mach.ioport
local dbg  = mach.debugger          -- debugger_manager (needs -debug)

local function setbtn(p, mk, v)
  local port = io.ports[":"..p]; if not port then LOG("!! no port :"..p); return end
  for _,f in pairs(port.fields) do if f.mask == mk then f:set_value(v); return end end
  LOG(("!! no field %s mask %04X"):format(p, mk))
end

------------------------------------------------------------------ counters
-- Firmware addresses (kn7000_disassembly/kn7000.sym + notes):
--   0x4848C043  MainSoundAdd  (voice allocator)          -> temp0
--   0x484948BC  MainSeqRun    (sequencer run)            -> temp1
--   0x4844812D  note handler  (downstream of kbd/APC)    -> temp2
if not cpu.debug then
  LOG("!! cpu.debug is nil -- relaunch with '-debug -debugger none'.")
else
  cpu.debug:bpset(0x4848c043, "1", "temp0=temp0+1; g")
  cpu.debug:bpset(0x484948bc, "1", "temp1=temp1+1; g")
  cpu.debug:bpset(0x4844812d, "1", "temp2=temp2+1; g")
  dbg:command("temp0=0"); dbg:command("temp1=0"); dbg:command("temp2=0")
  dbg.execution_state = "run"     -- machine starts paused under -debug; release it
  LOG("breakpoints armed: MainSoundAdd / MainSeqRun / note-handler")
end

local function report(tag)
  if not cpu.debug then return end
  -- snapshot the temps into the console log, then echo the tail to our file
  dbg:command('printf "RESULT %s MSA=%%d SEQ=%%d NOTE=%%d\\n", temp0, temp1, temp2'
              :format(tag))
  local cl = dbg.consolelog
  LOG(("%s -> %s"):format(tag, tostring(cl[#cl])))
end

------------------------------------------------------------------ navigation
-- Best-guess single path (edit EAR to the winner reported by chord_finder_probe.lua).
local APC_MODE     = {"SEG03", 0x02}
local CHORD_FINDER = {"SEG0F", 0x40}
local EAR          = {"SEG11", 0x02}   -- <-- set to the sweep winner
local HOLD = 30
local frame = 0
local plan = {}
local function at(f, fn) plan[f] = fn end

at(1020, function() setbtn(APC_MODE[1],APC_MODE[2],1) end)
at(1020+HOLD, function() setbtn(APC_MODE[1],APC_MODE[2],0); report("after APC MODE") end)
at(1090, function() setbtn(CHORD_FINDER[1],CHORD_FINDER[2],1) end)
at(1090+HOLD, function() setbtn(CHORD_FINDER[1],CHORD_FINDER[2],0); report("after CHORD FINDER") end)
at(1200, function()
     if cpu.debug then dbg:command("temp0=0"); dbg:command("temp1=0"); dbg:command("temp2=0") end
     LOG("counters zeroed; pressing EAR")
     setbtn(EAR[1],EAR[2],1) end)
at(1200+HOLD, function() setbtn(EAR[1],EAR[2],0) end)
at(1320, function() report("after EAR press") ; if logf then logf:close() end end)

emu.add_machine_frame_notifier(function()
  frame = frame + 1
  local fn = plan[frame]; if fn then fn() end
end)
LOG("chord_finder_bpcount.lua armed")
