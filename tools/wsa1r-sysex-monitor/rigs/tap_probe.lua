local mach = manager.machine
emu.print_error("### A: start")
local cpu = mach.devices[":cpu1"]
emu.print_error("### B: cpu = " .. tostring(cpu))
local prog = cpu.spaces["program"]
emu.print_error("### C: prog = " .. tostring(prog))
local ok, res = pcall(function()
  return prog:install_read_tap(0xFBA259, 0xFBA259, "STOCK", function(offset, data, mask) return data end)
end)
emu.print_error("### D: install ok=" .. tostring(ok) .. " res=" .. tostring(res))
