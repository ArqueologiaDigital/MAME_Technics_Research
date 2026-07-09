local cpu = manager.machine.devices[":maincpu"]
local space = cpu.spaces["program"]
local hits = {}
local function pcval()
  local v=0
  if not pcall(function() v=cpu.state["CURPC"].value end) then pcall(function() v=cpu.state["PC"].value end) end
  return v
end
-- tap reads across the whole rhythm style-name table region
local tap = space:install_read_tap(0x4872A000, 0x4872CFFF, "styletap", function(offset, data, mask)
  local key = string.format("%08X", pcval())
  local h = hits[key]; if not h then h={n=0,lo=offset,hi=offset}; hits[key]=h end
  h.n=h.n+1; if offset<h.lo then h.lo=offset end; if offset>h.hi then h.hi=offset end
end)
local pressed=false; local dumped=false
emu.register_frame_done(function() local m=manager.machine; local t=m.time.seconds
  if not pressed and t>=17.3 then pressed=true
    for _,f in pairs(m.ioport.ports[":SEG00"].fields) do if f.mask==0x10 then f:set_value(1) end end end
  if not dumped and t>=18.6 then dumped=true
    for k,h in pairs(hits) do print(string.format("TAP pc=%s reads=%d range=%08X..%08X", k, h.n, h.lo, h.hi)) end
    m:exit()
  end end)
