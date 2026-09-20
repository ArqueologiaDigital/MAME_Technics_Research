local OUT = os.getenv("PCSLOG") or "/tmp/tap.log"
local logf = io.open(OUT, "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local c1 = mach.devices[":cpu1"]
local sp1 = c1.spaces["program"]
local nread = 0
local nwrite = 0
local first = {}
local okt, errt = pcall(function()
  _G._rt = sp1:install_read_tap(0x7c0000, 0x7c0001, "linkrd", function(offset, data, mask)
    nread = nread + 1
    if nread <= 12 then first[#first+1] = string.format("R t=%.4f off=%06X data=%02X", mach.time.as_double(), offset, data & 0xff) end
    return data
  end)
  _G._wt = sp1:install_write_tap(0x7c0000, 0x7c0001, "linkwr", function(offset, data, mask)
    nwrite = nwrite + 1
    if nwrite <= 12 then first[#first+1] = string.format("W t=%.4f off=%06X data=%02X", mach.time.as_double(), offset, data & 0xff) end
    return data
  end)
end)
if not okt then LOG("TAP FAIL "..tostring(errt)) end
local last = -1
_G._tp = emu.add_machine_frame_notifier(function()
  local t = mach.time.seconds
  if t ~= last then
    last = t
    if t % 10 == 0 then LOG(string.format("t=%3d reads=%d writes=%d 8A=%02X tick=%04X", t, nread, nwrite, sp1:read_u8(0x8a), sp1:read_u16(0x80))) end
    if t == 40 then for _, s in ipairs(first) do LOG("  "..s) end; LOG("DONE") end
  end
end)
LOG("tap armed")
