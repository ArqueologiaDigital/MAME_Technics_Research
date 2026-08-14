-- a1b.lua: pin the remaining r4..rA fields (follow-up to a1.lua).
-- F3 = FILTER ENVELOPE page: PART3=START POINT, PART10=RLS, PART12=CUTOFF ADJUST,
--   PART6=DCY1 (expect r9 hi).  P2 = PITCH ENVELOPE: PART6=DCY1 (expect r5 hi),
--   PART7=SUS1 (expect r5 lo).
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

local tg_addr = {0,0}
local watching = false
local cap = {}
local function mktap(base, idx, label, name)
  return prog:install_write_tap(base, base+3, name, function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then tg_addr[idx] = data & 0xffff end
    if (mask & 0xffff0000) ~= 0 then
      local a = tg_addr[idx]; local d = (data>>16) & 0xffff
      if watching and (a & 0xff00) ~= 0xfc00 and a < 0x0400 then
        cap[#cap+1] = ("%s%04X=%04X"):format(label, a, d)
      end
    end
    return nil
  end)
end

local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end
local function press(t, tag, mask, desc, hold)
  hold = hold or 0.35
  at(t, desc, function()
    local p = mac.ioport.ports[tag]
    if not p then log("NO PORT "..tag) return end
    for _, f in pairs(p.fields) do if f.mask == mask then f:set_value(1) end end
  end)
  at(t + hold, "", function()
    local p = mac.ioport.ports[tag]
    if not p then return end
    for _, f in pairs(p.fields) do if f.mask == mask then f:clear_value() end end
  end)
end
local shots = 0
local function snap(t, desc)
  at(t, "", function()
    mac.video:snapshot(); shots = shots + 1
    log(("SNAP#%d t=%.1f %s"):format(shots-1, t, desc))
  end)
end
local function note(t, label)
  at(t, "", function() watching = true; cap = {} end)
  at(t+0.15, "", function()
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:set_value(1) end end
  end)
  at(t+1.2, "", function()
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:clear_value() end end
  end)
  at(t+2.2, "", function()
    watching = false
    log(("CAP %s n=%d: %s"):format(label, #cap, table.concat(cap, " ")))
  end)
  return t + 2.5
end

at(25.0, "taps", function()
  _G.t1 = mktap(0x98040000, 1, "M", "tgA")
  _G.t2 = mktap(0x98050000, 2, "S", "tgB")
end)

press(26.0, ":cpanel:CPR_SEG0", 0x04, "PROGRAM MENUS")
press(27.8, ":cpanel:CPR_SEG5", 0x10, "SOUND EDIT")
press(29.6, ":cpanel:CPL_SEG0", 0x04, "FILTER (LCDL5)")
press(31.4, ":cpanel:CPC_SEG11", 0x10, "PAGE+")
press(32.6, ":cpanel:CPC_SEG11", 0x10, "PAGE+")
snap(33.8, "filter page 3/4")
local t = note(34.2, "F3:base")
local sweeps = {
  {":cpanel:CPC_SEG8",  0x01, "F3:PART3-STARTPT"},
  {":cpanel:CPC_SEG10", 0x04, "F3:PART12-CUTADJ"},
  {":cpanel:CPC_SEG9",  0x40, "F3:PART10-RLS"},
  {":cpanel:CPC_SEG8",  0x40, "F3:PART6-DCY1"},
}
for _, c in ipairs(sweeps) do
  press(t, c[1], c[2], c[3].." hold", 3.0); t = t + 3.4
  snap(t, "after "..c[3]); t = t + 0.4
  t = note(t, c[3])
end
press(t, ":cpanel:CPC_SEG11", 0x80, "EXIT"); t = t + 1.5
press(t, ":cpanel:CPL_SEG0", 0x01, "PITCH (LCDL4)"); t = t + 1.8
press(t, ":cpanel:CPC_SEG11", 0x10, "PAGE+"); t = t + 1.2
snap(t, "pitch page 2/3"); t = t + 0.4
t = note(t, "P2:base")
local sweeps2 = {
  {":cpanel:CPC_SEG8", 0x40, "P2:PART6-DCY1"},
  {":cpanel:CPC_SEG9", 0x01, "P2:PART7-SUS1"},
  {":cpanel:CPC_SEG10",0x04, "P2:PART12-DEPTH"},
}
for _, c in ipairs(sweeps2) do
  press(t, c[1], c[2], c[3].." hold", 3.0); t = t + 3.4
  snap(t, "after "..c[3]); t = t + 0.4
  t = note(t, c[3])
end
at(t + 1.0, "done", function() log("A1B DONE"); mac:exit() end)

local i = 1
emu.register_periodic(function()
  local nw = mac.time.seconds + mac.time.attoseconds/1e18
  while i <= #acts and nw >= acts[i].t do
    local a = acts[i]; i = i + 1
    local ok, err = pcall(a.fn)
    if not ok then log(("ERR t=%.1f %s: %s"):format(nw, tostring(a.desc), tostring(err)))
    elseif a.desc ~= "" then log(("[%6.1f] %s"):format(nw, a.desc)) end
  end
end)
log("a1b.lua armed")
