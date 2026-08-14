-- intc_core_verify.lua -- INTC+TM5-in-CPU-core refactor live verification (Integrate stage).
-- The on-chip interrupt controller and the TM4/TM5 tempo timer moved from driver
-- HLE into the mn10300 core; every interrupt path must behave exactly as before:
-- (a) boot to home -> snapshot (panel serial handshake incl. group 0x11 c11
--     re-delivery + group 0x1A ATN + EXTMD re-arm all through the core)
-- (b) keybed C4 press -> firmware TG voice writes (key FIFO poll + sys tick)
-- (c) RHYTHM GROUP BALLAD -> genre list snapshot (panel events cpanel->core)
-- (d) SD MENU toggle -> SD menu snapshot (SD card-detect group-0x1B ICR pokes)
-- (e) DEMO + START/STOP -> ~20 s of demo song; the 96-PPQN beat phase at
--     0x50149664 must advance (TM5 underflow -> core INTC group 7 -> ISR).
local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

-- TG write tap (proves the keybed note reaches the tone generator)
local tg_addr = {0,0}
local voice = 0
local watching = false
local function tap(base, idx, label)
  prog:install_write_tap(base, base+3, "tg"..idx, function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then tg_addr[idx] = data & 0xffff end
    if (mask & 0xffff0000) ~= 0 then
      local a = tg_addr[idx]
      if (a & 0xff00) ~= 0xfc00 and watching then voice = voice + 1 end
    end
    return nil
  end)
end
tap(0x98040000, 1, "MAIN")
tap(0x98050000, 2, "SUB")

local function setkey(name, v)
  for _,f in pairs(mac.ioport.ports[":KEYS0"].fields) do
    if f.name == name then f:set_value(v); return true end end
  return false
end
local function press(tag, mask, v)
  local p = mac.ioport.ports[tag]
  if p == nil then log("[intc] ERROR: port "..tag.." missing"); return end
  p:field(mask):set_value(v)
end

local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end

at(27.5, "home snapshot",      function() mac.video:snapshot() end)
at(28.0, "C4 press (watch TG)",function() watching = true; setkey("Key C4", 1) end)
at(29.0, "C4 release",         function() setkey("Key C4", 0) end)
at(29.8, "TG result",          function()
  watching = false
  log(("[intc] keybed C4 -> %d non-FC TG voice writes (%s)"):format(
    voice, voice > 0 and "OK firmware drives the TG" or "FAIL no voice writes"))
end)
at(30.0, "BALLAD press",       function() press(":cpanel:CPL_SEG2", 0x08, 1) end)
at(30.4, "BALLAD release",     function() press(":cpanel:CPL_SEG2", 0x08, 0) end)
at(32.5, "genre-list snapshot",function() mac.video:snapshot() end)
at(33.0, "SD MENU press",      function() press(":cpanel:CPR_SEG1", 0x80, 1) end)
at(33.4, "SD MENU release",    function() press(":cpanel:CPR_SEG1", 0x80, 0) end)
at(36.5, "SD-menu snapshot",   function() mac.video:snapshot() end)
at(37.0, "SD MENU press (toggle home)", function() press(":cpanel:CPR_SEG1", 0x80, 1) end)
at(37.4, "SD MENU release",    function() press(":cpanel:CPR_SEG1", 0x80, 0) end)
at(39.0, "DEMO press",         function() press(":cpanel:CPL_SEG6", 0x40, 1) end)
at(39.4, "DEMO release",       function() press(":cpanel:CPL_SEG6", 0x40, 0) end)
at(42.0, "demo-screen snapshot", function() mac.video:snapshot() end)
at(43.0, "START/STOP press",   function() press(":cpanel:CPL_SEG0", 0x10, 1) end)
at(43.4, "START/STOP release", function() press(":cpanel:CPL_SEG0", 0x10, 0) end)
local beat1 = -1
at(48.0, "beat phase probe 1", function()
  beat1 = prog:read_u8(0x50149664)
  log(("[intc] t=48 beat phase 0x50149664 = 0x%02X"):format(beat1))
end)
at(58.0, "beat phase probe 2 + verdict", function()
  local beat2 = prog:read_u8(0x50149664)
  log(("[intc] t=58 beat phase 0x50149664 = 0x%02X (%s)"):format(
    beat2, (beat2 ~= beat1) and "ADVANCING: TM5->core INTC group 7 ISR ALIVE"
                             or "STUCK: tempo timer NOT ticking"))
end)
at(62.0, "demo-playing snapshot + exit", function() mac.video:snapshot(); log("[intc] gauntlet done"); mac:exit() end)

local i = 1
emu.register_periodic(function()
  local now = mac.time.seconds + mac.time.attoseconds/1e18
  while i <= #acts and now >= acts[i].t do
    local a = acts[i]; i = i + 1
    local ok, err = pcall(a.fn)
    if not ok then log("[intc] ERR "..tostring(a.desc)..": "..tostring(err))
    elseif a.desc ~= "" then log(("[intc][%6.1f] %s"):format(now, a.desc)) end
  end
end)
log("intc_core_verify armed")
