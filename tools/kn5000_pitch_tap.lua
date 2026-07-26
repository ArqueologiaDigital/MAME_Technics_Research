-- PITCH AUDIT: tap the IC303 register bus over a held note.
local OUT = os.getenv("OUT") or "/tmp/pitchtap.log"
local T_ARM = tonumber(os.getenv("T_ARM") or "12.0")
local T_ON  = tonumber(os.getenv("T_ON")  or "13.0")
local T_OFF = tonumber(os.getenv("T_OFF") or "16.0")
local T_END = tonumber(os.getenv("T_END") or "17.5")
local KEYPORT = os.getenv("KEYPORT") or "KEY2"
local KEYMASK = tonumber(os.getenv("KEYMASK") or "1")
local f = io.open(OUT,"w")
local function LOG(s) emu.print_info(s); if f then f:write(s.."\n"); f:flush() end end
local mach = manager.machine
local dbg  = mach.debugger
local sub  = mach.devices[":subcpu"]
local sp   = sub.spaces["program"]
dbg.execution_state = "run"
local function setkey(v)
  local p = mach.ioport.ports[":"..KEYPORT]; if not p then LOG("!! no port "..KEYPORT); return end
  for _,fl in pairs(p.fields) do if fl.mask==KEYMASK then fl:set_value(v); return end end
  LOG("!! no field mask")
end
local mark=0
local st={}
local function once(k) if st[k] then return false end st[k]=true; return true end
_G._n = emu.add_machine_frame_notifier(function()
  local ok,err = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds/1e18
    if t>=T_ARM and once("arm") then
      mark = #dbg.consolelog
      sub.debug:wpset(sp,"w",0x100000,4,"1",'printf "IC %06X=%04X", wpaddr, wpdata; g')
      LOG(("ARM @%.2f"):format(t))
    end
    if t>=T_ON and once("on") then setkey(1); LOG(("KEYON @%.3f  idx=%d"):format(t,#dbg.consolelog)) end
    if t>=(T_ON+T_OFF)/2 and once("mid") then LOG(("MID @%.3f  idx=%d"):format(t,#dbg.consolelog)) end
    if t>=T_OFF and once("off") then setkey(0); LOG(("KEYOFF @%.3f  idx=%d"):format(t,#dbg.consolelog)) end
    if t>=T_END and once("end") then
      local cl = dbg.consolelog
      LOG(("---- STREAM %d..%d ----"):format(mark+1,#cl))
      for i=mark+1,#cl do LOG(cl[i]) end
      LOG("---- END ----")
      mach:exit()
    end
  end)
  if not ok then LOG("ERR "..tostring(err)) end
end)
