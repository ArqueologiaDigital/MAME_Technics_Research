-- LIFE-1 probe: start the rhythm, count gates (0x81xx) and frees (0x7E00) per channel,
-- and sample the number of channels that are gated-but-not-freed over time.
local mach = manager.machine
local prog = mach.devices[":subcpu"].spaces["program"]
local f = io.open(os.getenv("LIFEOUT") or "/tmp/life.log", "w")
local function L(s) f:write(s.."\n"); f:flush() end
local reg = 0
local gate, free = {}, {}
local live = {}          -- ch -> true while gated and not yet freed
local nlive, maxlive = 0, 0
for i=0,63 do gate[i]=0; free[i]=0; live[i]=false end
_G._r1 = prog:install_write_tap(0x100000, 0x100001, "a", function(o,d,m) reg = d & 0xffff; return nil end)
_G._r2 = prog:install_write_tap(0x100002, 0x100003, "d", function(o,d,m)
  local a = reg & 0xffff
  if (a >> 8) == 0 and ((a >> 6) & 3) == 0 then
    local ch = a & 0x3f
    local dd = d & 0xffff
    if (dd & 0xff00) == 0x8100 then
      gate[ch] = gate[ch] + 1
      if not live[ch] then live[ch]=true; nlive=nlive+1; if nlive>maxlive then maxlive=nlive end end
    elseif dd == 0x7e00 then
      free[ch] = free[ch] + 1
      if live[ch] then live[ch]=false; nlive=nlive-1 end
    end
  end
  return nil end)
local function press(port, mask, down)
  local p = mach.ioport.ports[":cpanel:" .. port]
  if not p then L("NOPORT " .. port); return end
  for _, fl in pairs(p.fields) do if fl.mask == mask then fl:set_value(down); return end end
end
local q = {}
local function AT(t, fn) q[#q+1] = {t, fn, false} end
AT(20.0, function() L("START"); press("CPR_SEG8", 0x20, 1) end)
AT(20.2, function() press("CPR_SEG8", 0x20, 0) end)
for i=1,9 do AT(21.0+i*2.0, function() L(string.format("t=%.1f live=%d max=%d", mach.time:as_double(), nlive, maxlive)) end) end
AT(40.0, function() L("STOP"); press("CPR_SEG8", 0x20, 1) end)
AT(40.2, function() press("CPR_SEG8", 0x20, 0) end)
AT(42.0, function()
  local tg, tf, used = 0, 0, 0
  for i=0,63 do tg=tg+gate[i]; tf=tf+free[i]; if gate[i]>0 then used=used+1 end end
  L(string.format("TOTAL gates=%d frees=%d channels-used=%d peak-simultaneously-live=%d final-live=%d", tg, tf, used, maxlive, nlive))
  for i=0,63 do if gate[i]>0 or free[i]>0 then L(string.format("  ch%02d gate=%d free=%d live=%s", i, gate[i], free[i], tostring(live[i]))) end end
  mach:exit() end)
_G._n = emu.add_machine_frame_notifier(function()
  local t = mach.time:as_double()
  for _, e in ipairs(q) do if (not e[3]) and t >= e[1] then e[3]=true; e[2]() end end
end)
L("life armed")
