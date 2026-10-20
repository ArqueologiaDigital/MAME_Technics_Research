-- aw_tap44.lua -- -bios sp7001 with the Another World card: press SD CARD LOAD at 12 s and log, per PC, every read and
-- write of the IC23 window above its 256 KB (0x44040000-0x44FFFFFF, 0x84040000-0x84FFFFFF) until 30 s; prints
-- the top 10 PCs of each with their address range. With IC23 repeating every 256 KB, those all land on IC23.
local M = manager.machine; local cpu = M.devices[":maincpu"]; local sp = cpu.spaces["program"]
local W, R = {}, {}
local function note(t, off) local pc = cpu.state["PC"].value; local k = string.format("%08x", pc)
  local e = t[k]; if not e then e = {n = 0, lo = off, hi = off}; t[k] = e end
  e.n = e.n + 1; if off < e.lo then e.lo = off end; if off > e.hi then e.hi = off end end
_G.TW = sp:install_write_tap(0x44040000, 0x44ffffff, "w44", function(o, d, m) note(W, o) end)
_G.TW2 = sp:install_write_tap(0x84040000, 0x84ffffff, "w84", function(o, d, m) note(W, o) end)
_G.TR = sp:install_read_tap(0x44040000, 0x44ffffff, "r44", function(o, d, m) note(R, o); return d end)
_G.TR2 = sp:install_read_tap(0x84040000, 0x84ffffff, "r84", function(o, d, m) note(R, o); return d end)
local SD
for _, p in pairs(M.ioport.ports) do for name, f in pairs(p.fields) do if name:upper():find("SD CARD") then SD = f end end end
local st = 0
_G.TN = emu.add_machine_frame_notifier(function()
  local t = M.time:as_double()
  if st == 0 and t > 12 then SD:set_value(1); st = 1 end
  if st == 1 and t > 12.4 then SD:set_value(0); st = 2 end
  if st == 2 and t > 30 then st = 3
    for name, tb in pairs({writes = W, reads = R}) do
      local ks = {}; for k, e in pairs(tb) do ks[#ks + 1] = {k, e} end
      table.sort(ks, function(a, b) return a[2].n > b[2].n end)
      for i = 1, math.min(10, #ks) do local e = ks[i][2]
        emu.print_error(string.format("TAP %s pc=%s n=%d range=%08x-%08x", name, ks[i][1], e.n, e.lo, e.hi)) end
    end
    M:exit()
  end
end)
