-- kn6_huff.lua -- KN6000 missing-text investigation: is the string decompressor running?
-- rig-machine: kn6000
--
-- Sibling of kn6_blit.lua / kn6_fn.lua on the kn6_text_bp.lua harness. Arms 0x48405fb1 (the
-- suspected Huffman/string decoder) plus its aliases 0x4c005fb1 and 0x8c005fb1.
--
-- Distinguishes two very different causes of a blank screen: strings never decompressed
-- (this fires zero times) versus strings decompressed but never drawn (this fires, kn6_fn
-- does not).
--
--   ./tools/rig.sh kn6_huff kn6000 -s 40 -- -debug -debugger none
--
-- Needs the debugger. Writes kn6_huff.log in the emulator directory (overwritten on publish).
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local out  = io.open("kn6_huff.log", "w")
local armed = false
local lastlog = 0
local counts = {}
local CAP = 40
local bps = {
  {0x48405fb1, "HUFF"},
  {0x4c005fb1, "aHUFF"},
  {0x8c005fb1, "bHUFF"},
}
_G._k6t = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    for _, b in ipairs(bps) do
      cpu.debug:bpset(b[1], "1",
        string.format("printf \"BP %s a0=%%08X a1=%%08X d0=%%08X d1=%%08X ret=%%08X\", a0, a1, d0, d1, d@(sp) ; g", b[2]))
    end
    dbg.execution_state = "run"
    out:write("armed\n"); out:flush()
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    local tag = line:match("^BP (%S+)")
    if tag then
      counts[tag] = (counts[tag] or 0) + 1
      if counts[tag] <= CAP then
        out:write(string.format("t=%8.3f %s\n", t, line))
      end
    end
  end
  lastlog = #cl
  if t >= 30 and not _G._k6t_done then
    _G._k6t_done = true
    local s = "COUNTS:"
    for k, v in pairs(counts) do s = s .. string.format(" %s=%d", k, v) end
    out:write(s .. "\n"); out:flush()
    mach.video:snapshot()
  end
end)
