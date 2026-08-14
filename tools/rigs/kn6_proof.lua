-- DIAGNOSTIC ONLY (never shipped): prove that the KN6000's missing text is caused solely by
-- the undumped table/mask ROM at 0x48000000, whose header 0x200..0x210 holds the font
-- descriptor pointers. Inject the KN7000 table ROM's font region + header values and see
-- whether glyphs appear.
--
-- The 4 MB input kn7000_table.bin is NOT kept in this directory on purpose (it is the
-- KN7000's mask ROM and must never be mistaken for KN6000 data). Regenerate it with:
--   python3 -c "e=open('roms/kn7000/kn7000_table_even.rom','rb').read(); \
--     o=open('roms/kn7000/kn7000_table_odd.rom','rb').read(); \
--     t=bytearray(); [t.extend(e[i:i+2]+o[i:i+2]) for i in range(0,len(e),2)]; \
--     open('kn7000_table.bin','wb').write(t)"
local mach = manager.machine
local mem  = mach.devices[":maincpu"].spaces["program"]
local rgn  = mach.memory.regions[":table"]
local injected, shot = false, false
emu.register_frame_done(function()
  local t = mach.time.seconds
  if not injected and t >= 8 then
    injected = true
    local f = assert(io.open("kn7000_table.bin", "rb"))
    local data = f:read(0x40000); f:close()
    for i = 1, #data do rgn:write_u8(i - 1, data:byte(i)) end
    -- the five font/resource table pointers the KN6000 font init copied from 0x48000200
    mem:write_u32(0x5024F658, 0x48000240)
    mem:write_u32(0x5024F65C, 0x4800E880)
    mem:write_u32(0x5024F660, 0x4801221C)
    mem:write_u32(0x5024F664, 0x480237A4)
    mem:write_u32(0x5024F668, 0x00000000)
    print("INJECTED font descriptors")
  end
  if not shot and t >= 13 then
    shot = true
    mach.video:snapshot()
    print("PROOF snapshot taken")
    mach:exit()
  end
end)
