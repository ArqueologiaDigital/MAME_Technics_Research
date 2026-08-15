-- kn6_fontchk.lua -- is the KN6000's font table pointer valid, and what does it point at?
-- rig-machine: kn6000
--
-- Reads the pointer at 0x5024F664, then dumps sixteen 0x14-byte font records from it. A base of
-- 0 or 0xFFFFFFFF means the font was never resolved -- which is a completely different defect
-- from a font that resolves but renders wrongly, and the two are indistinguishable from the
-- screen alone.
--
--   ./tools/rig.sh kn6_fontchk kn6000 -s 16
--
-- Writes kn6_fontchk.log in the emulator directory and exits at t=14.

local cpu = manager.machine.devices[":maincpu"]
local mem = cpu.spaces["program"]
local done=false
emu.register_frame_done(function()
  if manager.machine.time.seconds >= 14 and not done then
    done=true
    local out=io.open("kn6_fontchk.log","w")
    local base = mem:read_u32(0x5024F664)
    out:write(string.format("fonttable ptr *(0x5024F664) = %08X\n", base))
    if base ~= 0 and base ~= 0xffffffff then
      for i=0,15 do
        local r=base+i*0x14
        local s={}
        for j=0,0x13,4 do s[#s+1]=string.format("%08X", mem:read_u32(r+j)) end
        out:write(string.format("font[%2d] @%08X: %s\n", i, r, table.concat(s," ")))
      end
    end
    out:close()
    print("FONTCHK done")
    manager.machine:exit()
  end
end)
