-- sched.lua -- IS THE SX-WSA1R'S RTOS SCHEDULER ENTERED?
--
-- QUESTION: prom_a's IRQ_Epilogue at 0xF857B7 reads control register 0x3C
-- (INTNEST) and enters Kernel_Dispatch ONLY when it reads exactly 1:
--     f857b8 ldc WA,cr3C / f857bb cp WA,1 / f857bd jr Z,0xf857c1
--     f857bf pop WA / f857c0 reti              <- NOT the outermost interrupt
--     f857c1 xor WA,WA / f857c3 ldc cr3C,WA / ... / f857d3 jrl 0xf85715
-- So counting opcode fetches at 0xF857D2 counts SCHEDULER ENTRIES, and fetches
-- at 0xF857BE count EPILOGUE ARRIVALS (both paths).  Ratio 0 means the
-- comparison never matches, i.e. INTNEST never reads 1.
-- SIGNAL: CPU 1 program-space reads (opcode fetch goes through the space).
-- Ranges are word-aligned; the nearest unrelated code is 0x12 bytes away, well
-- clear of RDOP()'s 4-byte prefetch.
local cpu = manager.machine.devices[":cpu1"]
local sp  = cpu.spaces["program"]
epi, sch = 0, 0
TAPS = {}   -- MUST be global: a local tap is garbage-collected and stops firing
TAPS[1] = sp:install_read_tap(0xf857be, 0xf857bf, "epi", function() epi = epi + 1 end)
TAPS[2] = sp:install_read_tap(0xf857d2, 0xf857d3, "sch", function() sch = sch + 1 end)
local n = 0
SUB = emu.add_machine_frame_notifier(function()
  n = n + 1
  if n % 60 == 0 then
    print(string.format("SCHED t=%3ds  epilogue=%-8d scheduler=%-8d", n//60, epi, sch))
    io.stdout:flush()
  end
end)
