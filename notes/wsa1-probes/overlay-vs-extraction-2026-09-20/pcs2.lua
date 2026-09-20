local OUT = os.getenv("PCSLOG") or "/tmp/pcs2.log"
local logf = io.open(OUT, "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local c1 = mach.devices[":cpu1"]; local c2 = mach.devices[":cpu2"]
local sp1 = c1.spaces["program"]; local sp2 = c2.spaces["program"]
local late1 = {}; local late2 = {}; local n=0
local lastlog = -1
_G._pcs = emu.add_machine_frame_notifier(function()
  local ok, err = pcall(function()
    local t = mach.time.seconds
    local p1 = c1.state["CURPC"].value; local p2 = c2.state["CURPC"].value
    if t >= 6 then
      late1[p1] = (late1[p1] or 0) + 1
      late2[p2] = (late2[p2] or 0) + 1
      n = n + 1
    end
    if t ~= lastlog then
      lastlog = t
      LOG(string.format("t=%d cpu1PC=%06X cpu2PC=%06X tick1=%04X tick2=%04X m8A_1=%02X m8A_2=%02X",
        t, p1, p2, sp1:read_u16(0x80), sp2:read_u16(0x80), sp1:read_u8(0x8a), sp2:read_u8(0x8a)))
    end
    if t >= 8 and not _G._done then
      _G._done = true
      local function dump(name, h)
        LOG("== LATE(6-8s) "..name.." ==")
        local keys = {}
        for k,_ in pairs(h) do keys[#keys+1] = k end
        table.sort(keys, function(a,b) return h[a] > h[b] end)
        for i = 1, #keys do LOG(string.format("  %06X : %d", keys[i], h[keys[i]])) end
        LOG("  distinct="..#keys)
      end
      LOG("late samples="..n)
      dump("CPU1", late1); dump("CPU2", late2)
      LOG("DONE")
    end
  end)
  if not ok then LOG("ERR "..tostring(err)) end
end)
LOG("pcs2 armed")
