wait 30
lua local sp=manager.machine.devices[":maincpu"].spaces["program"]; local T=function() return manager.machine.time:as_double() end; _G.FT={}; _G.FT.w=sp:install_write_tap(0x98020000,0x9802000f,"fdcw",function(o,d,m) emu.print_error(string.format("FDCW t=%.3f %X %X/%X",T(),o,d,m)); return d end)
create $HOME/compartilhado/tmp/flop-exe-trial/fmt7k2/kn7000_blank.img
wait 6
press CPR_SEG1 04
wait 4
press CPL_SEG0 02
wait 5
snap
press CPR_SEG7 01
wait 3
snap
lua emu.print_error("MARK yes")
press CPR_SEG7 01
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
lua emu.print_error("MARK r4")
press CPR_SEG6 01
wait 4
snap
lua emu.print_error("MARK exit")
press CPC_SEG11 80
wait 4
snap
lua emu.print_error("MARK ok")
press CPR_SEG6 01
wait 6
snap
unload
info
