-- kn6000: capture C34B draw-post args incl. the stack data ptr; dump pointed memory.
-- RUN WITH: kn6000 -debug -debugger none
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local mem  = cpu.spaces["program"]
local dbg  = mach.debugger
local out  = io.open("kn6_str.log", "w")
local armed = false
local lastlog = 0
local ptrs = {}
local n = 0
_G._k6s = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    cpu.debug:bpset(0x4c01c34b, "1",
      "printf \"BP d0=%08X d1=%08X p=%08X q=%08X\", d0, d1, d@(sp+2C), d@(sp+30) ; g")
    dbg.execution_state = "run"
    out:write("armed\n"); out:flush()
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    local d0,d1,p,q = line:match("^BP d0=(%x+) d1=(%x+) p=(%x+) q=(%x+)")
    if d0 then
      n = n + 1
      if n <= 200 then out:write(string.format("t=%8.3f %s\n", t, line)) end
      local pv = tonumber(p,16)
      if pv and pv >= 0x40000000 then ptrs[pv] = true end
      local qv = tonumber(q,16)
      if qv and qv >= 0x40000000 then ptrs[qv] = true end
    end
  end
  lastlog = #cl
  if t >= 25 and not _G._k6s_done then
    _G._k6s_done = true
    out:write(string.format("total: %d\nPOINTER DUMPS:\n", n))
    for pv in pairs(ptrs) do
      local bytes = {}
      local txt = {}
      for i = 0, 47 do
        local b = mem:read_u8(pv + i)
        bytes[#bytes+1] = string.format("%02x", b)
        txt[#txt+1] = (b >= 32 and b < 127) and string.char(b) or "."
      end
      out:write(string.format("  %08X: %s |%s|\n", pv, table.concat(bytes, " "), table.concat(txt)))
    end
    out:flush()
  end
end)
