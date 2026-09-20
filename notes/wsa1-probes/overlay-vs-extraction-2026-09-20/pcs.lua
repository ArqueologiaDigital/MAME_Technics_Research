local OUT = os.getenv("PCSLOG") or "/tmp/pcs.log"
local logf = io.open(OUT, "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local c1 = mach.devices[":cpu1"]; local c2 = mach.devices[":cpu2"]
local h1 = {}; local h2 = {}; local n = 0
_G._pcs = emu.add_machine_frame_notifier(function()
  local ok, err = pcall(function()
    local p1 = c1.state["CURPC"].value; local p2 = c2.state["CURPC"].value
    -- sample many times per frame by also reading after a tiny delay is not possible; count exact PCs
    h1[p1] = (h1[p1] or 0) + 1
    h2[p2] = (h2[p2] or 0) + 1
    n = n + 1
    local t = mach.time.seconds
    if t >= 8 and not _G._done then
      _G._done = true
      local function dump(name, h)
        LOG("== "..name.." ==")
        local keys = {}
        for k,_ in pairs(h) do keys[#keys+1] = k end
        table.sort(keys, function(a,b) return h[a] > h[b] end)
        for i = 1, math.min(#keys, 30) do
          LOG(string.format("  %06X : %d", keys[i], h[keys[i]]))
        end
        LOG("  distinct="..#keys)
      end
      LOG("samples="..n)
      dump("CPU1", h1); dump("CPU2", h2)
      LOG("DONE")
    end
  end)
  if not ok then LOG("ERR "..tostring(err)) end
end)
LOG("pcs armed")
