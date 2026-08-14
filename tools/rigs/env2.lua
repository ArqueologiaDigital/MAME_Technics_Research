-- env2.lua: ENVELOPE screen interaction probe.
-- Verify: balance up/down buttons edit the columns (ATK=PART3 ... SUSTAIN=PART10),
-- hold=auto-repeat?, DATA dial effect, and that the TG tap sees r-block on C4.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

local tg_addr = {0,0}
local watching = false
local cap = {}
local function tap(base, idx, label)
  prog:install_write_tap(base, base+3, "tgenv"..idx, function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then tg_addr[idx] = data & 0xffff end
    if (mask & 0xffff0000) ~= 0 then
      local a = tg_addr[idx]; local d = (data>>16) & 0xffff
      if watching and (a & 0xff00) ~= 0xfc00 then
        cap[#cap+1] = {tg=label, reg=a, data=d}
      end
    end
    return nil
  end)
end
_G.envtap1 = tap(0x98040000, 1, "M")
_G.envtap2 = tap(0x98050000, 2, "S")

local function fld(tag, mask)
  local p = mac.ioport.ports[tag]
  if not p then log("NOPORT "..tag); return nil end
  for _, f in pairs(p.fields) do if f.mask == mask then return f end end
  log(("NOFIELD %s %02X"):format(tag, mask)); return nil
end
local function setkey(name, v)
  for pi = 0, 4 do
    local p = mac.ioport.ports[":KEYS"..pi]
    if p then
      for _,f in pairs(p.fields) do
        if f.name == name then f:set_value(v); return true end
      end
    end
  end
  log("NOKEY "..name); return false
end

local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end
local function press(t, tag, mask, desc, hold)
  hold = hold or 0.35
  at(t, desc.." DOWN", function() local f=fld(tag,mask) if f then f:set_value(1) end end)
  at(t+hold, desc.." UP", function() local f=fld(tag,mask) if f then f:clear_value() end end)
end
local shots = 0
local function snap(t, desc)
  at(t, "", function() mac.video:snapshot(); shots = shots + 1
    log(("SNAP#%d %s"):format(shots-1, desc)) end)
end

-- navigate to ENVELOPE (proven path)
press(23.0, ":cpanel:CPR_SEG0", 0x04, "PROGRAM-MENUS")
press(25.0, ":cpanel:CPR_SEG5", 0x10, "SOUND-EDIT")
press(27.0, ":cpanel:CPL_SEG0", 0x20, "AMPLITUDE")
press(29.0, ":cpanel:CPC_SEG11", 0x10, "PAGE-UP")
snap (31.0, "ENVELOPE-baseline")

-- probe 1: single tap PART3-UP (expect ATK 0 -> 1)
press(32.0, ":cpanel:CPC_SEG8", 0x01, "P3UP-once")
snap (33.5, "AFTER-P3UP-once")
-- probe 2: hold PART3-UP 3 s (auto-repeat?)
press(34.0, ":cpanel:CPC_SEG8", 0x01, "P3UP-hold3", 3.0)
snap (38.0, "AFTER-P3UP-hold3")
-- probe 3: DATA dial +4 steps
at   (39.0, "dial+4", function() local f=fld(":DIAL",0xff) if f then f:set_value(4) end end)
at   (39.4, "dial+8", function() local f=fld(":DIAL",0xff) if f then f:set_value(8) end end)
snap (41.0, "AFTER-DIAL+8")
-- probe 4: PART6-UP once (expect SUS1 0 -> 1)
press(42.0, ":cpanel:CPC_SEG8", 0x40, "P6UP-once")
snap (43.5, "AFTER-P6UP-once")
-- probe 5: play C4 with the tap armed (validate capture on the edit screen)
at   (44.5, "watch on", function() watching = true; cap = {} end)
at   (45.0, "C4 down", function() setkey("Key C4", 1) end)
at   (46.5, "C4 up",   function() setkey("Key C4", 0) end)
at   (48.0, "dump", function()
  watching = false
  log(("CAPTURED %d TG writes"):format(#cap))
  for i, w in ipairs(cap) do
    if i <= 250 then log(("TGW %s %04X=%04X"):format(w.tg, w.reg, w.data)) end
  end
end)
at   (49.0, "exit", function() mac:exit() end)

local i = 1
emu.register_periodic(function()
  local t = mac.time.seconds + mac.time.attoseconds/1e18
  while i <= #acts and t >= acts[i].t do
    local a = acts[i]; i = i + 1
    local ok, err = pcall(a.fn)
    if not ok then log("ERR "..a.desc..": "..tostring(err))
    elseif a.desc ~= "" then log(("[%5.1f] %s"):format(t, a.desc)) end
  end
end)
log("env2 armed")
