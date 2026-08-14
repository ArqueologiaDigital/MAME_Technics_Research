-- b2ram.lua -- locate the per-part effect DEPTH cache: dump main RAM before and
-- after the SOUND-DSP refresh that turns the cold chorus/multi depths (0) into
-- the real ones (0x3C / 0x50). Dumps to /tmp scratchpad as raw binary.
local OUT = os.getenv("B2_OUT") or "/tmp"
local function press(p, mm, v)
  local pp = manager.machine.ioport.ports[p]
  if not pp then emu.print_error("[b2r] MISSING PORT " .. p) return end
  for _, f in pairs(pp.fields) do if f.mask == mm then f:set_value(v) end end
end
local function dump(name)
  local sp = manager.machine.devices[":maincpu"].spaces["program"]
  local f = io.open(OUT .. "/" .. name, "wb")
  local base, size, chunk = 0x50000000, 0x180000, 0x10000
  for off = 0, size - 1, chunk do
    f:write(sp:read_range(base + off, base + off + chunk - 1, 8))
  end
  f:close()
  emu.print_error("[b2r] dumped " .. name)
end
local st = 0
_G._b2r = emu.add_machine_frame_notifier(function()
  local m = manager.machine
  local mt = m.time
  local t = mt.seconds + mt.attoseconds / 1e18
  local seq = {
    {20.0, function() press(":cpanel:CPR_SEG5", 0x04, 1) end},
    {20.4, function() press(":cpanel:CPR_SEG5", 0x04, 0) end},
    {22.0, function() press(":cpanel:CPR_SEG4", 0x04, 1) end},
    {22.4, function() press(":cpanel:CPR_SEG4", 0x04, 0) end},
    {24.5, function() dump("ramA.bin") end},                       -- cold: chorus+multi ON, depth 0
    {26.0, function() press(":cpanel:CPR_SEG3", 0x08, 1) end},     -- SOUND DSP = the refresh
    {26.4, function() press(":cpanel:CPR_SEG3", 0x08, 0) end},
    {28.5, function() dump("ramB.bin") end},                       -- post-refresh: depths live
    {29.0, function() press(":cpanel:CPR_SEG3", 0x08, 1) end},     -- SOUND DSP off again
    {29.4, function() press(":cpanel:CPR_SEG3", 0x08, 0) end},
    {31.5, function() dump("ramC.bin") end},                       -- dsp off: chorus/multi still on+deep
  }
  local step = seq[st + 1]
  if step and t > step[1] then st = st + 1; step[2]() end
end)
