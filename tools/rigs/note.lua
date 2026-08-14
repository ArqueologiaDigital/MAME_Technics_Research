-- At t>=16s (home screen reached) press PC key "C4" and hold it, so the first-cut
-- sine synth sustains a 261.63 Hz tone that -wavwrite captures.
local mac = manager.machine
local sp  = mac.devices[":maincpu"].spaces["program"]
local done=false
emu.add_machine_frame_notifier(function()
  if not done and mac.time.seconds >= 16 then
    done=true
    local hit=false
    for _,f in pairs(mac.ioport.ports[":KEYS0"].fields) do
      if f.name == "Key C4" then f:set_value(1); hit=true end
    end
    -- home-screen sanity: framebuffer nonzero count
    local nz=0
    for a=0x9ce00000,0x9ce00000+640*240*2-1,256 do if sp:read_u32(a)~=0 then nz=nz+1 end end
    print(string.format("KEY C4 DOWN=%s  fb_nonzero=%d  t=%d", tostring(hit), nz, mac.time.seconds))
  end
end)
