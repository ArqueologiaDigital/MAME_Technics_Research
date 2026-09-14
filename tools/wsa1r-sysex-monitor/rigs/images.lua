local mach = manager.machine
emu.print_error("### images:")
for tag, img in pairs(mach.images) do
  emu.print_error(string.format("###   %-12s exists=%s file=%s",
      tag, tostring(img.exists), tostring(img.filename)))
end
_G._f = emu.register_frame_done(function()
  local t = mach.time.seconds + mach.time.attoseconds/1e18
  if t >= 2.0 then mach:exit() end
end)
