-- show_probe.lua -- KN7000: what does <SHOW OBJ="name"> do for a given object name?
-- Boots, presses DEMO (cpanel CPL_SEG6 0x40) at t = 20 s, inserts $FEATURE_IMG (a disk made by
-- show_probe_disk.py) into :fdc:0:35hd at t = 25 s, so the FEATURE.PRE presentation loads and its
-- song's PIC points select slide 0, 1, 2 ... Logs, through debugger breakpoints:
--   PIC n      0x4858099B  slide n is being shown (PicDispatch)
--   SHOW name  0x4857FC28  the OBJ name the SHOW handler looks up (first 16 bytes, as text)
--   LOOKUP id  0x4857FC2D  the lookup's result (0x48580EE6): an object id (slot << 20 | index),
--                          or FFFFFFFF when no object has that name; on a hit the handler sends
--                          the object EV_PAINT (0x00050009) through 0x4842938D
-- and takes a snapshot 1 s after each slide change. Exits at $RUN_END (default 125) seconds.
-- Run: kn7000 kn7000 -rompath ROMS -window -nothrottle -debug -debugger none \
--        -snapshot_directory OUT -autoboot_delay 0 -autoboot_script show_probe.lua  (env FEATURE_IMG)
local IMG = os.getenv("FEATURE_IMG")
local RUN_END = tonumber(os.getenv("RUN_END") or "125")
local m = manager.machine
local dbg = m.debugger
local seen, pending, done = 0, {}, {}
local function setbtn(p, mk, v)
  local port = m.ioport.ports[":cpanel:" .. p] or m.ioport.ports[":" .. p]
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v); return end end
end
local function hexstr(s)                       -- "%08X%08X..." of little-endian dwords -> text
  local out = {}
  for w in s:gmatch("%x%x%x%x%x%x%x%x") do
    local v = tonumber(w, 16)
    for i = 0, 3 do local c = (v >> (8 * i)) & 0xff; if c == 0 then return table.concat(out) end
      out[#out + 1] = string.char(c) end
  end
  return table.concat(out)
end
local armed = false
_G.show_sub = emu.add_machine_frame_notifier(function()
  local t = m.time.seconds
  if not armed then
    armed = true
    dbg:command('bp 4858099b,1,{printf "PIC %X",d0; g}')
    dbg:command('bp 4857fc28,1,{printf "SHOWNAME %08X%08X%08X%08X",d@a0,d@(a0+4),d@(a0+8),d@(a0+0xc); g}')
    dbg:command('bp 4857fc2d,1,{printf "LOOKUP %X",d0; g}')
    dbg:command("g")
  end
  local log = dbg.consolelog
  while seen < #log do
    seen = seen + 1
    local line = log[seen]
    local hx = line:match("^SHOWNAME (%x+)")
    if hx then print(string.format("[%.2f] SHOW %s", t, hexstr(hx)))
    elseif line:match("^PIC ") or line:match("^LOOKUP ") then
      print(string.format("[%.2f] %s", t, line))
      local n = line:match("^PIC (%x+)")
      if n then pending[#pending + 1] = { t + 1.0, n } end
    end
  end
  for _, p in ipairs(pending) do
    if not p.done and t >= p[1] then p.done = true; m.video:snapshot(); print(string.format("[%.2f] SNAP after PIC %s", t, p[2])) end
  end
  if t >= 20 and not done.demo then done.demo = true; setbtn("CPL_SEG6", 0x40, 1) end
  if t >= 20.4 and not done.demo_up then done.demo_up = true; setbtn("CPL_SEG6", 0x40, 0) end
  if t >= 25 and not done.ins then done.ins = true
    print("LOAD " .. tostring(m.images[":fdc:0:35hd"]:load(IMG))) end
  if t >= RUN_END then m:exit() end
end)
