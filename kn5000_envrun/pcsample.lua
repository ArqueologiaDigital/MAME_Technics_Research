-- pcsample.lua -- sample subcpu (and maincpu) PC over time to see what code regions execute.
local RUNDIR="/home/fsanches/compartilhado/kn7000_mame/kn5000_envrun"
local logf=io.open(RUNDIR.."/pcsample.log","w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach=manager.machine
local sub=mach.devices[":subcpu"]; local main=mach.devices[":maincpu"]
local subhist={}; local mainhist={}; local n=0
local function bucket(pc) return string.format("%02X0000", (pc>>16)&0xFF) end
_G._s=emu.add_machine_frame_notifier(function()
 local ok,err=pcall(function()
  local sp=sub.state["CURPC"].value; local mp=main.state["CURPC"].value
  subhist[bucket(sp)]=(subhist[bucket(sp)] or 0)+1
  mainhist[bucket(mp)]=(mainhist[bucket(mp)] or 0)+1
  -- also keep a fine subcpu histogram in low region
  if (sp>>16)&0xFF <= 0x0F then
    local b=string.format("%04X", (sp>>8)&0xFFFF)
    subhist["lo_"..b]=(subhist["lo_"..b] or 0)+1
  end
  n=n+1
  local t=mach.time.seconds+mach.time.attoseconds/1e18
  if t>=9.0 and not _G._done then _G._done=true
    LOG("samples="..n)
    LOG("== SUBCPU pc buckets ==")
    local keys={}; for k,_ in pairs(subhist) do keys[#keys+1]=k end; table.sort(keys)
    for _,k in ipairs(keys) do LOG(("  %s : %d"):format(k, subhist[k])) end
    LOG("== MAINCPU pc buckets ==")
    keys={}; for k,_ in pairs(mainhist) do keys[#keys+1]=k end; table.sort(keys)
    for _,k in ipairs(keys) do LOG(("  %s : %d"):format(k, mainhist[k])) end
    LOG("DONE")
  end
 end); if not ok then LOG("ERR "..tostring(err)) end
end)
LOG("pcsample armed")
