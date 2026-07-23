-- diag.lua -- verify debug-core counter + consolelog readback + watchpoint firing.
local RUNDIR = "/home/fsanches/compartilhado/kn7000_mame/kn5000_envrun"
local logf = io.open(RUNDIR.."/diag.log", "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local dbg  = mach.debugger
local sub  = mach.devices[":subcpu"]
LOG("dbg="..tostring(dbg).." sub="..tostring(sub).." sub.debug="..tostring(sub and sub.debug))
local subsp = sub.spaces["program"]
-- count DSP_Write_Channel (boot writer of 0x130000) and watch 0x130000
sub.debug:bpset(0x01FCDE, "1", "temp1=temp1+1; g")
sub.debug:bpset(0x01FC95, "1", "temp2=temp2+1; g")
dbg:command("temp1=0"); dbg:command("temp2=0")
sub.debug:wpset(subsp, "w", 0x130000, 0x20, "1", 'printf "D130 %06X=%04X", wpaddr, wpdata; g')
dbg.execution_state = "run"
LOG("armed diag")
local last=0
_G._d = emu.add_machine_frame_notifier(function()
  local ok,err = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds/1e18
    if t>=5.0 and last==0 then
      last=1
      LOG("consolelog type="..type(dbg.consolelog))
      local cl = dbg.consolelog
      LOG("consolelog len="..tostring(cl and #cl))
      dbg:command('printf "CNT dwc=%d dic=%d", temp1, temp2')
      cl = dbg.consolelog
      LOG("after printf len="..tostring(#cl).." last="..tostring(cl[#cl]))
      -- dump any D130 lines
      local n=0
      for i=1,#cl do local s=cl[i]; if type(s)=="string" and s:find("D130") then n=n+1; if n<=12 then LOG("  "..s) end end end
      LOG("D130 line count="..n)
      LOG("DIAG DONE")
    end
  end)
  if not ok then LOG("ERR "..tostring(err)) end
end)
