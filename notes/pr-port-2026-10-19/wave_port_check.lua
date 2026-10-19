-- wave_port_check.lua -- does the driver serve the wave ROMs to the firmware's own wave ROM test protocol?
-- After 20 s of emulation it sweeps each tone generator's test port through the CPU's address space exactly as
-- the firmware's checksum core does (0x484839A1 in PROGRAM 941): 0x8000 | bank into P+6, 0x8000 | a | select into
-- P+8 for a = 0, 2 .. 0x7FFE, read the word at P+A, add its two bytes. Each sum must equal the one the firmware
-- expects for that index (the table at 0x485CFD18 in 941, the same in every build), whose screen labels are
-- MAIN TG IC203/IC204 at 0x98050000 and SUB TG IC207/IC208 at 0x98040000. Prints one PROBE line per index, then exits.
-- Negative control: WAVE_CHECK_SWAP=1 exchanges the two ports, which is what the firmware sees when a driver maps the
-- main and sub tone generators the other way round; every index must then fail.
local idx = {
  { 0x98050000, 0, 0x8164C77C, "IC203" }, { 0x98050000, 1, 0x815CFC83, "IC204" },
  { 0x98040000, 0, 0x8331EF0B, "IC207" }, { 0x98040000, 1, 0x83254F9D, "IC208" },
}
if os.getenv("WAVE_CHECK_SWAP") == "1" then
  for _, t in ipairs(idx) do t[1] = (t[1] == 0x98050000) and 0x98040000 or 0x98050000 end
end
local done = false
emu.register_periodic(function()
  local m = manager.machine
  if done or m.time:as_double() < 20 then return end
  done = true
  local sp = m.devices[":maincpu"].spaces["program"]
  local bad = 0
  for i, t in ipairs(idx) do
    local p, sel, golden, label = t[1], t[2], t[3], t[4]
    local sum = 0
    sp:write_u16(p + 6, 0x8000)
    for bank = 0, 511 do
      sp:write_u16(p + 6, 0x8000 | bank)
      for a = sel, 0x7fff, 2 do
        sp:write_u16(p + 8, 0x8000 | a)
        local w = sp:read_u16(p + 0xa)
        sum = (sum + (w >> 8) + (w & 0xff)) & 0xffffffff
      end
    end
    sp:write_u16(p + 6, 0)
    local ok = sum == golden
    if not ok then bad = bad + 1 end
    emu.print_error(string.format("PROBE index %d port %08X select %d (%s): sum %08X expected %08X %s",
      i - 1, p, sel, label, sum, golden, ok and "OK" or "NG"))
  end
  emu.print_error(string.format("PROBE end: %d of 4 OK", 4 - bad))
  m:exit()
end)
