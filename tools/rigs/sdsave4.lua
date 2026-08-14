-- sdsave4 run C: SAVE browser -> SAVE (LCDR1) -> confirm overwrite YES (LCDR3) -> watch the write.
local mac = manager.machine
local V = mac.video
local prog = mac.devices[":maincpu"].spaces["program"]
local function log(s) emu.print_error(s) end
local function fld(tag, mask)
  local p = mac.ioport.ports[tag]; if not p then log("NOPORT "..tag); return nil end
  for _, f in pairs(p.fields) do if f.mask == mask then return f end end
  log("NOFIELD "..tag); return nil
end
local SDTOG = fld(":cpanel:CPR_SEG1", 0x80)
local LCDR1 = fld(":cpanel:CPR_SEG5", 0x10)
local LCDR2 = fld(":cpanel:CPR_SEG5", 0x20)
local LCDR3 = fld(":cpanel:CPR_SEG7", 0x01)
_G.SPI_R, _G.SPI_W = 0, 0
_G.T1 = prog:install_read_tap(0x9805000C, 0x9805000F, "spir", function() _G.SPI_R = _G.SPI_R + 1 return nil end)
_G.T2 = prog:install_write_tap(0x9805000C, 0x9805000F, "spiw", function() _G.SPI_W = _G.SPI_W + 1 return nil end)
local function snap(tag) V:snapshot(); log(("%s r=%d w=%d"):format(tag, _G.SPI_R, _G.SPI_W)) end
local function press(f) if f then f:set_value(1) end end
local function rel(f) if f then f:clear_value() end end
local steps = {
  {26.0, function() snap("S1-home"); press(SDTOG) end},
  {26.4, function() rel(SDTOG) end},
  {28.5, function() snap("S2-menu"); press(LCDR2) end},
  {28.9, function() rel(LCDR2) end},
  {31.5, function() snap("S3-savemenu"); press(LCDR2) end},
  {31.9, function() rel(LCDR2) end},
  {35.0, function() snap("S4-browser"); press(LCDR1) end},  -- SAVE
  {35.4, function() rel(LCDR1) end},
  {37.5, function() snap("S5-dialog"); press(LCDR3) end},   -- YES
  {37.9, function() rel(LCDR3) end},
  {40.0, function() snap("S6-writing1") end},
  {44.0, function() snap("S7-writing2") end},
  {50.0, function() snap("S8-done") end},
  {56.0, function() snap("S9-settle"); log("RUN C COMPLETE") end},
}
local i = 1
emu.register_periodic(function()
  if i > #steps then return end
  local t = mac.time.seconds + mac.time.attoseconds / 1e18
  if t >= steps[i][1] then steps[i][2](); i = i + 1 end
end)
