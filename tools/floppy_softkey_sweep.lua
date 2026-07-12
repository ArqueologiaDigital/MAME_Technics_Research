-- floppy_softkey_sweep.lua : reach FLOPPY DISK FORMAT, save state, then test EVERY SEG* button from
-- that identical state (save/load) to find the soft-key that selects a format type (2HD/2DD).
-- Snapshots each; md5-diff afterward. FDC tap flags a real disk op. Run WITHOUT -log.
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local sp   = cpu.spaces["program"]
local function setbtn(p, mk, v)
  local port = mach.ioport.ports[":" .. p]; if not port then return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end
local fdc = 0
_G._rt = sp:install_read_tap(0x98010000, 0x9801000f, "fr", function() fdc=fdc+1 end)
_G._wt = sp:install_write_tap(0x98010000, 0x9801000f, "fw", function() fdc=fdc+1 end)

-- build candidate list from all :SEGxx ports (skip nothing; we test every panel bit)
local cand = {}
for tag, port in pairs(mach.ioport.ports) do
  local seg = tag:match("^:(SEG%x%x)$")
  if seg then
    for _, f in pairs(port.fields) do
      if f.mask and f.mask > 0 then cand[#cand+1] = {seg, f.mask} end
    end
  end
end
table.sort(cand, function(a,b) if a[1]==b[1] then return a[2]<b[2] else return a[1]<b[1] end end)
emu.print_info("### candidates = " .. #cand)

local phase = "boot"; local fc = 0; local ci = 0; local fdc_at_save = 0
_G._n = emu.register_frame_done(function()
  local ok, err = pcall(function()
    fc = fc + 1
    local t = mach.time.seconds
    if phase == "boot" then
      if t >= 17 then setbtn("SEG0D",0x04,1); phase="disk_hold"; fc=0 end
    elseif phase == "disk_hold" and fc>=20 then setbtn("SEG0D",0x04,0); phase="disk_wait"; fc=0
    elseif phase == "disk_wait" and fc>=140 then setbtn("SEG11",0x10,1); phase="f_hold"; fc=0
    elseif phase == "f_hold" and fc>=20 then setbtn("SEG11",0x10,0); phase="f_wait"; fc=0
    elseif phase == "f_wait" and fc>=140 then
      mach:save("fmt"); fdc_at_save = fdc
      mach.video:snapshot()      -- 0000 = FORMAT baseline
      emu.print_info("### saved FORMAT state; begin sweep")
      phase="ld"; fc=0
    elseif phase == "ld" then
      mach:load("fmt"); phase="ld_settle"; fc=0
    elseif phase == "ld_settle" and fc>=3 then
      ci = ci + 1
      if ci > #cand then emu.print_info("### sweep done"); mach:exit(); return end
      fdc = fdc_at_save
      setbtn(cand[ci][1], cand[ci][2], 1); phase="c_hold"; fc=0
    elseif phase == "c_hold" and fc>=12 then setbtn(cand[ci][1], cand[ci][2], 0); phase="c_wait"; fc=0
    elseif phase == "c_wait" and fc>=45 then
      mach.video:snapshot()
      local hit = (fdc > fdc_at_save) and " <<FDC!>>" or ""
      emu.print_info(string.format("### c%03d %s %02X fdc=%d%s", ci, cand[ci][1], cand[ci][2], fdc-fdc_at_save, hit))
      phase="ld"; fc=0
    end
  end)
  if not ok then emu.print_info("### CALLBACK ERROR: "..tostring(err)) end
end)
emu.print_info("### floppy_softkey_sweep loaded")
