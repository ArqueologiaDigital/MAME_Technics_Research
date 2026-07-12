-- floppy_diskmenu_probe.lua : boot, press DISK MENU (SEG0D 0x40) with a floppy mounted,
-- detect FDC accesses at 0x98010000 via a narrow tap (prints to stdout; run WITHOUT -log,
-- which otherwise floods error.log with every io_r/io_w and stalls the emulator).
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local sp   = cpu.spaces["program"]

local function setbtn(p, mk, v)
  local port = mach.ioport.ports[":" .. p]
  if not port then emu.print_info("### NO PORT " .. p); return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end
local function pcv() return cpu.state["PC"].value end

local fdc_hits = 0
_G._rtap = sp:install_read_tap(0x98010000, 0x9801000f, "fdcrd", function(off, data, mask)
  fdc_hits = fdc_hits + 1
  if fdc_hits <= 80 then emu.print_info(string.format("### FDC RD off=%08X pc=%08X", off, pcv())) end
end)
_G._wtap = sp:install_write_tap(0x98010000, 0x9801000f, "fdcwr", function(off, data, mask)
  fdc_hits = fdc_hits + 1
  emu.print_info(string.format("### FDC WR off=%08X data=%04X pc=%08X", off, data, pcv()))
end)

local phase = "boot"; local fc = 0; local hbn = 0
_G._n = emu.register_frame_done(function()
  local ok, err = pcall(function()
    fc = fc + 1; hbn = hbn + 1
    if hbn % 300 == 0 then emu.print_info("### hb sec=" .. tostring(mach.time.seconds) .. " phase=" .. phase .. " fdc=" .. fdc_hits) end
    local t = mach.time.seconds
    if phase == "boot" and t >= 17 then
      emu.print_info("### t=" .. t .. " pressing DISK MENU (SEG0D 0x40)")
      setbtn("SEG0D", 0x40, 1); phase = "hold"; fc = 0
    elseif phase == "hold" and fc >= 20 then
      setbtn("SEG0D", 0x40, 0); phase = "wait"; fc = 0
      emu.print_info("### released DISK MENU; waiting")
    elseif phase == "wait" and fc >= 240 then
      emu.print_info("### FDC hits total = " .. fdc_hits .. "; snapshot + exit")
      local sok, serr = pcall(function() mach.video:snapshot() end)
      if not sok then emu.print_info("### snapshot failed: " .. tostring(serr)) end
      mach:exit()
    end
  end)
  if not ok then emu.print_info("### CALLBACK ERROR: " .. tostring(err)) end
end)
emu.print_info("### floppy_diskmenu_probe loaded")
