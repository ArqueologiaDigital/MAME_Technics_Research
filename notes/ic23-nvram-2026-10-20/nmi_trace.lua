-- nmi_trace.lua -- what does the CPU do after POWER OFF? At t=40 it prints the NMI path (IC18 at 0x40000008, the RAM stubs at
-- 0x50000000..0x5000000B, the arm byte 0x5006CC81, TM5 mode), presses POWER OFF, then prints PC, SP, PSW, the GPIO latch
-- (bit 3 = power latch), the TM5 count and the stamp at 0x84030174 every frame until MAME exits. Run on -bios v16.
local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local sp = cpu.spaces["program"]
local pressed = nil
local n = 0
_G.SUB = emu.add_machine_frame_notifier(function()
  local t = mac.time:as_double()
  if not pressed and t >= 40 then
    emu.print_error(string.format("pre: 0x40000008=%08x %08x  0x50000000=%08x %08x %08x  cc81=%02x tm5mode=%02x",
      sp:read_u32(0x40000008), sp:read_u32(0x4000000c), sp:read_u32(0x50000000), sp:read_u32(0x50000004), sp:read_u32(0x50000008),
      sp:read_u8(0x5006cc81), sp:read_u8(0x34001082)))
    for _, f in pairs(mac.ioport.ports[":POWER"].fields) do f:set_value(1) end
    pressed = t
  elseif pressed then
    n = n + 1
    emu.print_error(string.format("+%.1fms PC=%08x SP=%08x PSW=%04x gpio=%04x tm5cnt=%04x stamp=%08x",
      (t - pressed) * 1000, cpu.state["PC"].value, cpu.state["SP"].value, cpu.state["PSW"].value,
      sp:read_u16(0x36008004), sp:read_u16(0x340010a2), sp:read_u32(0x84030174)))
  end
end)
