-- pcprobe.lua -- capture the PC of the boot writes to 0x130000 to find the
-- runtime<->disasm offset (disasm: DSP_Write_Channel=0x01FCDE, DSP_Init=0x01FC95).
local RUNDIR="/home/fsanches/compartilhado/kn7000_mame/kn5000_envrun"
local logf=io.open(RUNDIR.."/pcprobe.log","w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach=manager.machine; local dbg=mach.debugger; local sub=mach.devices[":subcpu"]
local sp=sub.spaces["program"]
sub.debug:wpset(sp,"w",0x130000,0x20,"1",'printf "D130 %06X=%04X pc=%06X", wpaddr, wpdata, pc; g')
dbg.execution_state="run"
LOG("pcprobe armed")
local st=false
_G._p=emu.add_machine_frame_notifier(function()
 local ok,err=pcall(function()
  local t=mach.time.seconds+mach.time.attoseconds/1e18
  if t>=6.0 and not st then st=true
    local cl=dbg.consolelog
    LOG("consolelog lines="..#cl)
    local n=0
    for i=1,#cl do local s=cl[i]; if type(s)=="string" and s:find("D130") then n=n+1; if n<=20 then LOG(s) end end end
    LOG("total D130="..n)
    -- also sample subcpu PC now
    LOG("CURPC now="..string.format("%06X", sub.state["CURPC"].value))
    LOG("DONE")
  end
 end); if not ok then LOG("ERR "..tostring(err)) end
end)
