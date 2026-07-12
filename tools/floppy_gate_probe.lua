-- floppy_gate_probe.lua : sample the disk-subsystem state bytes around a DISK-MENU press
-- (SEG0D 0x40) vs the working SD-MENU press (SEG0D 0x80), to see if the DISK event reaches the
-- disk stack and what the drive-present status byte (0x5006bc19) reads. Run WITHOUT -log.
local mach = manager.machine
local sp   = mach.devices[":maincpu"].spaces["program"]

local function setbtn(p, mk, v)
  local port = mach.ioport.ports[":" .. p]
  if not port then emu.print_info("### NO PORT " .. p); return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end
local function snap(tag)
  emu.print_info(string.format(
    "### %-14s initA=%d initB=%d  stat@bc19=%02X  struct[1f0..200]=%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X",
    tag,
    sp:read_u32(0x50002d10), sp:read_u32(0x50002d14),
    sp:read_u8(0x5006bc19),
    sp:read_u8(0x5006bc10), sp:read_u8(0x5006bc11), sp:read_u8(0x5006bc12), sp:read_u8(0x5006bc13),
    sp:read_u8(0x5006bc14), sp:read_u8(0x5006bc15), sp:read_u8(0x5006bc16), sp:read_u8(0x5006bc17),
    sp:read_u8(0x5006bc18), sp:read_u8(0x5006bc19), sp:read_u8(0x5006bc1a)))
end

local phase = "boot"; local fc = 0; local hbn = 0
_G._n = emu.register_frame_done(function()
  local ok, err = pcall(function()
    fc = fc + 1; hbn = hbn + 1
    if hbn % 300 == 0 then emu.print_info("### hb sec=" .. tostring(mach.time.seconds) .. " phase=" .. phase) end
    local t = mach.time.seconds
    if phase == "boot" and t >= 17 then
      snap("idle(pre)")
      emu.print_info("### press DISK (SEG0D 0x40)")
      setbtn("SEG0D", 0x40, 1); phase = "disk_hold"; fc = 0
    elseif phase == "disk_hold" and fc >= 20 then
      setbtn("SEG0D", 0x40, 0); phase = "disk_wait"; fc = 0
    elseif phase == "disk_wait" and fc >= 150 then
      snap("after DISK")
      mach.video:snapshot()               -- 0000 = after DISK
      emu.print_info("### press SD MENU (SEG0D 0x80) as working reference")
      setbtn("SEG0D", 0x80, 1); phase = "sd_hold"; fc = 0
    elseif phase == "sd_hold" and fc >= 20 then
      setbtn("SEG0D", 0x80, 0); phase = "sd_wait"; fc = 0
    elseif phase == "sd_wait" and fc >= 150 then
      snap("after SD")
      mach.video:snapshot()               -- 0001 = after SD MENU
      mach:exit()
    end
  end)
  if not ok then emu.print_info("### CALLBACK ERROR: " .. tostring(err)) end
end)
emu.print_info("### floppy_gate_probe loaded")
