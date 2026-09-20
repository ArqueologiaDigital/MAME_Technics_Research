-- Does the SX-WSA1R's RTOS ever get entered?
-- IRQ_Epilogue (prom_a 0xF857B7) reads control register 0x3C and compares it
-- with 1: equal = this was the OUTERMOST interrupt, so enter the kernel at
-- 0xF857C1; otherwise pop/RETI at 0xF857BF.  Counting instruction fetches in
-- the two arms says which way it goes.  Kernel_Dispatch__switch_to (0xF8575B)
-- is an actual task switch.
local OUT = os.getenv("PCSLOG") or "/tmp/kern.log"
local logf = io.open(OUT, "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local c1 = mach.devices[":cpu1"]
local sp1 = c1.spaces["program"]
local n = { epi = 0, reti = 0, kern = 0, disp = 0, sw = 0 }
local function tap(addr, key, name)
  local ok, err = pcall(function()
    _G["_t_"..key] = sp1:install_read_tap(addr, addr + 1, name, function(offset, data, mask)
      n[key] = n[key] + 1
      return data
    end)
  end)
  if not ok then LOG("TAP FAIL "..name.." "..tostring(err)) end
end
tap(0xF857B6, "epi",  "irq_epilogue")       -- entry
tap(0xF857BE, "reti", "nested_reti_arm")    -- pop WA / reti
tap(0xF857C6, "kern", "enter_kernel_arm")   -- ei 0x00, inside the kernel arm
tap(0xF85714, "disp", "kernel_dispatch")
tap(0xF8575A, "sw",   "kernel_switch_to")
local last = -1
_G._k = emu.add_machine_frame_notifier(function()
  local t = mach.time.seconds
  if t ~= last then
    last = t
    if t % 2 == 0 then
      LOG(string.format("t=%3d tick=%04X epilogue=%d retiarm=%d kernelarm=%d dispatch=%d switch=%d",
        t, sp1:read_u16(0x80), n.epi, n.reti, n.kern, n.disp, n.sw))
    end
  end
end)
LOG("kern armed")
