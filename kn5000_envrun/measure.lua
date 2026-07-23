-- measure.lua -- DECISIVE KN5000 envelope measurement via debug-core watchpoints
-- (verified to fire on the TLCS-900 sub-CPU).
--   D130  watchpoint : subcpu 0x130000..0x13001F writes  (Felipe's ADSR candidate)
--   IC303 watchpoint : subcpu 0x100000..0x100003 writes  (reg-addr latch + data)
-- Over one held keybed note we see (a) whether 0x130000 is touched during play,
-- and (b) whether the IC303 LEVEL reg (group8.bank0 = addr 0x0800|ch) is
-- re-written with a ramp (software envelope) or written once.
local RUNDIR = "/home/fsanches/compartilhado/kn7000_mame/kn5000_envrun"
local TAG    = os.getenv("TAG") or "default"
local KEYPORT= os.getenv("KEYPORT") or "KEY2"
local KEYMASK= tonumber(os.getenv("KEYMASK") or "1")   -- 0x001 = C4
local T_ARM  = tonumber(os.getenv("T_ARM")  or "10.0") -- arm IC303 wp, snapshot
local T_ON   = tonumber(os.getenv("T_ON")   or "10.3")
local T_OFF  = tonumber(os.getenv("T_OFF")  or "11.8")
local T_END  = tonumber(os.getenv("T_END")  or "12.8")

local logf = io.open(RUNDIR.."/meas_"..TAG..".log", "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local dbg  = mach.debugger
local sub  = mach.devices[":subcpu"]
local subsp= sub.spaces["program"]

-- 0x130000 block: armed from start (catches boot writes -> validation, then play).
sub.debug:wpset(subsp, "w", 0x130000, 0x20, "1", 'printf "D130 %06X=%04X pc=%06X", wpaddr, wpdata, pc; g')
dbg.execution_state = "run"
LOG(("armed. TAG=%s key=%s mask=0x%03X arm=%.2f on=%.2f off=%.2f end=%.2f"):format(TAG,KEYPORT,KEYMASK,T_ARM,T_ON,T_OFF,T_END))

local function setkey(v)
  local port = mach.ioport.ports[":"..KEYPORT]; if not port then LOG("!! no port"); return end
  for _,f in pairs(port.fields) do if f.mask==KEYMASK then f:set_value(v); return end end
  LOG("!! no field")
end
local function dumpfrom(mark, label)
  local cl = dbg.consolelog
  LOG(("---- %s : consolelog[%d..%d] ----"):format(label, mark+1, #cl))
  for i=mark+1,#cl do LOG(cl[i]) end
end

local mark_arm = 0
local st = {}
local function once(k) if st[k] then return false end st[k]=true; return true end
_G._m = emu.add_machine_frame_notifier(function()
  local ok,err = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds/1e18
    if t>=T_ARM and once("arm") then
      mach.video:snapshot()
      local cl=dbg.consolelog
      -- count boot D130 writes seen so far
      local n=0; for i=1,#cl do local s=cl[i]; if type(s)=="string" and s:find("D130") then n=n+1 end end
      LOG("BOOT D130 write count = "..n)
      mark_arm = #cl
      sub.debug:wpset(subsp, "w", 0x100000, 4, "1", 'printf "IC303 %06X=%04X", wpaddr, wpdata; g')
      LOG("IC303 watchpoint armed; play window begins")
    end
    if t>=T_ON  and once("on")  then setkey(1); LOG(("KEY ON @%.3f"):format(t)) end
    if t>=(T_ON+T_OFF)/2 and once("mid") then mach.video:snapshot(); LOG("mid snapshot") end
    if t>=T_OFF and once("off") then setkey(0); LOG(("KEY OFF @%.3f"):format(t)) end
    if t>=T_END and once("end") then
      dumpfrom(mark_arm, "PLAY WINDOW (D130 + IC303 stream)")
      mach.video:snapshot(); LOG("DONE")
    end
  end)
  if not ok then LOG("ERR "..tostring(err)) end
end)
