-- pres_probe.lua -- KN7000 MAME: does a KN7000-form FEATURE presentation (FEATURE.PRE +
-- <base>.SQT 'J KD' with picture events + <base>.ACT 'SSW-ACT-V01' + JPEGs) load on the
-- DEMONSTRATION screen, and do its pictures change on screen as the song plays?
-- Derived from featurepre/feature_probe.lua (same breakpoints and forcing), plus: picture
-- event / dispatch / draw breakpoints, a snapshot 0.6 s after every picture dispatch,
-- periodic snapshots, RAM dumps (song at 0x502C0000, demo pool header, pool+0x30 ACT
-- table, named-image records) and raw frame-buffer + CLUT dumps for render_fb.py.
-- REQUIRES the debug core.  Env:
--   PROBE_TAG     log / dump name suffix
--   FEATURE_IMG   floppy image to insert at t=25 (raw 1.44 MB FAT12)
--   FORCE_PRESENCE=1  clear the FDC DSKCHG bit (MAME never clears it; featurepre poll_probe)
--   FORCE_SD=1    also force the two floppy-only gates and switch the fmm drive byte
--                 0x5007125A to 1 (SD) before FeaturePreLoad: files come from -harddisk
--   RUN_END       seconds after which to stop taking periodic snapshots (default 130)
-- run (from <lane>/mamerun):
--   PROBE_TAG=SD1 FEATURE_IMG=<lane>/weserl_floppy.img FORCE_PRESENCE=1 FORCE_SD=1 \
--   /home/fsanches/compartilhado/kn7000_mame_build/kn7000 kn7000 \
--     -rompath /home/fsanches/compartilhado/technics_romsets -harddisk <lane>/sd_weserl.img \
--     -video none -sound none -nothrottle -debug -debugger none -seconds_to_run 135 \
--     -snapshot_directory <lane>/mamerun/snap_SD1 -cfg_directory <lane>/mamerun/cfg \
--     -nvram_directory <lane>/mamerun/nvram -autoboot_delay 0 \
--     -autoboot_script <lane>/pres_probe.lua
local LANE = "/home/fsanches/compartilhado/tmp/kn7000-act/runtime"
local TAG = os.getenv("PROBE_TAG") or "X"
local IMG = os.getenv("FEATURE_IMG")
local FORCE_SD = os.getenv("FORCE_SD") == "1"
local RUN_END = tonumber(os.getenv("RUN_END") or "130")
local SNAP_DELAY = tonumber(os.getenv("SNAP_DELAY") or "0.6")   -- s after a PicDispatch (SD2: 2.8)
local DUMPDIR = LANE .. "/dumps_" .. TAG
os.execute("mkdir -p " .. DUMPDIR)
local logf = io.open(LANE .. "/pres_probe_" .. TAG .. ".log", "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s .. "\n"); logf:flush() end end

local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local mem  = cpu.spaces["program"]

local function setbtn(p, mk, v)
  local port = mach.ioport.ports[":cpanel:" .. p] or mach.ioport.ports[":" .. p]
  if not port then LOG("!! no port " .. p); return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v); return end end
  LOG(("!! no field %s %02X"):format(p, mk))
end
local function rd32(a) return mem:read_u32(a) end
local function dump(name, addr, len)
  local t = {}
  for i = 0, len - 1 do t[#t + 1] = string.char(mem:read_u8(addr + i)) end
  local f = io.open(DUMPDIR .. "/" .. name, "wb"); f:write(table.concat(t)); f:close()
  LOG(("dump %s 0x%08X len 0x%X"):format(name, addr, len))
end
local function cstr(a, max)
  local t = {}
  for i = 0, (max or 32) - 1 do local c = mem:read_u8(a + i); if c == 0 then break end; t[#t + 1] = string.char(c) end
  return table.concat(t)
end

local S4 = function(r) return ("d@(%s), d@(%s+4), d@(%s+8), d@(%s+0xc)"):format(r, r, r, r) end
local BPS = {
  {0x48402758, 'printf "BP floppy present -> LibParamSet(0x10708000,1)\\n"; g'},
  {0x4854DBC0, 'printf "BP MdDemo 0x50014 with code 0x708000\\n"; g'},
  {0x4854DBE0, 'printf "BP  ... title == 0xF00CF (DEMO)\\n"; g'},
  {0x4854DC0E, 'printf "BP  ... floppy check func_4854DAA5 -> d0=%X\\n", d0; ' .. (FORCE_SD and 'd0=0; ' or '') .. 'g'},
  {0x4854DC23, 'printf "BP  ... FEATURE .PRE exists -> d0=%X\\n", d0; ' .. (FORCE_SD and 'd0=1; ' or '') .. 'g'},
  {0x4854DC36, 'printf "BP  ... calling FeaturePreLoad, ext mode=%X\\n", b@0x5007125a; ' .. (FORCE_SD and 'b@0x5007125a=1; ' or '') .. 'g'},
  {0x48565814, 'printf "BP SD fmmopen name=%08X%08X%08X%08X\\n", ' .. S4("a0") .. '; g'},
  {0x4854DC3B, 'printf "BP FeaturePreLoad d0=%X sqt=%08X%08X%08X%08X act=%08X%08X%08X%08X title=%08X%08X%08X%08X\\n", d0, ' .. S4("a2") .. ', ' .. S4("a3") .. ', ' .. S4("d2") .. '; g'},
  {0x4854DC4F, 'printf "BP FeatureDemoSqtLoad -> d0=%X  (0x5008294C=%X len=%X pool=%X size=%X)\\n", d0, d@0x5008294c, d@0x50082950, d@0x50082954, d@0x50082958; g'},
  {0x4854DC5A, 'printf "BP FeatureDemoActLoad -> d0=%X\\n", d0; g'},
  {0x48580882, 'printf "BP SswActScriptLoad -> d3=%X\\n", d3; g'},
  {0x48580F9D, 'printf "BP SswImageFileLoad name=%08X%08X%08X%08X\\n", ' .. S4("a0") .. '; g'},
  {0x485464BE, 'printf "BP SrtExtDemo d0=%X\\n", d0; g'},
  {0x48457355, 'printf "BP DemoSongLoad d0=%X\\n", d0; g'},
  {0x4854E37B, 'printf "BP StartFeatureDemo d0=%X\\n", d0; g'},
  {0x4857EDC2, 'printf "BP PicParam 0x600014 param=%X\\n", d0; g'},
  {0x4857E444, 'printf "BP PicEvent d0=%X\\n", d0; g'},
  {0x4858099B, 'printf "BP PicDispatch d0=%X\\n", d0; g'},
  {0x48580A6D, 'printf "BP PicDispatch end\\n"; g'},
  {0x4857F5ED, 'printf "BP ACT tag mode=%X\\n", d1; g'},
  {0x4857FA7E, 'printf "BP IMG tag mode=%X\\n", d1; g'},
  -- call target is SswDrawImage_entry (SD1 used the movm address 0x4858056A, which a call skips)
  {0x4858056C, 'printf "BP SswDrawImage_entry a0=%X (first bytes %08X)\\n", a0, d@a0; g'},
  {0x48580F4F, 'printf "BP GetSswObjectID NOT FOUND\\n"; g'},
  {0x4854E3E7, 'printf "BP EndFeatureDemo (EV_DEMOSONGEND)\\n"; g'},
  {0x4854DEE4, 'printf "BP AcDemoFdSelect EV_DEMOSONGNAME title=%08X%08X%08X%08X\\n", ' .. S4("d@(sp+0x30)") .. '; g'},
  {0x4854E1FE, 'printf "BP func_4854E1FE start external demo, song data %X\\n", d@0x5008294c; g'},
}
if not cpu.debug then
  LOG("!! cpu.debug is nil -- relaunch with -debug -debugger none")
else
  for _, b in ipairs(BPS) do cpu.debug:bpset(b[1], "1", b[2]) end
  dbg.execution_state = "run"
  LOG("breakpoints armed: " .. #BPS .. " image=" .. tostring(IMG) .. " FORCE_SD=" .. tostring(FORCE_SD))
end

local function floppy()
  for tag, img in pairs(mach.images) do
    if tag:find("fdc") or tag:find("flop") then return tag, img end
  end
end

local nsnap = 0
local function snap(why)
  mach.video:snapshot(); nsnap = nsnap + 1
  LOG(("[%.2f] snap #%d %s"):format(mach.time:as_double(), nsnap, why))
end
local function dump_fb(name)
  -- LcdOut 0x48414D71: FB byte p with (p & 0xF0) == 0xD0 is a direct-colour pixel
  -- (R = p & 0xF, G/B = the PICTURE_PLANE2 byte's nibbles); any other p goes through the
  -- RGB565 palette 0x50122AAC.  render_fb.py combines the three dumps the same way.
  dump(name .. "_fb.bin", 0x500D4080, 640 * 240)
  dump(name .. "_plane2.bin", 0x500F9880, 640 * 240)
  dump(name .. "_pal565.bin", 0x50122AAC, 0x200)
end
local function dump_state(name)
  LOG(("state %s: 0x5008294C=%08X len=%08X poolbase=%08X poolsize=%08X 0x5009CED4=%08X 0x5009CED0=%08X"):format(
      name, rd32(0x5008294C), rd32(0x50082950), rd32(0x50082954), rd32(0x50082958), rd32(0x5009CED4), rd32(0x5009CED0)))
  local pb = rd32(0x50082954)
  if pb ~= 0 then
    dump(name .. "_pool_hdr.bin", pb, 0x1000)
    local sc = rd32(pb + 0x20)
    LOG(("  pool+0x20 script=%08X '%s'"):format(sc, sc ~= 0 and cstr(sc, 24) or ""))
    LOG(("  pool+0x24 slideshow=%08X  pool+0x28 action=%08X '%s'"):format(rd32(pb + 0x24), rd32(pb + 0x28), rd32(pb + 0x28) ~= 0 and cstr(rd32(pb + 0x28), 40) or ""))
    for n = 0, 30 do
      local p = rd32(pb + 0x30 + 4 * n)
      if p ~= 0 then LOG(("  ACT[%d] -> %08X '%s'"):format(n, p, cstr(p, 36))) end
    end
    for k = 0, 63 do
      local r = pb + 0x5F0 + 0x20 * k
      local nm = cstr(r, 16)
      if nm ~= "" then LOG(("  named[%d] @%08X '%s' words %08X %08X %08X %08X"):format(k, r, nm, rd32(r + 0x10), rd32(r + 0x14), rd32(r + 0x18), rd32(r + 0x1C))) end
    end
  end
  dump(name .. "_song_502C0000.bin", 0x502C0000, 0x100)
  if os.getenv("DUMP_SONG") == "1" then dump(name .. "_songall_502C0000.bin", 0x502C0000, 0xD7C0) end
end

local plan = {}
local function at(sec, fn) table.insert(plan, {sec, fn, false}) end
at(20, function() LOG("press DEMO"); setbtn("CPL_SEG6", 0x40, 1) end)
at(20.4, function() setbtn("CPL_SEG6", 0x40, 0) end)
at(24, function() snap("DEMONSTRATION menu before insert") end)
at(25, function()
  local tag, img = floppy()
  LOG("insert floppy into " .. tostring(tag))
  if img and IMG then local r = img:load(IMG); LOG("load -> " .. tostring(r) .. " " .. tostring(img.filename)) end
  if os.getenv("FORCE_PRESENCE") == "1" then
    cpu.debug:bpset(0x48402637, "1", 'd0=d0&7f; g')
    cpu.debug:bpset(0x484026AC, "1", 'd0=d0&7f; g')
    cpu.debug:bpset(0x484026EB, "1", 'd0=d0&7f; g')
    LOG("FORCE_PRESENCE: DSKCHG bit forced clear from now on")
  end
end)
for s = 26, RUN_END, 4 do at(s, function() snap("periodic t=" .. s) end) end
at(33, function() dump_state("t33") end)
at(RUN_END, function() dump_state("tend"); dump_fb("tend") end)

local pending = {}
local lastn = 0
local ndisp = 0
_G._pres_sub = emu.add_machine_frame_notifier(function()
  local t = mach.time:as_double()
  for _, p in ipairs(plan) do
    if not p[3] and t >= p[1] then
      p[3] = true
      local ok, err = pcall(p[2]); if not ok then LOG("!! step error: " .. tostring(err)) end
    end
  end
  for i = #pending, 1, -1 do
    if t >= pending[i][1] then
      local pd = table.remove(pending, i)
      local ok, err = pcall(function() snap("after PicDispatch " .. pd[2]); dump_fb(("disp%02d"):format(pd[3])) end)
      if not ok then LOG("!! snap error: " .. tostring(err)) end
    end
  end
  if dbg then
    local cl = dbg.consolelog
    while lastn < #cl do
      lastn = lastn + 1
      local line = cl[lastn]
      if line ~= "" then
        LOG(string.format("[%.2f] %s", t, line))
        local d = line:match("BP PicDispatch d0=(%x+)")
        if d then ndisp = ndisp + 1; table.insert(pending, {t + SNAP_DELAY, d, ndisp}) end
      end
    end
  end
end)
LOG("pres_probe.lua armed")
