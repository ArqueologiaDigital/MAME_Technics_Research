-- Press a named cpanel button (substring match), then snapshot. Retain subs in _G.
local function findfield(sub)
  for _,port in pairs(manager.machine.ioport.ports) do
    for name,field in pairs(port.fields) do
      if name:find(sub, 1, true) then return field, name end
    end
  end
  return nil
end
local SEQ = {}                 -- filled from env: comma-separated button substrings, one press each
for tok in (os.getenv("SEQ") or ""):gmatch("[^,]+") do SEQ[#SEQ+1]=tok end
local n=0
local step=1
local phase="wait"    -- wait -> press -> release -> gap -> next ...
local t0=0
_G.__s = emu.add_machine_frame_notifier(function()
  n=n+1
  if n < 900 then return end
  if step > #SEQ then
    if phase~="done" then
      -- snapshot and exit a bit after the last release
      if phase=="settle" and n>=t0+80 then
        manager.machine.screens:at(1):snapshot(os.getenv("SHOT")); manager.machine:exit(); phase="done"
      elseif phase~="settle" then phase="settle"; t0=n end
    end
    return
  end
  -- press current step at its window
  if phase=="wait" then
    local f,nm = findfield(SEQ[step])
    if f then f:set_value(1); emu.print_info("PRESS "..nm) else emu.print_info("NOTFOUND "..SEQ[step]) end
    phase="press"; t0=n
  elseif phase=="press" and n>=t0+12 then
    local f = findfield(SEQ[step]); if f then f:set_value(0) end
    phase="gap"; t0=n
  elseif phase=="gap" and n>=t0+90 then
    step=step+1; phase="wait"
  end
end)
