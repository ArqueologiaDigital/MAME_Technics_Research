-- kn2400 boot probe: log PC samples + framebuffer fill, snapshot at end.
local out = io.open("kn24_probe.log", "w")
local cpu = manager.machine.devices[":maincpu"]
local mem = cpu.spaces["program"]
local vid = manager.machine.video
local function now()
  local t = manager.machine.time
  return t.seconds + t.attoseconds/1e18
end
local lastdump = 0
emu.register_frame_done(function()
  local t = now()
  if t - lastdump >= 1.0 then
    lastdump = t
    local pc = cpu.state["PC"].value
    local sp = cpu.state["SP"].value
    -- count non-black pixels in a sparse sample of the LCD framebuffer
    local nb = 0
    for i = 0, 299 do
      local a = 0x9ce00000 + i*1024
      local v = mem:read_u16(a)
      if v ~= 0 then nb = nb + 1 end
    end
    out:write(string.format("t=%.2f PC=%08x SP=%08x fbsample_nonzero=%d/300\n", t, pc, sp, nb))
    out:flush()
    if t >= 11.0 then
      vid:snapshot()
      out:write("snapshot taken\n")
      out:flush()
    end
  end
end)
