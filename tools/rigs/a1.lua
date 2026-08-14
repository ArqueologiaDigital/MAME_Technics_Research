-- a1.lua: r4..rA damp-bank investigation (queue item A1, 2026-07-20)
-- Part 1: capture the full group-0 note-on block (r0..rD) for MANY contrasting
--         factory sounds (16 sound-group defaults + 8 piano-group variants).
-- Part 2: FILTER EDIT screens -- page 1/4 CUTOFF/RESO and page 3/4 FILTER
--         ENVELOPE column sweeps; PITCH EDIT page 2/3 PITCH ENVELOPE sweep.
--         Pixel-verify every screen state via snapshots.
-- Gotchas honored: taps installed after t>=25; keybed press via :KEYS1 mask 0x0100.
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
      if watching and (a & 0xff00) ~= 0xfc00 then
        if a < 0x0400 or (a >= 0x1c00 and a < 0x2000) then
          cap[#cap+1] = ("%s%04X=%04X"):format(label, a, d)
        end
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

-- capture one C4 note (on 1.2 s, off, watch 1.2 s more for release traffic)
local function note(t, label)
  at(t, "", function() watching = true; cap = {} end)
  at(t+0.15, "", function()
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:set_value(1) end end
  end)
  at(t+1.35, "", function()
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:clear_value() end end
  end)
  at(t+2.45, "", function()
    watching = false
    log(("CAP %s n=%d: %s"):format(label, #cap, table.concat(cap, " ")))
  end)
  return t + 2.7
end

-- soft keys (normSeg map)
local SOFT = {
  L1 = {":cpanel:CPL_SEG0", 0x02}, L2 = {":cpanel:CPL_SEG0", 0x08},
  L3 = {":cpanel:CPL_SEG0", 0x20}, L4 = {":cpanel:CPL_SEG0", 0x01},
  L5 = {":cpanel:CPL_SEG0", 0x04},
  R1 = {":cpanel:CPR_SEG5", 0x10}, R2 = {":cpanel:CPR_SEG5", 0x20},
  R3 = {":cpanel:CPR_SEG7", 0x01}, R4 = {":cpanel:CPR_SEG6", 0x01},
}
local function soft(t, key, desc) press(t, SOFT[key][1], SOFT[key][2], desc) end

at(25.0, "install taps", function()
  _G.t1 = mktap(0x98040000, 1, "M", "tgA")
  _G.t2 = mktap(0x98050000, 2, "S", "tgB")
end)

-- ============ PART 1: sound-group defaults ====================================
-- authoritative bindings = the driver's cpanel PORT_NAMEs (kn7000_cpanel.cpp)
local groups = {
  {":cpanel:CPR_SEG4", 0x10, "PIANO"},
  {":cpanel:CPR_SEG3", 0x10, "GUITAR"},
  {":cpanel:CPR_SEG2", 0x10, "MALLET"},
  {":cpanel:CPR_SEG1", 0x10, "WORLD"},
  {":cpanel:CPR_SEG0", 0x10, "STRINGS_VOCAL"},
  {":cpanel:CPR_SEG9", 0x08, "BRASS"},
  {":cpanel:CPR_SEG8", 0x08, "SAX_WOODWIND"},
  {":cpanel:CPR_SEG7", 0x08, "ORGAN_ACCORD"},
  {":cpanel:CPR_SEG4", 0x20, "DIGITAL_DRAWBAR"},
  {":cpanel:CPR_SEG3", 0x20, "TAB_ORGAN"},
  {":cpanel:CPR_SEG2", 0x20, "ACCORDION_REG"},
  {":cpanel:CPR_SEG1", 0x20, "PAD"},
  {":cpanel:CPR_SEG0", 0x20, "SYNTH"},
  {":cpanel:CPR_SEG9", 0x04, "BASS"},
  {":cpanel:CPR_SEG8", 0x04, "DRUMKITS"},
}
local t = 26.0
for _, g in ipairs(groups) do
  press(t, g[1], g[2], "GROUP "..g[3]); t = t + 1.3
  t = note(t, "G:"..g[3])
end
snap(t, "after group sweep")

-- piano-group variants: back to PIANO, select 8 sounds via soft keys
t = t + 0.5
press(t, ":cpanel:CPR_SEG4", 0x10, "GROUP PIANO"); t = t + 1.3
snap(t, "piano list")
for _, k in ipairs({"L1","L2","L3","L4","R1","R2","R3","R4"}) do
  soft(t, k, "PIANO variant "..k); t = t + 1.2
  t = note(t, "P:"..k)
end
snap(t, "after piano variants")

-- ============ PART 2: FILTER / PITCH edit screens =============================
-- back to Concert Grand (L1), then PROGRAM MENUS -> SOUND EDIT -> FILTER
t = t + 0.5
soft(t, "L1", "select Concert Grand"); t = t + 1.5
press(t, ":cpanel:CPR_SEG0", 0x04, "PROGRAM MENUS"); t = t + 1.8
press(t, ":cpanel:CPR_SEG5", 0x10, "SOUND EDIT (LCDR1)"); t = t + 1.8
snap(t, "sound edit menu"); t = t + 0.4
soft(t, "L5", "FILTER (LCDL5 guess 0x04)"); t = t + 1.8
snap(t, "filter page 1/4"); t = t + 0.4

-- baseline note on FILTER 1/4
t = note(t, "F1:baseline")
-- sweep: hold each balance column up 3.0 s (auto-repeat), snapshot, note
local cols = {
  {":cpanel:CPC_SEG8", 0x01, "PART3up"},
  {":cpanel:CPC_SEG8", 0x04, "PART4up"},
  {":cpanel:CPC_SEG8", 0x10, "PART5up"},
  {":cpanel:CPC_SEG8", 0x40, "PART6up"},
}
for _, c in ipairs(cols) do
  press(t, c[1], c[2], "F1 sweep "..c[3], 3.0); t = t + 3.4
  snap(t, "F1 after "..c[3]); t = t + 0.4
  t = note(t, "F1:"..c[3])
end

-- FILTER page 3/4 (FILTER ENVELOPE): PAGE+ twice
press(t, ":cpanel:CPC_SEG11", 0x10, "PAGE+"); t = t + 1.0
press(t, ":cpanel:CPC_SEG11", 0x10, "PAGE+"); t = t + 1.2
snap(t, "filter page 3/4"); t = t + 0.4
t = note(t, "F3:baseline")
local cols3 = {
  {":cpanel:CPC_SEG8", 0x04, "PART4up"},   -- likely ATK (START POINT=PART3?)
  {":cpanel:CPC_SEG8", 0x10, "PART5up"},
  {":cpanel:CPC_SEG9", 0x01, "PART7up"},
  {":cpanel:CPC_SEG9", 0x10, "PART9up"},
}
for _, c in ipairs(cols3) do
  press(t, c[1], c[2], "F3 sweep "..c[3], 3.0); t = t + 3.4
  snap(t, "F3 after "..c[3]); t = t + 0.4
  t = note(t, "F3:"..c[3])
end

-- PITCH ENVELOPE: EXIT to SOUND EDIT menu, PITCH (L4), PAGE+ to 2/3
press(t, ":cpanel:CPC_SEG11", 0x80, "EXIT"); t = t + 1.5
snap(t, "back at sound edit menu"); t = t + 0.4
soft(t, "L4", "PITCH (LCDL4)"); t = t + 1.8
press(t, ":cpanel:CPC_SEG11", 0x10, "PAGE+"); t = t + 1.2
snap(t, "pitch page 2/3"); t = t + 0.4
t = note(t, "P2:baseline")
local colsp = {
  {":cpanel:CPC_SEG8", 0x04, "PART4up"},
  {":cpanel:CPC_SEG9", 0x04, "PART8up"},
}
for _, c in ipairs(colsp) do
  press(t, c[1], c[2], "P2 sweep "..c[3], 3.0); t = t + 3.4
  snap(t, "P2 after "..c[3]); t = t + 0.4
  t = note(t, "P2:"..c[3])
end

at(t + 1.0, "done", function() log("A1 RUN DONE"); mac:exit() end)

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
log("a1.lua armed")
