-- kn5000_xssp_verify.lua : verify the INT0 re-assertion fix.
-- (1) poll the SubCPU stack pointer XSSP over 22 s -- it must stay BOUNDED
--     (before the fix it drifted down ~8.6 KB/s into the code region).
-- (2) snapshot the play screen near the end so the sound-name lines can be read.
local mach = manager.machine
local sub  = mach.devices[":subcpu"]
local xssp = sub.state["XSSP"]

local minv, maxv = nil, nil
local samples = {}

_G._n = emu.register_frame_done(function()
  local ok, err = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds / 1e18
    local frame = mach.screens ~= nil
    -- sample once per ~0.5 s from t=4
    if t >= 4.0 and (math.floor(t*2) ~= (_G._last or -1)) then
      _G._last = math.floor(t*2)
      local v = xssp.value
      if minv == nil or v < minv then minv = v end
      if maxv == nil or v > maxv then maxv = v end
      table.insert(samples, string.format("t=%5.1f XSSP=%06X", t, v))
      emu.print_info(string.format("### XSSP t=%5.1f = %06X  (min=%06X max=%06X span=%d)",
        t, v, minv or 0, maxv or 0, (maxv or 0)-(minv or 0)))
    end
    if t >= 20.0 and not _G._snapped then
      _G._snapped = true
      mach.video:snapshot()
      emu.print_info("### SNAPSHOT taken at t=20")
    end
    if t >= 22.5 then
      emu.print_info(string.format("### RESULT XSSP min=%06X max=%06X span=%d bytes over run",
        minv or 0, maxv or 0, (maxv or 0)-(minv or 0)))
      -- verdict: code region begins ~0x035893; a healthy SP stays well above 0x03F000
      if (minv or 0) >= 0x03F000 then
        emu.print_info("### VERDICT: XSSP BOUNDED (never entered code region) -- LEAK FIXED")
      else
        emu.print_info("### VERDICT: XSSP entered/approached code region -- STILL LEAKING")
      end
      mach:exit()
    end
  end)
  if not ok then emu.print_info("### CALLBACK ERROR: " .. tostring(err)) end
end)
emu.print_info("### kn5000_xssp_verify loaded")
