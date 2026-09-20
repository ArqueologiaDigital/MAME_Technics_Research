-- QUESTION: which direction of the inter-processor link is alive?
-- CPU1's data port is 0x7C0000, CPU2's is 0x100000.  Counts reads and writes
-- on both, per bucket.
local m = manager.machine
local s1 = m.devices[":cpu1"].spaces["program"]
local s2 = m.devices[":cpu2"].spaces["program"]
local STOP   = tonumber(os.getenv("STOP_AT") or "6")
local BUCKET = tonumber(os.getenv("BUCKET_S") or "2")
local c = {c1w=0,c1r=0,c2w=0,c2r=0}
_G.t1w = s1:install_write_tap(0x7c0000,0x7c0001,"c1w",function() c.c1w=c.c1w+1 end)
_G.t1r = s1:install_read_tap (0x7c0000,0x7c0001,"c1r",function() c.c1r=c.c1r+1 end)
_G.t2w = s2:install_write_tap(0x100000,0x100001,"c2w",function() c.c2w=c.c2w+1 end)
_G.t2r = s2:install_read_tap (0x100000,0x100001,"c2r",function() c.c2r=c.c2r+1 end)
local nxt = BUCKET
_G.ln = emu.add_machine_frame_notifier(function ()
  local t = m.time:as_double()
  if t < nxt then return end
  nxt = nxt + BUCKET
  emu.print_error(string.format("LINK t<%6.1f  cpu1 w=%6d r=%6d | cpu2 w=%6d r=%6d",
    t, c.c1w, c.c1r, c.c2w, c.c2r))
  c.c1w,c.c1r,c.c2w,c.c2r = 0,0,0,0
  if t >= STOP then m:exit() end
end)
