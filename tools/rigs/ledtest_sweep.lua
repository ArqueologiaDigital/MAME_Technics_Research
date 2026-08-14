-- LED-test button->LED sweep (REAL test). Run MAME with this as -autoboot_script, then hold F3+F4 at
-- boot to enter the LED test. From t=28s this auto-presses each CPC / SD / sample button and logs which
-- cpl/cpc/cpr LED lights (LEDs accumulate in the test, so we log the DELTA per press). It does NOT touch
-- the test flag (the screenless RAM-flag mode doesn't drive the CPC board -- your real test does).
-- Output -> /home/fsanches/compartilhado/kn7000-emulator/ledtest_sweep.out   (Claude reads this).
_G.lts = _G.lts or {}
local mach = manager.machine
local out  = mach.output
local F = io.open("/home/fsanches/compartilhado/kn7000-emulator/ledtest_sweep.out", "w")
local function log(s) F:write(s.."\n"); F:flush() end

local function fld(n) for _,p in pairs(mach.ioport.ports) do local x=p.fields[n]; if x then return x end end end
local targets = {}
local function add(nm) local f=fld(nm); if f then targets[#targets+1]={nm=nm,f=f} end end
add("OTHER PARTS/TG (SW0)")
local mu,md = {},{}
for _,p in pairs(mach.ioport.ports) do for nm,f in pairs(p.fields) do
  local u=nm:match("MUTE UP (%d+) %("); local d=nm:match("MUTE DOWN (%d+) %(")
  if u then mu[tonumber(u)]={nm=nm,f=f} end
  if d then md[tonumber(d)]={nm=nm,f=f} end
end end
for i=1,8 do if mu[i] then targets[#targets+1]=mu[i] end; if md[i] then targets[#targets+1]=md[i] end end
add("SD VOLUME -"); add("SD VOLUME +"); add("SD STOP"); add("SD PLAY/PAUSE")
add("SD SKIP/SEARCH <<"); add("SD SKIP/SEARCH >>")
add("TECHNI-CHORD (SW0)")   -- CPR sanity: known press-lit LED (should log cpr_led33)

local function onset()
  local t={}
  for _,bn in ipairs({{"cpl_led",63},{"cpc_led",127},{"cpr_led",127}}) do
    for i=0,bn[2] do if (out:get_value(bn[1]..i) or 0)~=0 then t[bn[1]..i]=true end end
  end
  return t
end
local function newkeys(prev,cur) local r={} for k in pairs(cur) do if not prev[k] then r[#r+1]=k end end table.sort(r); return table.concat(r,",") end
local function tsec() return mach.time.seconds + mach.time.attoseconds/1e18 end

local START = 28.0    -- give time to boot + enter the LED test (F3+F4)
local slot  = 2.0
local started, idx, phase, prev = false, 1, 0, {}

_G.lts.n = emu.add_machine_frame_notifier(function()
  local t = tsec()
  if t < START then return end
  if not started then started=true; prev=onset(); log(string.format("[t=%.1f] sweep start; screen-baseline LEDs = %s", t, newkeys({},prev))) end
  local k = idx
  if k > #targets then
    if phase ~= 9 then log(string.format("[t=%.1f] SWEEP DONE (%d buttons).", t, #targets)); phase=9 end
    return
  end
  local ts = START + (k-1)*slot
  if phase==0 and t >= ts then targets[k].f:set_value(1); phase=1
  elseif phase==1 and t >= ts+1.3 then
    local cur=onset(); log(string.format("%-34s -> %s", targets[k].nm, newkeys(prev,cur))); prev=cur; phase=2
  elseif phase==2 and t >= ts+1.6 then targets[k].f:set_value(0); idx=idx+1; phase=0 end
end)
