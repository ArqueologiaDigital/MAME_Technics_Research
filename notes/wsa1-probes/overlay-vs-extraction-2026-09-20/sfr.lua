local OUT = os.getenv("PCSLOG") or "/tmp/sfr.log"
local logf = io.open(OUT, "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local c1 = mach.devices[":cpu1"]; local c2 = mach.devices[":cpu2"]
local sp1 = c1.spaces["program"]; local sp2 = c2.spaces["program"]
local done = {}
_G._sfr = emu.add_machine_frame_notifier(function()
  local ok, err = pcall(function()
    local t = mach.time.seconds
    for _, mark in ipairs({1, 3, 6}) do
      if t >= mark and not done[mark] then
        done[mark] = true
        for name, sp in pairs({cpu1 = sp1, cpu2 = sp2}) do
          local rows = {}
          for base = 0x20, 0x2f, 8 do
            local s = string.format("  %s SFR %02X:", name, base)
            for i = 0, 7 do s = s .. string.format(" %02X", sp:read_u8(base + i)) end
            rows[#rows+1] = s
          end
          for base = 0x70, 0x7f, 8 do
            local s = string.format("  %s SFR %02X:", name, base)
            for i = 0, 7 do s = s .. string.format(" %02X", sp:read_u8(base + i)) end
            rows[#rows+1] = s
          end
          LOG("t="..mark.." "..name.." tick="..string.format("%04X", sp:read_u16(0x80)))
          for _, r in ipairs(rows) do LOG(r) end
        end
      end
    end
    if t >= 7 and not _G._d then _G._d = true; LOG("DONE") end
  end)
  if not ok then LOG("ERR "..tostring(err)) end
end)
LOG("sfr armed")
