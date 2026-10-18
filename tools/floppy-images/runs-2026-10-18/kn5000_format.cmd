wait 30
lua local sp=manager.machine.devices[":maincpu"].spaces["program"]; local T=function() return manager.machine.time:as_double() end; _G.FT={}; _G.FT.w=sp:install_write_tap(0x11000a,0x11000b,"fdcw",function(o,d,m) emu.print_error(string.format("FDCW t=%.3f %02X",T(),d&0xff)); return d end); _G.FT.r=sp:install_read_tap(0x11000a,0x11000b,"fdcr",function(o,d,m) emu.print_error(string.format("FDCR t=%.3f %02X",T(),d&0xff)); return d end); _G.FT.a=sp:install_write_tap(0x110008,0x110009,"fdca",function(o,d,m) emu.print_error(string.format("FDCA t=%.3f %02X",T(),d&0xff)); return d end)
create $HOME/compartilhado/tmp/flop-exe-trial/fmt5k6/kn5000_blank.img
wait 6
press CPR_SEG10 20
wait 3
snap
press CPR_SEG10 20
wait 3
snap
press CPL_SEG10 02
wait 5
snap
press CPL_SEG8 01
wait 3
snap
lua emu.print_error("MARK yes")
press CPL_SEG8 01
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
wait 5
snap
wait 5
snap
wait 5
snap
wait 5
snap
lua emu.print_error("MARK nameok")
press CPL_SEG7 02
wait 6
snap
unload
info
exit
