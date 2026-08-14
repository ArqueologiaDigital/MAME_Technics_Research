local mac=manager.machine; local d=false
emu.register_periodic(function() local t=mac.time.seconds+mac.time.attoseconds/1e18
  if not d and t>=16 then mac.video:snapshot(); d=true end end)
