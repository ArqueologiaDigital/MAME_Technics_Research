local iop = manager.machine.ioport
local function press(tag,name,v)
  local ok,err = pcall(function() iop.ports[tag].fields[name]:set_value(v) end)
  if not ok then print("PRESSFAIL "..tag.." '"..name.."': "..tostring(err)) end
end
local d={}
emu.register_frame_done(function()
  local t = manager.machine.time.seconds
  if t>=15 and not d.a then d.a=true; press(":KEYS0","Key C4",1); print("NOTE C4 on t="..t) end
  if t>=15.6 and not d.b then d.b=true; press(":KEYS0","Key C4",0); press(":KEYS0","Key E4",1) end
  if t>=16.2 and not d.c then d.c=true; press(":KEYS0","Key E4",0); press(":KEYS1","Key C5",1) end
  if t>=16.8 and not d.d then d.d=true; press(":KEYS1","Key C5",0) end
  if t>=20 then manager.machine:exit() end
end)
