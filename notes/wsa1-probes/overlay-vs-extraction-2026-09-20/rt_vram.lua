-- QUESTION: does the firmware ever write NON-ZERO content into the SED1330's
-- display RAM?  Taps the lcdc's videoram space and reports zero vs non-zero
-- write counts, plus CPU1->CPU2 / CPU2->CPU1 link byte counts (taps on the two
-- link data ports) -- all per BUCKET seconds.
local m = manager.machine
local lc = m.devices[":lcdc"]
local sp1 = m.devices[":cpu1"].spaces["program"]
local vs
for name, s in pairs(lc.spaces) do vs = s end
local STOP   = tonumber(os.getenv("STOP_AT") or "22")
local BUCKET = tonumber(os.getenv("BUCKET_S") or "2")
local z, nz, l12, l21 = 0, 0, 0, 0
_G.vt = vs:install_write_tap(0x0000, 0xffff, "vram", function (offset, data, mask)
  if (data & 0xff) == 0 then z = z + 1 else nz = nz + 1 end
end)
_G.lt1 = sp1:install_write_tap(0x7c0000, 0x7c0001, "l12", function () l12 = l12 + 1 end)
_G.lt2 = sp1:install_read_tap(0x7c0000, 0x7c0001, "l21", function () l21 = l21 + 1 end)
local nxt = BUCKET
_G.vn = emu.add_machine_frame_notifier(function ()
  local t = m.time:as_double()
  if t < nxt then return end
  nxt = nxt + BUCKET
  emu.print_error(string.format("VRAM t<%6.1f  zero=%6d  NONZERO=%6d   link cpu1w=%4d cpu1r=%4d",
    t, z, nz, l12, l21))
  z, nz, l12, l21 = 0, 0, 0, 0
  if t >= STOP then m.video:snapshot(); m:exit() end
end)
