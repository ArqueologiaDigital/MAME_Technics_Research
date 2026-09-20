local OUT = os.getenv("VLOG") or "/tmp/vram.log"
local f = io.open(OUT, "w")
local function L(s) emu.print_info(s); if f then f:write(s.."\n"); f:flush() end end
local mach = manager.machine
local lcd = mach.devices[":lcdc"]
local vs = nil
for n, s in pairs(lcd.spaces) do vs = s end
local last = -1
_G._vp = emu.add_machine_frame_notifier(function()
  local ok, err = pcall(function()
    local t = mach.time.seconds
    if t == last then return end
    last = t
    if t % 10 ~= 0 then return end
    -- page 1 = 0x0000, page 2 = 0x2600, page 3 = 0x4c00, each 240*40 = 9600 bytes
    local p = {0, 0, 0, 0}
    local lo, hi = -1, -1
    for a = 0, 0x7fff do
      if vs:read_u8(a) ~= 0 then
        if lo < 0 then lo = a end
        hi = a
        local idx = 4
        if a < 0x2580 then idx = 1
        elseif a >= 0x2600 and a < 0x4b80 then idx = 2
        elseif a >= 0x4c00 and a < 0x7180 then idx = 3 end
        p[idx] = p[idx] + 1
      end
    end
    L(string.format("t=%3d page1=%d page2=%d page3=%d other=%d lo=%04X hi=%04X",
      t, p[1], p[2], p[3], p[4], lo, hi))
  end)
  if not ok then L("ERR "..tostring(err)) end
end)
L("vram_pages armed")
