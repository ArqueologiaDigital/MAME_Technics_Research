-- Measures the KN5000 sub-CPU scheduler tick empirically, so the refactor is
-- checked against the machine rather than against my own arithmetic.
--
-- The firmware's TaskSched_ConfigAndDispatch runs timer 3 on phiT256 with
-- TREG3 = 0x1D, which should fire at ~337 Hz (2.97 ms). Timer 3's interrupt is
-- INTET23; rather than hook it, this counts how often the 8-bit timer 3
-- up-counter wraps, by sampling TREG3's companion run bit and the CPU's own
-- elapsed time.
--
-- Simpler and more robust: time how long the firmware takes to advance its own
-- scheduler counter by a fixed amount. The scheduler tick is the only ~300 Hz
-- event in the machine, so any RAM word advancing at that rate is it.
local BASE, N = 0x000000, 0x4000        -- 64 KiB of sub-CPU work RAM, as words
local function snap(sp)
  local t = {}
  for i = 0, N - 1 do t[i] = sp:read_u32(BASE + i * 4) end
  return t
end
local function run()
  local cpu = manager.machine.devices[":subcpu"] or manager.machine.devices[":maincpu"]
  local sp = cpu.spaces["program"]
  emu.wait(6.0)
  local a = snap(sp)
  emu.wait(4.0)                          -- exactly 4 emulated seconds
  local b = snap(sp)
  local movers = {}
  for i = 0, N - 1 do
    local d = b[i] - a[i]
    if d > 0 and d < 100000000 then movers[#movers + 1] = { BASE + i * 4, d / 4.0 } end
  end
  table.sort(movers, function(p, q) return p[2] > q[2] end)
  print(string.format("K5TICK: %d words advancing", #movers))
  for k = 1, math.min(#movers, 10) do
    print(string.format("K5TICK: %06X  %.1f Hz  (%.2f ms)", movers[k][1], movers[k][2], 1000 / movers[k][2]))
  end
  print("K5TICK-DONE")
end
_G.k5t = coroutine.create(run)
emu.register_periodic(function()
  if coroutine.status(_G.k5t) == "suspended" then
    local ok, e = coroutine.resume(_G.k5t); if not ok then print("K5TICK err " .. tostring(e)) end
  end
end)
