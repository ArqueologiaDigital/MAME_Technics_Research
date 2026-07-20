-- poll BOTH cpus' PC + XSSP to locate the stall
local mach = manager.machine
local sub  = mach.devices[":subcpu"]
local main = mach.devices[":maincpu"]
_G._n = emu.register_frame_done(function()
  pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds/1e18
    if t >= 4.0 and (math.floor(t*2) ~= (_G._l or -1)) then
      _G._l = math.floor(t*2)
      emu.print_info(string.format("@@@ t=%5.1f MAIN pc=%06X xssp=%06X | SUB pc=%06X xssp=%06X",
        t, main.state["PC"].value, main.state["XSSP"].value,
        sub.state["PC"].value, sub.state["XSSP"].value))
    end
    if t >= 20.0 and not _G._s then _G._s=true; mach.video:snapshot() end
    if t >= 21.0 then mach:exit() end
  end)
end)
