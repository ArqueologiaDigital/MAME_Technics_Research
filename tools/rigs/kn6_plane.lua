-- KN6000: dump the UI index plane (0x5020042C), the companion plane, and the CLUT.
local cpu = manager.machine.devices[":maincpu"]
local mem = cpu.spaces["program"]
local done = false
emu.register_frame_done(function()
  if manager.machine.time.seconds >= 14 and not done then
    done = true
    local f = io.open("kn6_plane.bin", "wb")
    for a = 0x5020042C, 0x5020042C + 0x25800 - 1 do f:write(string.char(mem:read_u8(a))) end
    f:close()
    local g = io.open("kn6_plane2.bin", "wb")
    for a = 0x50225C2C, 0x50225C2C + 0x25800 - 1 do g:write(string.char(mem:read_u8(a))) end
    g:close()
    local c = io.open("kn6_clut.bin", "wb")
    for a = 0x5024F458, 0x5024F458 + 0x200 - 1 do c:write(string.char(mem:read_u8(a))) end
    c:close()
    manager.machine.video:snapshot()
    print("PLANEDUMP done")
    manager.machine:exit()
  end
end)
