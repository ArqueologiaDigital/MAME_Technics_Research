-- Run A: enter SD MENU via SD CARD LOAD, test re-press idempotency, then LCDL1-5
local mac = manager.machine
local shots = 0
local function log(s) emu.print_error(s) end
local function fld(tag, mask)
  local p = mac.ioport.ports[tag]
  if not p then log("NOPORT "..tag); return nil end
  for _,f in pairs(p.fields) do if f.mask == mask then return f end end
  log(("NOFIELD %s %02X"):format(tag, mask)); return nil
end
local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end
local function press(t, tag, mask, desc)
  at(t, desc.." DOWN", function() local f=fld(tag,mask) if f then f:set_value(1) end end)
  at(t+0.4, desc.." UP", function() local f=fld(tag,mask) if f then f:clear_value() end end)
end
local function snap(t, desc)
  at(t, "", function() mac.video:snapshot(); shots=shots+1
    log(("SNAP#%04d %s"):format(shots-1, desc)) end)
end

press(24.0, ":cpanel:CPR_SEG1", 0x80, "SDLOAD-enter")
snap (26.5, "menu-baseline")
press(27.0, ":cpanel:CPR_SEG1", 0x80, "SDLOAD-repress")
snap (29.2, "menu-after-repress")

local lmask = {0x02, 0x08, 0x20, 0x01, 0x04}
for k = 1, 5 do
  local base = 30 + (k-1)*6
  press(base,       ":cpanel:CPL_SEG0", lmask[k], ("LCDL%d"):format(k))
  snap (base+1.8,   ("after-LCDL%d"):format(k))
  press(base+2.4,   ":cpanel:CPR_SEG1", 0x80, "SDLOAD-recover")
  snap (base+4.6,   ("recover-after-LCDL%d"):format(k))
end

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
log("sdnav_a armed")
