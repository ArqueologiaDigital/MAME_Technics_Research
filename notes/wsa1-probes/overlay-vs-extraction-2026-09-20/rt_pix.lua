-- QUESTION: after the firmware's big draw batch, is the content IN display RAM,
-- and does it reach the SCREEN?  Reports, per bucket: non-zero bytes in the
-- SED1330's videoram, and non-zero pixels in the emulated screen bitmap.
local m = manager.machine
local lc = m.devices[":lcdc"]
local scr = m.screens[":screen"]
local vs
for _, s in pairs(lc.spaces) do vs = s end
local STOP   = tonumber(os.getenv("STOP_AT") or "8")
local BUCKET = tonumber(os.getenv("BUCKET_S") or "2")
local nxt = BUCKET
_G.px = emu.add_machine_frame_notifier(function ()
  local t = m.time:as_double()
  if t < nxt then return end
  nxt = nxt + BUCKET
  local vnz = 0
  for a = 0, 0x7fff do if vs:read_u8(a) ~= 0 then vnz = vnz + 1 end end
  -- how many screen bytes DIFFER from the first byte: 0 = a uniform (blank) panel
  local pnz = 0
  local ok, pix = pcall(function () return scr:pixels() end)
  if ok and pix and #pix > 0 then
    local b0 = pix:byte(1)
    for i = 1, #pix do if pix:byte(i) ~= b0 then pnz = pnz + 1 end end
  end
  emu.print_error(string.format("PIX t<%6.1f  vram_nonzero=%6d   screenbytes_differing_from_uniform=%8d",
    t, vnz, pnz))
  if t >= STOP then m.video:snapshot(); m:exit() end
end)
