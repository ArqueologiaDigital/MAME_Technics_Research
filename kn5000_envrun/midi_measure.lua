-- midi_measure.lua -- watch subcpu 0x130000 and IC303 while a MIDI file plays a
-- held note (fed via -min <file.mid>). No panel/keybed needed.
local RUNDIR = "/home/fsanches/compartilhado/kn7000_mame/kn5000_envrun"
local TAG    = os.getenv("TAG") or "midi"
local T_ARM  = tonumber(os.getenv("T_ARM")  or "8.0")   -- arm IC303 wp + snapshot
local T_MID  = tonumber(os.getenv("T_MID")  or "9.8")   -- mid-note snapshot
local T_END  = tonumber(os.getenv("T_END")  or "12.0")  -- harvest
local logf = io.open(RUNDIR.."/midi_"..TAG..".log", "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local dbg  = mach.debugger
local sub  = mach.devices[":subcpu"]
local subsp= sub.spaces["program"]
sub.debug:wpset(subsp, "w", 0x130000, 0x20, "1", 'printf "D130 %06X=%04X pc=%06X", wpaddr, wpdata, pc; g')
dbg.execution_state = "run"
LOG(("armed TAG=%s arm=%.2f mid=%.2f end=%.2f"):format(TAG,T_ARM,T_MID,T_END))
local mark=0; local st={}
local function once(k) if st[k] then return false end st[k]=true; return true end
local function dumpfrom(m,l) local cl=dbg.consolelog; LOG(("---- %s [%d..%d] ----"):format(l,m+1,#cl)); for i=m+1,#cl do LOG(cl[i]) end end
_G._mm = emu.add_machine_frame_notifier(function()
  local ok,err = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds/1e18
    if t>=T_ARM and once("arm") then
      mach.video:snapshot()
      local cl=dbg.consolelog; local n=0
      for i=1,#cl do local s=cl[i]; if type(s)=="string" and s:find("D130") then n=n+1 end end
      LOG("BOOT D130 count="..n); mark=#cl
      sub.debug:wpset(subsp, "w", 0x100000, 4, "1", 'printf "IC303 %06X=%04X", wpaddr, wpdata; g')
      LOG("IC303 wp armed")
    end
    if t>=T_MID and once("mid") then mach.video:snapshot(); LOG("mid snapshot @"..string.format("%.2f",t)) end
    if t>=T_END and once("end") then dumpfrom(mark,"PLAY WINDOW"); mach.video:snapshot(); LOG("DONE") end
  end)
  if not ok then LOG("ERR "..tostring(err)) end
end)
