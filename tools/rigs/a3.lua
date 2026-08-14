-- a3.lua: LIVE DSP experiments (queue item A, 2026-07-20)
--  A3: unit-role capture -- log host->DSP upload blocks (PM/DM targets) + the
--      DspEffectSelect param-block writes while switching REVERB/CHORUS/MULTI/
--      SOUND-DSP types on the panel GUI.
--  A2: u8 EQ DM coefficient-bank dump at flat vs edited EQ.
-- Gotchas honored: taps installed AFTER boot (t>=25); pixel-verify via snapshots;
-- single MAME instance on the SD image.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local dsp  = mac.devices[":dsp"]
local dspdm, dsppm
if dsp then
  dspdm = dsp.spaces["data"]
  dsppm = dsp.spaces["program"]
end

local function now() return mac.time.seconds + mac.time.attoseconds/1e18 end

-- ============ host->DSP upload capture (index 0x98000000 / data 0x9C000000) ====
local curidx = 0
local addrbuf = {}
local pending_addr, pending_cnt = nil, nil
local blocks = {}      -- {t, mode, addr, cnt, halves={}}
local curblk = nil
local capture_on = false

local function on_idx(h)  curidx = h end
local function on_dat(h)
  if not capture_on then return end
  if curidx == 0x40 then
    addrbuf[#addrbuf+1] = h
    if #addrbuf >= 2 then pending_addr = (addrbuf[2]<<16)|addrbuf[1]; addrbuf = {} end
  elseif curidx == 0x42 then
    pending_cnt = h
  elseif curidx == 0x1c then
    if h == 0xa1 or h == 0x41 then
      curblk = {t=now(), mode=(h==0xa1) and "PM" or "DM", addr=pending_addr or -1,
                cnt=pending_cnt or -1, halves={}}
      blocks[#blocks+1] = curblk
    else
      curblk = nil
    end
    addrbuf = {}
  elseif curidx == 0x04 then
    if curblk and #curblk.halves < 600 then curblk.halves[#curblk.halves+1] = h end
  end
end

_G._keep = {}
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
end

-- ============ DspEffectSelect param-block watcher =============================
local pblock_base = nil
local function poll_pblock()
  local ok, v = pcall(function() return prog:read_u32(0x500A01E0) end)
  if not ok then return end
  if v ~= 0xFFFFFFFF and v >= 0x50000000 and v < 0x50200000 and v ~= pblock_base then
    pblock_base = v
    log(("PARAM-BLOCK allocated at %08X (t=%.1f)"):format(v, now()))
    _G._keep[3] = prog:install_write_tap(v, v + 0xB40 - 1, "pblk", function(off, data, mask)
      local rel = off - pblock_base
      local unit = rel // 0x120
      local o = rel % 0x120
      if o <= 0x0C then
        log(("PBLK t=%.2f unit=%d off=+0x%02X data=%08X mask=%08X"):format(now(), unit, o, data, mask))
      end
      return nil
    end)
  end
end

-- ============ DSP memory dumps ================================================
local function dump_u8_slab(tag)
  if not dspdm then log("NO DSP DATA SPACE") return end
  local base = 0xC000 + 8*0x4D           -- unit-8 param slab (c000..c04C)
  local parts = {}
  for i = 0, 0x4C do
    local ok, v = pcall(function() return dspdm:read_u32(base + i) end)
    parts[#parts+1] = ok and ("%08X"):format(v) or "ERR"
  end
  log(("U8SLAB %s @%04X: %s"):format(tag, base, table.concat(parts, " ")))
  -- unit-8 state slab (PM bus 0x9800+8*0x50) via DM view (PM(0x9800)==DM(0x9800))
  local sbase = 0x9800 + 8*0x50
  local sp = {}
  for i = 0, 0x1F do
    local ok, v = pcall(function() return dspdm:read_u32(sbase + i) end)
    sp[#sp+1] = ok and ("%08X"):format(v) or "ERR"
  end
  log(("U8STATE %s @%04X: %s"):format(tag, sbase, table.concat(sp, " ")))
end

local function dump_chain()
  if not dsppm then log("NO DSP PM SPACE") return end
  local parts = {}
  for _, a in ipairs({0x8080,0x8083,0x8086,0x8089,0x808C,0x808F,0x8093,0x8097,0x809D,0x80A0}) do
    local ok, v = pcall(function() return dsppm:read_u64(a) end)
    parts[#parts+1] = ok and ("%04X:%012X"):format(a, v & 0xFFFFFFFFFFFF) or (("%04X:ERR"):format(a))
  end
  log("CHAIN " .. table.concat(parts, " "))
  -- u8 slot head (0x8C00): is rec34 loaded?
  local p2 = {}
  for i = 0, 5 do
    local ok, v = pcall(function() return dsppm:read_u64(0x8C00 + i) end)
    p2[#p2+1] = ok and ("%012X"):format(v & 0xFFFFFFFFFFFF) or "ERR"
  end
  log("PM8C00 " .. table.concat(p2, " "))
end

-- ============ action scheduler ================================================
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

-- soft keys (normSeg map: SEG00=CPL_SEG0, SEG11=CPR_SEG5, SEG12=CPR_SEG6, SEG13=CPR_SEG7)
local SOFT = {
  L1 = {":cpanel:CPL_SEG0", 0x02}, L2 = {":cpanel:CPL_SEG0", 0x08},
  L3 = {":cpanel:CPL_SEG0", 0x20}, L4 = {":cpanel:CPL_SEG0", 0x01},
  L5 = {":cpanel:CPL_SEG0", 0x04},                       -- guess (DETAIL EDIT slot)
  R1 = {":cpanel:CPR_SEG5", 0x10}, R2 = {":cpanel:CPR_SEG5", 0x20},
  R3 = {":cpanel:CPR_SEG7", 0x01}, R4 = {":cpanel:CPR_SEG6", 0x01},
  R5 = {":cpanel:CPR_SEG3", 0x40},                       -- guess (LCD RIGHT 5)
}
local function soft(t, key, desc)
  local s = SOFT[key]
  marker(t - 0.1, desc .. " (" .. key .. ")")
  press(t, s[1], s[2], desc)
end

-- ================= timeline ===================================================
at(25.0, "install taps + arm capture", function()
  install_taps(); capture_on = true
end)
at(25.5, "initial dumps", function() dump_chain(); dump_u8_slab("BOOT-FLAT") end)

-- --- REVERB screen: hold REVERB (CPR_SEG3 0x04) 2.5 s
marker(26.9, "OPEN REVERB SCREEN")
press(27.0, ":cpanel:CPR_SEG3", 0x04, "hold REVERB", 2.6)
snap(30.5, "reverb screen")
local t = 31.5
local rev = {{"L1","Room1"},{"L2","Room2"},{"L3","Plate1"},{"L4","Plate2"},
             {"R1","Concert1"},{"R2","Concert2"},{"R3","Dark1"},{"R4","Dark2"}}
for _, r in ipairs(rev) do soft(t, r[1], "REVERB "..r[2]); t = t + 2.5 end
snap(t, "reverb end")

-- --- CHORUS screen: hold CHORUS (CPR_SEG5 0x04) 2.5 s
t = t + 1.0
marker(t - 0.1, "OPEN CHORUS SCREEN")
press(t, ":cpanel:CPR_SEG5", 0x04, "hold CHORUS", 2.6); t = t + 3.5
snap(t, "chorus screen"); t = t + 1.0
local cho = {{"L1","Chorus1"},{"L2","Chorus2"},{"L3","Chorus3"},{"L4","Chorus4"},
             {"R1","GM Chorus1"},{"R2","GM Chorus2"},{"R3","GM Chorus3"},{"R4","GM Chorus4"}}
for _, r in ipairs(cho) do soft(t, r[1], "CHORUS "..r[2]); t = t + 2.5 end
snap(t, "chorus end")

-- --- MULTI screen: hold MULTI (CPR_SEG4 0x04) 2.5 s
t = t + 1.0
marker(t - 0.1, "OPEN MULTI SCREEN")
press(t, ":cpanel:CPR_SEG4", 0x04, "hold MULTI", 2.6); t = t + 3.5
snap(t, "multi screen"); t = t + 1.0
soft(t, "L1", "MULTI sel L1"); t = t + 2.5
soft(t, "L2", "MULTI sel L2"); t = t + 2.5
soft(t, "R1", "MULTI sel R1"); t = t + 2.5
snap(t, "multi end")

-- --- SOUND DSP: toggle insert ON (short press), then hold to open, select two
t = t + 1.0
marker(t - 0.1, "SOUND DSP toggle ON (short press)")
press(t, ":cpanel:CPR_SEG3", 0x08, "SOUND DSP on"); t = t + 2.0
marker(t - 0.1, "OPEN SOUND DSP SCREEN")
press(t, ":cpanel:CPR_SEG3", 0x08, "hold SOUND DSP", 2.6); t = t + 3.5
snap(t, "sound dsp screen"); t = t + 1.0
soft(t, "L1", "SOUNDDSP sel L1"); t = t + 2.5
soft(t, "R1", "SOUNDDSP sel R1"); t = t + 2.5
snap(t, "sound dsp end")

-- --- EQUALIZER screen: EXIT, PROGRAM MENUS -> REVERB&EFFECT (L2) -> EQUALIZER (R5)
t = t + 1.0
press(t, ":cpanel:CPC_SEG11", 0x80, "EXIT"); t = t + 1.5
press(t, ":cpanel:CPR_SEG6", 0x40, "PROGRAM MENUS"); t = t + 2.0
snap(t, "program menus"); t = t + 0.5
soft(t, "L2", "REVERB & EFFECT menu"); t = t + 2.0
snap(t, "reverb&effect menu"); t = t + 0.5
soft(t, "R5", "EQUALIZER item"); t = t + 2.0
snap(t, "equalizer screen"); t = t + 0.5
at(t, "u8 dump flat", function() dump_u8_slab("EQ-SCREEN-FLAT") end); t = t + 1.0
soft(t, "L4", "EQ preset Treble Boost"); t = t + 2.0
snap(t, "after treble boost"); t = t + 0.5
at(t, "u8 dump tb", function() dump_u8_slab("TREBLE-BOOST") end); t = t + 1.0
soft(t, "L1", "EQ preset Flat"); t = t + 2.0
at(t, "u8 dump flat2", function() dump_u8_slab("FLAT-PRESET") end); t = t + 1.0
snap(t, "eq end")

-- ================= wrap-up ====================================================
at(t + 2.0, "summary", function()
  log(("== upload blocks captured: %d =="):format(#blocks))
  for i, b in ipairs(blocks) do
    local head = {}
    for j = 1, math.min(#b.halves, 12) do head[#head+1] = ("%04X"):format(b.halves[j]) end
    log(("BLK %3d t=%7.2f %s @%06X cnt=%d halves=%d head: %s"):format(
      i, b.t, b.mode, b.addr, b.cnt, #b.halves, table.concat(head, " ")))
  end
  -- full payload dump for DM blocks in the u8 window + small PM blocks (types)
  for i, b in ipairs(blocks) do
    if (b.mode == "DM" and b.addr >= 0xC000 and b.addr <= 0xC302) or
       (b.mode == "DM" and b.addr >= 0x9800 and b.addr < 0x9C40) then
      local all = {}
      for j = 1, #b.halves do all[#all+1] = ("%04X"):format(b.halves[j]) end
      log(("BLKFULL %3d t=%7.2f %s @%06X: %s"):format(i, b.t, b.mode, b.addr, table.concat(all, " ")))
    end
  end
  log("A3 RUN DONE")
  mac:exit()
end)

local i = 1
emu.register_periodic(function()
  poll_pblock()
  local nw = now()
  while i <= #acts and nw >= acts[i].t do
    local a = acts[i]; i = i + 1
    local ok, err = pcall(a.fn)
    if not ok then log(("ERR t=%.1f %s: %s"):format(nw, tostring(a.desc), tostring(err)))
    elseif a.desc ~= "" then log(("[%6.1f] %s"):format(nw, a.desc)) end
  end
end)
log("a3.lua armed")
