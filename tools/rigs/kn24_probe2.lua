-- kn2400 probe 2: long run, scan lcdbuf (0x9C000000..0x9CFFFFFF) + vram for content.
local out = io.open("kn24_probe2.log", "w")
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
  if t - lastdump >= 5.0 then
    lastdump = t
    local pc = cpu.state["PC"].value
    -- coarse scan: lcdbuf 16MB at 64KB stride, report first nonzero regions
    local regions = {}
    for blk = 0, 255 do
      local a = 0x9c000000 + blk*0x10000
      local nz = 0
      for i = 0, 15 do
        if mem:read_u32(a + i*0x1000) ~= 0 then nz = nz + 1 end
      end
      if nz > 0 then regions[#regions+1] = string.format("%02x:%d", blk, nz) end
    end
    local vr = {}
    for blk = 0, 63 do
      local a = 0x90000000 + blk*0x10000
      local nz = 0
      for i = 0, 15 do
        if mem:read_u32(a + i*0x1000) ~= 0 then nz = nz + 1 end
      end
      if nz > 0 then vr[#vr+1] = string.format("%02x:%d", blk, nz) end
    end
    out:write(string.format("t=%.1f PC=%08x lcdbuf_nz=[%s] w90_nz=[%s]\n", t, pc,
      table.concat(regions, " "), table.concat(vr, " ")))
    out:flush()
    if t >= 40 then vid:snapshot() end
  end
end)
