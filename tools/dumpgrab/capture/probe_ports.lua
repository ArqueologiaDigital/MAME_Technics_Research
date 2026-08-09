local OUT = os.getenv("DG_OUT") or "/tmp/dg_ports.log"
local logf = io.open(OUT, "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
for tag,port in pairs(mach.ioport.ports) do
  local names = {}
  for n,f in pairs(port.fields) do names[#names+1] = ("%02X=%s"):format(f.mask, n) end
  table.sort(names)
  LOG(("PORT %s : %s"):format(tag, table.concat(names, " | ")))
end
LOG("--- devices ---")
for tag,dev in pairs(mach.devices) do LOG("DEV "..tag) end
if logf then logf:close() end
mach:exit()
