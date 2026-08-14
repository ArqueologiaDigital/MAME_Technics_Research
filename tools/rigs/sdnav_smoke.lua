-- Smoke test: confirm SD MENU at t=30, inspect DIAL field API
local mac = manager.machine
local done = {}
local function once(k) if done[k] then return false end done[k]=true return true end
emu.register_periodic(function()
  local t = mac.time.seconds + mac.time.attoseconds/1e18
  if t>=2 and once("ports") then
    local p = mac.ioport.ports[":DIAL"]
    if p then
      for n,f in pairs(p.fields) do
        emu.print_error(("DIAL field '%s' mask=%02X is_analog=%s val=%s"):format(
          n, f.mask, tostring(f.is_analog), tostring(p:read())))
      end
    else emu.print_error("NO :DIAL port") end
    for _,tag in ipairs({":cpanel:CPL_SEG0", ":cpanel:CPR_SEG1", ":cpanel:CPC_SEG11", ":CPSD_SDSW"}) do
      local pp = mac.ioport.ports[tag]
      emu.print_error(("port %s -> %s"):format(tag, pp and "OK" or "MISSING"))
    end
  end
  if t>=30 and once("snap") then
    mac.video:snapshot()
    emu.print_error("[30] baseline snapshot taken")
  end
end)
emu.print_error("sdnav_smoke armed")
