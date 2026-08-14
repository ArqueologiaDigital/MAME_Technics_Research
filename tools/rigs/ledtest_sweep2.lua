-- Find TEMPO/PROGRAM (PANEL MEMORY SET lights the whole CPR bank) + probe the SD LEDs.
-- Forces the LED-test RAM flag at t=16 so it can self-run; if you enter the real F3+F4 test it also works.
-- Output -> /home/fsanches/compartilhado/kn7000-emulator/ledtest_sweep2.out
_G.s2 = _G.s2 or {}
local mach = manager.machine
local out  = mach.output
local prg  = mach.devices[":maincpu"].spaces["program"]
local F = io.open("/home/fsanches/compartilhado/kn7000-emulator/ledtest_sweep2.out", "w")
local function log(s) F:write(s.."\n"); F:flush() end
local function fld(n) for _,p in pairs(mach.ioport.ports) do local x=p.fields[n]; if x then return x end end end
local PMS = fld("SOUND SET (PANEL MEMORY SET) (SW6)")
local SDP = fld("SD PLAY/PAUSE")
local TC  = fld("TECHNI-CHORD (SW0)")

local function litset(bank, n) local t={} for i=0,n do if (out:get_value(bank..i) or 0)~=0 then t[#t+1]=i end end return t end
local function fmt(l) return "{"..table.concat(l,",").."}" end
local function toset(l) local s={} for _,v in ipairs(l) do s[v]=true end return s end
local function delta(prev,curl) local r={} for _,v in ipairs(curl) do if not prev[v] then r[#r+1]=v end end return fmt(r) end
local function tsec() return mach.time.seconds + mach.time.attoseconds/1e18 end

local base_cpr = {}
local sched = {
  {16.0, function() log("[t=16] forcing test flag (self-run); real F3+F4 also fine") end},
  {19.0, function() base_cpr = toset(litset("cpr_led",255)); log("[t=19] baseline cpr = "..fmt(litset("cpr_led",255))) end},
  {20.0, function() if PMS then PMS:set_value(1) end end},
  {21.6, function()
      log("PANEL MEMORY SET -> full cpr = "..fmt(litset("cpr_led",255)))
      log("PANEL MEMORY SET -> NEW cpr  = "..delta(base_cpr, litset("cpr_led",255))) end},
  {22.0, function() if PMS then PMS:set_value(0) end end},
  {23.5, function() local pc=toset(litset("cpl_led",63)); local cc=toset(litset("cpc_led",127)); local rc=toset(litset("cpr_led",255))
      if SDP then SDP:set_value(1) end
      _G.s2.pre = {pc=pc, cc=cc, rc=rc} end},
  {25.1, function()
      log("SD PLAY/PAUSE -> NEW cpl = "..delta(_G.s2.pre.pc, litset("cpl_led",63))
        .."  cpc = "..delta(_G.s2.pre.cc, litset("cpc_led",127))
        .."  cpr = "..delta(_G.s2.pre.rc, litset("cpr_led",255))) end},
  {25.5, function() if SDP then SDP:set_value(0) end end},
  {26.5, function() _G.s2.tcpre = toset(litset("cpr_led",255)); if TC then TC:set_value(1) end end},
  {28.1, function() log("TECHNI-CHORD (sanity) -> NEW cpr = "..delta(_G.s2.tcpre, litset("cpr_led",255))) end},
  {28.5, function() if TC then TC:set_value(0) end; log("[t=28.5] DONE") end},
}
local i = 1
_G.s2.n = emu.add_machine_frame_notifier(function()
  local t = tsec()
  if t >= 16.0 then prg:write_u8(0x5006BFB2, 1) end   -- hold the LED-test flag
  while i <= #sched and t >= sched[i][1] do sched[i][2](); i = i + 1 end
end)
