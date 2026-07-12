-- floppy_format_probe.lua : boot -> DISK (SEG0D 0x04) -> SEG11 0x10 (reaches FLOPPY DISK FORMAT)
-- -> SEG11 0x40 (select "1.44M Byte : 2HD", R3) and observe the format op + FDC accesses.
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local sp   = cpu.spaces["program"]
local function setbtn(p, mk, v)
  local port = mach.ioport.ports[":" .. p]; if not port then emu.print_info("### NO PORT "..p); return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end
local function pcv() return cpu.state["PC"].value end

local fdc = 0
_G._rt = sp:install_read_tap(0x98010000, 0x9801000f, "fr", function(off, d, m)
  fdc = fdc + 1; if fdc <= 200 then emu.print_info(string.format("### FDC RD %08X pc=%08X", off, pcv())) end
end)
_G._wt = sp:install_write_tap(0x98010000, 0x9801000f, "fw", function(off, d, m)
  fdc = fdc + 1; emu.print_info(string.format("### FDC WR %08X = %04X pc=%08X", off, d, pcv()))
end)

local steps = {
  {"SEG0D", 0x04, "DISK menu",        150},
  {"SEG11", 0x10, "R1 -> FORMAT scr", 200},
  {"SEG11", 0x40, "R3 1.44M 2HD",     600},   -- long wait: watch for confirm + format progress
}
local si = 1; local phase = "boot"; local fc = 0; local hbn = 0
_G._n = emu.register_frame_done(function()
  local ok, err = pcall(function()
    fc = fc + 1; hbn = hbn + 1
    if hbn % 300 == 0 then emu.print_info("### hb sec="..tostring(mach.time.seconds).." phase="..phase.." fdc="..fdc) end
    local t = mach.time.seconds
    if phase == "boot" and t >= 17 then
      mach.video:snapshot(); phase = "press"; fc = 0
    elseif phase == "press" then
      local s = steps[si]; emu.print_info("### press "..s[3]); setbtn(s[1], s[2], 1); phase = "hold"; fc = 0
    elseif phase == "hold" and fc >= 20 then
      setbtn(steps[si][1], steps[si][2], 0); phase = "wait"; fc = 0
    elseif phase == "wait" and fc >= steps[si][4] then
      local s = steps[si]; mach.video:snapshot(); emu.print_info("### after "..s[3].." fdc="..fdc)
      si = si + 1
      if si > #steps then emu.print_info("### TOTAL FDC hits = "..fdc); mach:exit()
      else phase = "press"; fc = 0 end
    end
  end)
  if not ok then emu.print_info("### CALLBACK ERROR: "..tostring(err)) end
end)
emu.print_info("### floppy_format_probe loaded")
