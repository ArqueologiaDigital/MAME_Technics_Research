-- fdc_irq_probe.lua -- is the floppy controller's interrupt serviced?
--
-- Question it answers: on the KN-series MN10300 boards, does the firmware's FDC
-- interrupt handler run? It counts (a) reads of the FDC registers
-- (0x98010000-0x9802000f) and (b) acknowledges of interrupt group 0x19 -- a
-- write to its ICR 0x34000164 whose low byte is 1. The firmware enables group
-- 0x19 at boot and polls the FDC until the interrupt arrives, so a serviced
-- interrupt shows as acks > 0 and a short poll; a misrouted one as 0 acks and
-- hundreds of thousands of polls.
--
--   kn <set> -autoboot_script fdc_irq_probe.lua -seconds_to_run 12 ...
local cpu = manager.machine.devices[":maincpu"]
local prog = cpu.spaces["program"]
fdcp = { reads = 0, acks = 0, first_ack = nil }
fdcp_r = prog:install_read_tap(0x98010000, 0x9802000f, "fdcp_r",
	function(offset, data, mask) fdcp.reads = fdcp.reads + 1; return data end)
fdcp_w = prog:install_write_tap(0x34000164, 0x34000167, "fdcp_w",
	function(offset, data, mask)
		if (mask & 0xff) ~= 0 and (data & 0xff) == 1 then
			fdcp.acks = fdcp.acks + 1
			if not fdcp.first_ack then
				fdcp.first_ack = manager.machine.time:as_double()
				print(string.format("[fdc] first group-0x19 ack at %.3f s, pc=%08x", fdcp.first_ack, cpu.state["PC"].value))
			end
		end
		return data end)
fdcp_stop = emu.add_machine_stop_notifier(function()
	print(string.format("[fdc] FDC register reads %d, group-0x19 acks %d", fdcp.reads, fdcp.acks))
end)
