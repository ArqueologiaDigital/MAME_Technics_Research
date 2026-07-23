-- env_trace.lua -- DECISIVE envelope experiment for the KN5000 tone generator.
-- Uses the debug core (bpset/wpset) which fires on the TLCS-900 sub-CPU
-- (install_write_tap misses tlcs900 writes; debugger watchpoints do not).
--
--   fs_mamed kn5000 -rp roms -debug -debugger none -seconds_to_run 24 \
--       -autoboot_delay 0 -autoboot_script <this> -nvram_directory <iso>
--
-- What it measures over one held keybed note:
--   * 0x130000 block (subcpu) writes  -> validated at boot, watched during play.
--   * 0x100000/0x100002 (IC303)       -> the full register/data stream during play,
--       so we can see whether the LEVEL reg (group8.bank0 = addr 0x800|ch) is
--       re-written with a ramp over the note (software envelope) or written once.
--   * call counts of ToneGen_WriteVoiceParams / DSP_Write_Channel / DSP_Init_Channels.

local RUNDIR = "/home/fsanches/compartilhado/kn7000_mame/kn5000_envrun"
local TAG    = os.getenv("TAG") or "default"
local KEYPORT= os.getenv("KEYPORT") or "KEY2"   -- KEY2 = middle-C octave
local KEYMASK= tonumber(os.getenv("KEYMASK") or "1")  -- 0x001 = C4
local T_KEYON  = tonumber(os.getenv("T_KEYON")  or "20.2")
local T_KEYOFF = tonumber(os.getenv("T_KEYOFF") or "21.7")
local T_END    = tonumber(os.getenv("T_END")    or "22.6")

local logf = io.open(RUNDIR.."/trace_"..TAG..".log", "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end

local mach = manager.machine
local dbg  = mach.debugger
local sub  = mach.devices[":subcpu"]
if not dbg or not sub or not sub.debug then
  LOG("!! debug core missing -- relaunch with -debug -debugger none"); return
end
local subsp = sub.spaces["program"]

-- ---- addresses (task + disasm) --------------------------------------------
local A_WVP = 0x02D0FD   -- ToneGen_WriteVoiceParams (note-on / param writer)
local A_DWC = 0x01FCDE   -- DSP_Write_Channel  (writes 0x130000 block)
local A_DIC = 0x01FC95   -- DSP_Init_Channels  (writes 0x130000 block)

-- ---- counters (auto-continue breakpoints) ---------------------------------
sub.debug:bpset(A_WVP, "1", "temp0=temp0+1; g")
sub.debug:bpset(A_DWC, "1", "temp1=temp1+1; g")
sub.debug:bpset(A_DIC, "1", "temp2=temp2+1; g")
dbg:command("temp0=0"); dbg:command("temp1=0"); dbg:command("temp2=0")

-- ---- watchpoints -----------------------------------------------------------
-- 0x130000 block: armed from the start so it CATCHES the boot DSP_Init writes
-- (self-validation that watchpoints fire on tlcs900) and shows any play writes.
sub.debug:wpset(subsp, "w", 0x130000, 0x20, "1",
  'printf "D130 %06X %04X", wpaddr, wpdata; g')
-- IC303: armed only during the play window (boot emits thousands of TG writes).
local wp_ic303 = nil

dbg.execution_state = "run"    -- release the initial -debug pause
LOG(("armed. TAG=%s key=%s mask=0x%03X on=%.2f off=%.2f end=%.2f")
    :format(TAG, KEYPORT, KEYMASK, T_KEYON, T_KEYOFF, T_END))

-- ---- helpers ---------------------------------------------------------------
local function counters(label)
  dbg:command(('printf "CNT[%s] wvp=%%d dwc=%%d dic=%%d", temp0, temp1, temp2'):format(label))
  local cl = dbg.consolelog
  LOG(("%s"):format(tostring(cl[#cl])))
end
local function setkey(v)
  local port = mach.ioport.ports[":"..KEYPORT]
  if not port then LOG("!! no port :"..KEYPORT); return end
  for _,f in pairs(port.fields) do if f.mask == KEYMASK then f:set_value(v); return end end
  LOG("!! no field mask in "..KEYPORT)
end
local cl_mark = 0
local function harvest(fromidx, label)
  local cl = dbg.consolelog
  LOG(("---- consolelog %s [%d..%d] ----"):format(label, fromidx+1, #cl))
  for i = fromidx+1, #cl do LOG(cl[i]) end
end

-- ---- timeline --------------------------------------------------------------
local done = {}
local function once(key) if done[key] then return false end done[key]=true; return true end

emu.add_machine_frame_notifier(function()
  local t = mach.time.seconds + mach.time.attoseconds/1e18

  if t >= T_KEYON-0.15 and once("boot") then
    -- boot snapshot + boot counters (validates DSP_Init ran, 0x130000 boot writes)
    mach.video:snapshot()
    counters("boot")
    cl_mark = #dbg.consolelog
    -- zero counters for the play window
    dbg:command("temp0=0"); dbg:command("temp1=0"); dbg:command("temp2=0")
    -- arm IC303 watchpoint for the play window
    wp_ic303 = sub.debug:wpset(subsp, "w", 0x100000, 4, "1",
      'printf "IC303 %06X %04X", wpaddr, wpdata; g')
    LOG("boot snapshot taken; IC303 watchpoint armed; counters zeroed")
  end

  if t >= T_KEYON and once("on") then
    setkey(1); LOG(("KEY ON @ %.3f"):format(t))
  end
  if t >= (T_KEYON+T_KEYOFF)/2 and once("mid") then
    counters("mid-hold"); mach.video:snapshot()
  end
  if t >= T_KEYOFF and once("off") then
    setkey(0); LOG(("KEY OFF @ %.3f"):format(t))
  end
  if t >= T_END and once("end") then
    counters("play-window")
    harvest(cl_mark, "play-window (D130 + IC303 stream)")
    mach.video:snapshot()
    LOG("DONE")
    if logf then logf:flush() end
  end
end)
