local OUT = os.getenv("PCSLOG") or "/tmp/long.log"
local logf = io.open(OUT, "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local c1 = mach.devices[":cpu1"]
local sp1 = c1.spaces["program"]
local lcd = mach.devices[":lcdc"]
local vs = nil
for n, s in pairs(lcd.spaces) do vs = s; LOG("lcdc space: "..n) end
local last = -1
local shots = 0
_G._lg = emu.add_machine_frame_notifier(function()
  local ok, err = pcall(function()
    local t = mach.time.seconds
    if t ~= last then
      last = t
      local nz = 0
      if vs then for a = 0, 0x7fff, 16 do if vs:read_u8(a) ~= 0 then nz = nz + 1 end end end
      if t % 5 == 0 then
        LOG(string.format("t=%3d cpu1PC=%06X tick=%04X vram_nz/2048=%d", t, c1.state["CURPC"].value, sp1:read_u16(0x80), nz))
      end
      if (t == 30 or t == 80 or t == 145) and shots < 5 then shots = shots + 1; mach.video:snapshot() end
    end
  end)
  if not ok then LOG("ERR "..tostring(err)) end
end)
LOG("long armed")
