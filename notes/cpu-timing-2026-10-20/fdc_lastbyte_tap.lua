-- log DACK reads (with PC), TC writes and FDC result bytes, with emulated time in us
local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local sp = cpu.spaces["program"]
_G.F2 = {n=0, last=0}
local function us() return mac.time:as_double() * 1e6 end
_G.F2.d = sp:install_read_tap(0x98010000, 0x98010003, "dack", function(off, data, mask)
  _G.F2.n = _G.F2.n + 1
  local pc = cpu.state["PC"].value
  local function st(n) local e = cpu.state[n]; return e and e.value or 0 end
  if pc < 0x48402000 or pc > 0x48402300 then _G.F2.last = us(); _G.F2.c = {st("TINSN"), st("TMEM"), st("TICMISS"), st("TDCMISS")}; return end
  local c = _G.F2.c or {0,0,0,0}
  emu.print_error(string.format("DACKCPU %.1f n=%d pc=%08X lastdma=%.1f dinsn=%d dmemq=%d dicmiss=%d ddcmiss=%d", us(), _G.F2.n, pc, _G.F2.last,
    st("TINSN") - c[1], st("TMEM") - c[2], st("TICMISS") - c[3], st("TDCMISS") - c[4]))
end)
_G.F2.g = sp:install_write_tap(0x36008004, 0x36008007, "gpio", function(off, data, mask)
  emu.print_error(string.format("GPIOW %.1f data=%08X mask=%08X pc=%08X", us(), data, mask, cpu.state["PC"].value))
end)
_G.F2.r = sp:install_read_tap(0x98020008, 0x9802000b, "fifor", function(off, data, mask)
  if (mask & 0x00ff0000) == 0 then return end
  emu.print_error(string.format("FDCR %.1f data=%02X", us(), (data >> 16) & 0xff))
end)
_G.F2.i = sp:install_write_tap(0x3400013c, 0x34000163, "icr", function(off, data, mask)
  local t = us() - (_G.F2.last or 0)
  if t < 200 then
    local function st(n) local e = cpu.state[n]; return e and e.value or 0 end
    local c = _G.F2.c or {0,0,0,0}
    emu.print_error(string.format("ICRW +%.1f off=%08X data=%08X mask=%08X pc=%08X dinsn=%d", t, off, data, mask, cpu.state["PC"].value, st("TINSN") - c[1]))
  end
end)
_G.F2.p = sp:install_read_tap(0x34000160, 0x34000163, "g18r", function(off, data, mask)
  local t = us() - (_G.F2.last or 0)
  if t < 120 and (data & 0x10) ~= 0 then
    emu.print_error(string.format("G18R +%.1f data=%08X pc=%08X", t, data, cpu.state["PC"].value))
  end
end)
