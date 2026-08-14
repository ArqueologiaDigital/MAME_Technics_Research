-- a3b.lua: A2 completion -- EQUALIZER screen u8 DM bank dump (flat vs presets),
-- with FIXED upload payload capture (payload streams into EPB0 BEFORE the DMAC
-- commit, so buffer data-port halves and attach them at the 0x1C commit).
-- Correct navigation: PROGRAM MENUS = CPR_SEG0 0x04 (driver port names are the
-- source of truth; CPR_SEG6 0x40 / CPR_SEG3 0x40 are PANEL MEMORY 2/5!).
-- LCDL1..5 = CPL_SEG0 0x02/0x08/0x20/0x01/0x04; LCDR1..5 = CPR_SEG5 0x10 /
-- CPR_SEG5 0x20 / CPR_SEG7 0x01 / CPR_SEG6 0x01 / CPR_SEG5 0x01.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local dsp  = mac.devices[":dsp"]
local dspdm = dsp and dsp.spaces["data"]

local function now() return mac.time.seconds + mac.time.attoseconds/1e18 end

-- ============ upload capture with payload =====================================
local curidx = 0
local addrbuf = {}
local pending_addr = nil
local pending_data = {}
local blocks = {}
local capture_on = false

local function on_idx(h) curidx = h end
local function on_dat(h)
  if not capture_on then return end
  if curidx == 0x40 then
    addrbuf[#addrbuf+1] = h
    if #addrbuf >= 2 then pending_addr = (addrbuf[2]<<16)|addrbuf[1]; addrbuf = {} end
  elseif curidx == 0x04 then
    if #pending_data < 800 then pending_data[#pending_data+1] = h end
  elseif curidx == 0x1c then
    if h == 0xa1 or h == 0x41 then
      blocks[#blocks+1] = {t=now(), mode=(h==0xa1) and "PM" or "DM",
                           addr=pending_addr or -1, halves=pending_data}
    end
    pending_data = {}
    addrbuf = {}
  end
end

_G._keep = {}
local pblock_base = nil
local function install_taps()
  _G._keep[1] = prog:install_write_tap(0x98000000, 0x98000003, "dspidx", function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then on_idx(data & 0xffff) end
    if (mask & 0xffff0000) ~= 0 then on_idx((data>>16) & 0xffff) end
    return nil
  end)
  _G._keep[2] = prog:install_write_tap(0x9c000000, 0x9c000003, "dspdat", function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then on_dat(data & 0xffff) end
    if (mask & 0xffff0000) ~= 0 then on_dat((data>>16) & 0xffff) end
    return nil
  end)
  local v = prog:read_u32(0x500A01E0)
  if v ~= 0xFFFFFFFF and v >= 0x50000000 and v < 0x50200000 then
    pblock_base = v
    log(("PARAM-BLOCK at %08X"):format(v))
    _G._keep[3] = prog:install_write_tap(v, v + 0xB40 - 1, "pblk", function(off, data, mask)
      local rel = off - pblock_base
      local unit = rel // 0x120
      local o = rel % 0x120
      if unit == 8 and o <= 0x10 then
        log(("PBLK8 t=%.2f off=+0x%02X data=%08X mask=%08X"):format(now(), o, data, mask))
      end
      return nil
    end)
  end
end

local function dump_u8(tag)
  local base = 0xC000 + 8*0x4D
  local parts = {}
  for i = 4, 0x19 do
    local ok, v = pcall(function() return dspdm:read_u32(base + i) end)
    parts[#parts+1] = ok and ("%08X"):format(v) or "ERR"
  end
  log(("U8BANK %s c004..c019: %s"):format(tag, table.concat(parts, " ")))
end

-- ============ scheduler =======================================================
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
local function marker(t, s) at(t, "", function() log(("=== MARK t=%.1f %s"):format(now(), s)) end) end

local SOFT = {
  L1 = {":cpanel:CPL_SEG0", 0x02}, L2 = {":cpanel:CPL_SEG0", 0x08},
  L3 = {":cpanel:CPL_SEG0", 0x20}, L4 = {":cpanel:CPL_SEG0", 0x01},
  L5 = {":cpanel:CPL_SEG0", 0x04},
  R1 = {":cpanel:CPR_SEG5", 0x10}, R2 = {":cpanel:CPR_SEG5", 0x20},
  R3 = {":cpanel:CPR_SEG7", 0x01}, R4 = {":cpanel:CPR_SEG6", 0x01},
  R5 = {":cpanel:CPR_SEG5", 0x01},
}
local function soft(t, key, desc)
  marker(t - 0.1, desc .. " (" .. key .. ")")
  press(t, SOFT[key][1], SOFT[key][2], desc)
end

at(25.0, "install taps", function() install_taps(); capture_on = true end)
press(26.0, ":cpanel:CPR_SEG0", 0x04, "PROGRAM MENUS")
soft(28.0, "L2", "REVERB & EFFECT")
snap(29.8, "reverb&effect menu")
soft(30.2, "R5", "EQUALIZER")
snap(32.0, "equalizer screen")
at(32.5, "dump flat", function() dump_u8("FLAT0") end)

local t = 33.5
for _, p in ipairs({{"L4","TrebleBoost"},{"L2","MakeUp"},{"L3","Radio"},
                    {"L5","NoHiHat"},{"L1","Flat"}}) do
  soft(t, p[1], "EQ preset "..p[2])
  snap(t + 1.4, "after "..p[2])
  at(t + 1.9, "", function() dump_u8(p[2]) end)
  t = t + 3.0
end
-- right-column keys (unknown roles: EQ ON/OFF? ORIGINAL?)
for _, p in ipairs({{"R1","Rkey1"},{"R2","Rkey2"}}) do
  soft(t, p[1], "EQ "..p[2])
  snap(t + 1.4, "after "..p[2])
  at(t + 1.9, "", function() dump_u8(p[2]) end)
  t = t + 3.0
end
-- a GAIN balance-column edit (PART3 col up, 2 s auto-repeat)
marker(t - 0.1, "GAIN col PART3 up hold")
press(t, ":cpanel:CPC_SEG8", 0x01, "PART3 up", 2.0)
snap(t + 2.6, "after gain edit")
at(t + 3.0, "", function() dump_u8("GainEdit") end)
t = t + 4.0

at(t, "summary", function()
  log(("== blocks: %d =="):format(#blocks))
  for i, b in ipairs(blocks) do
    local all = {}
    for j = 1, math.min(#b.halves, 80) do all[#all+1] = ("%04X"):format(b.halves[j]) end
    log(("BLK %3d t=%7.2f %s @%06X n=%d: %s"):format(i, b.t, b.mode, b.addr, #b.halves,
        table.concat(all, " ")))
  end
  log("A3B RUN DONE")
  mac:exit()
end)

local i = 1
emu.register_periodic(function()
  local nw = now()
  while i <= #acts and nw >= acts[i].t do
    local a = acts[i]; i = i + 1
    local ok, err = pcall(a.fn)
    if not ok then log(("ERR t=%.1f %s: %s"):format(nw, tostring(a.desc), tostring(err)))
    elseif a.desc ~= "" then log(("[%6.1f] %s"):format(nw, a.desc)) end
  end
end)
log("a3b.lua armed")
