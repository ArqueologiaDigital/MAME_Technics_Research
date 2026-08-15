-- At t>=16s (home screen reached) press PC key "C4" and hold it, so the first-cut
-- sine synth sustains a 261.63 Hz tone that -wavwrite captures.
local mac = manager.machine
local sp  = mac.devices[":maincpu"].spaces["program"]
-- ⚠ FIXED 2026-08-15: the handle must be held in a GLOBAL or the Lua GC collects it and the
-- notifier never fires. As committed, this rig silently did nothing -- no key press, no
-- "KEY C4 DOWN" line, and a completely silent capture that looks exactly like a broken audio
-- path. The hazard is documented in tools/rigs/README.md; this rig predated the fix.
_G.NOTE = _G.NOTE or {}
local done=false
_G.NOTE.h = emu.add_machine_frame_notifier(function()
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
