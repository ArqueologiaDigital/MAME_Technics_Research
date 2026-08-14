-- env1.lua: navigate to SOUND EDIT -> AMPLITUDE EDIT -> ENVELOPE page, snapshot each
-- screen, tap TG group-0 writes, play C4 to capture the baseline r0..rF block.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

-- ---- TG write tap (both TGs), captures full group-0 register block per note ----
local tg_addr = {0,0}
local watching = false
local cap = {}          -- list of {tg,reg,data}
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
  for _,f in pairs(mac.ioport.ports[":KEYS0"].fields) do
    if f.name == name then f:set_value(v); return true end end
  log("NOKEY "..name); return false
end

local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end
local function press(t, tag, mask, desc)
  at(t, desc.." DOWN", function() local f=fld(tag,mask) if f then f:set_value(1) end end)
  at(t+0.35, desc.." UP", function() local f=fld(tag,mask) if f then f:clear_value() end end)
end
local shots = 0
local function snap(t, desc)
  at(t, "", function() mac.video:snapshot(); shots = shots + 1
    log(("SNAP#%d %s"):format(shots-1, desc)) end)
end

snap (22.0, "HOME")
press(23.0, ":cpanel:CPR_SEG0", 0x04, "PROGRAM-MENUS")
snap (25.0, "PROGRAM-MENUS")
press(25.5, ":cpanel:CPR_SEG5", 0x10, "LCDR1(SOUND EDIT?)")
snap (27.5, "AFTER-LCDR1")
press(28.0, ":cpanel:CPL_SEG0", 0x20, "LCDL3(AMPLITUDE?)")
snap (30.0, "AFTER-LCDL3")
press(30.5, ":cpanel:CPC_SEG11", 0x10, "PAGE-UP")
snap (32.5, "AFTER-PAGEUP")
-- baseline note capture on the edit screen
at   (33.5, "watch on", function() watching = true; cap = {} end)
at   (34.0, "C4 down", function() setkey("Key C4", 1) end)
at   (35.5, "C4 up",   function() setkey("Key C4", 0) end)
at   (37.0, "dump", function()
  watching = false
  log(("CAPTURED %d TG writes"):format(#cap))
  for i, w in ipairs(cap) do
    if i <= 200 then log(("TGW %s %04X=%04X"):format(w.tg, w.reg, w.data)) end
  end
end)
at   (38.0, "exit", function() mac:exit() end)

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
log("env1 armed")
