-- SD SAVE round-trip, leg 2 (proven 2026-07-19): fresh boot (default rhythm) -> SD LOAD
-- browser -> LOAD folder01/song01 (saved with the BALLAD rhythm by sd_roundtrip_save.lua)
-- -> the final home snapshot shows RHYTHM "BALLAD 01 ?" instead of the boot default,
-- proving the panel state persisted through the card image.
-- Run: DISPLAY=:0 ./run.sh -window -harddisk sdcard_work.img -autoboot_script sd_roundtrip_load.lua -seconds_to_run 47
-- Flow: home -> SD CARD LOAD toggle (CPR_SEG1 0x80) -> SD MENU -> LCDR1 = SD LOAD browser
-- (LOAD=LCDR1 row 1) -> LCDR1 LOAD executes (~95k SPI reads), returns home with loaded state.
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
_G.SPI_R = 0
_G.T1 = prog:install_read_tap(0x9805000C, 0x9805000F, "spir", function() _G.SPI_R = _G.SPI_R + 1 return nil end)
local function snap(tag) V:snapshot(); log(("%s r=%d"):format(tag, _G.SPI_R)) end
local function press(f) if f then f:set_value(1) end end
local function rel(f) if f then f:clear_value() end end
local steps = {
  {26.0, function() snap("S1-home-default"); press(SDTOG) end},
  {26.4, function() rel(SDTOG) end},
  {28.5, function() snap("S2-menu"); press(LCDR1) end},     -- LOAD
  {28.9, function() rel(LCDR1) end},
  {32.0, function() snap("S3-loadbrowser"); press(LCDR1) end}, -- LOAD execute
  {32.4, function() rel(LCDR1) end},
  {35.5, function() snap("S4-afterload1") end},
  {40.0, function() snap("S5-afterload2") end},
  {46.0, function() snap("S6-final"); log("RUN E COMPLETE") end},
}
local i = 1
emu.register_periodic(function()
  if i > #steps then return end
  local t = mac.time.seconds + mac.time.attoseconds / 1e18
  if t >= steps[i][1] then steps[i][2](); i = i + 1 end
end)
