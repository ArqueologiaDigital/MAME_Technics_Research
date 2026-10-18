-- seq_probe.lua -- KN7000 MAME: does an ordinary sequencer song loaded from SD (TECHNICS
-- format, TFLD001/01001KN7.*) bring its 01001KN7.ACT and pictures into the main slide-show
-- pool, and are the pictures shown at the song's PIC points under SEQUENCER PLAY?
-- Media: sd_seq.img from build_seq_sd.py.  Key map from kn7000_mame/tools/
-- sd_roundtrip_load.lua (SD CARD LOAD = CPR_SEG1 0x80, LCDR1 = CPR_SEG5 0x10) and
-- kn7000_mame/notes/AUTONOMOUS-STATUS.md (SEQUENCER PLAY = SEG0D 0x08 = CPR_SEG1 0x08);
-- START/STOP = CPL_SEG0 0x10.  REQUIRES the debug core.  Env PROBE_TAG, RUN_END.
-- run (from <lane>/mamerun):
--   PROBE_TAG=SEQ1 /home/fsanches/compartilhado/kn7000_mame_build/kn7000 kn7000 \
--     -rompath /home/fsanches/compartilhado/technics_romsets -harddisk <lane>/sd_seq.img \
--     -video none -sound none -nothrottle -debug -debugger none -seconds_to_run 150 \
--     -snapshot_directory <lane>/mamerun/snap_SEQ1 -nvram_directory <lane>/mamerun/nvram_SEQ1 \
--     -autoboot_delay 0 -autoboot_script <lane>/seq_probe.lua
local LANE = "/home/fsanches/compartilhado/tmp/kn7000-act/runtime"
local TAG = os.getenv("PROBE_TAG") or "SEQ"
local RUN_END = tonumber(os.getenv("RUN_END") or "145")
local T_PLAY = tonumber(os.getenv("T_PLAY") or "44")
local DUMPDIR = LANE .. "/dumps_" .. TAG
os.execute("mkdir -p " .. DUMPDIR)
local logf = io.open(LANE .. "/seq_probe_" .. TAG .. ".log", "w")
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
  -- call targets are the *_entry labels (the call instruction itself does the movm/add sp);
  -- SEQ1 used the movm addresses 0x4852C10C/0x4857EE8D/0x4858070A, which never fire.
  {0x4852C111, 'printf "BP SeqActFileLoad_entry a0=%08X%08X%08X%08X\\n", ' .. S4("a0") .. '; g'},
  {0x4857EE92, 'printf "BP SswSongActLoad_entry d0=%X\\n", d0; g'},
  {0x4858070F, 'printf "BP SswActOpen_entry name=%08X%08X%08X%08X\\n", ' .. S4("a0") .. '; g'},
  {0x48458705, 'temp0=temp0+1; g'},   -- sequencer event decoder (status dispatch, 0x8A at 0x48458745): count only
  {0x48580882, 'printf "BP SswActScriptLoad -> d3=%X\\n", d3; g'},
  {0x48565814, 'printf "BP SD fmmopen name=%08X%08X%08X%08X\\n", ' .. S4("a0") .. '; g'},
  {0x48580F9D, 'printf "BP SswImageFileLoad name=%08X%08X%08X%08X\\n", ' .. S4("a0") .. '; g'},
  {0x4857EDC2, 'printf "BP PicParam 0x600014 param=%X\\n", d0; g'},
  {0x4857E444, 'printf "BP PicEvent d0=%X\\n", d0; g'},
  {0x4858099B, 'printf "BP PicDispatch d0=%X\\n", d0; g'},
  {0x4857F5ED, 'printf "BP ACT tag mode=%X\\n", d1; g'},
  {0x4857FA7E, 'printf "BP IMG tag mode=%X\\n", d1; g'},
  {0x4858056C, 'printf "BP SswDrawImage_entry a0=%X\\n", a0; g'},
  {0x48546326, 'printf "BP StartStopInDemo d0=%X d1=%X\\n", d0, d1; g'},
}
for _, b in ipairs(BPS) do cpu.debug:bpset(b[1], "1", b[2]) end
dbg.execution_state = "run"
LOG("breakpoints armed: " .. #BPS)
local nsnap = 0
local function snap(why) mach.video:snapshot(); nsnap = nsnap + 1; LOG(("[%.2f] snap #%d %s"):format(mach.time:as_double(), nsnap, why)) end
local function dump_pool(name, pb)
  LOG(("pool %s @%08X: +0x20 script=%08X '%s' +0x24=%08X +0x28=%08X"):format(name, pb, rd32(pb + 0x20),
      rd32(pb + 0x20) ~= 0 and cstr(rd32(pb + 0x20), 16) or "", rd32(pb + 0x24), rd32(pb + 0x28)))
  dump(name .. "_pool_hdr.bin", pb, 0x1000)
  for n = 0, 30 do local p = rd32(pb + 0x30 + 4 * n); if p ~= 0 then LOG(("  ACT[%d] -> %08X '%s'"):format(n, p, cstr(p, 30))) end end
  for k = 0, 63 do local r = pb + 0x5F0 + 0x20 * k; local nm = cstr(r, 16)
    if nm ~= "" then LOG(("  named[%d] @%08X '%s' %08X %08X %08X %08X"):format(k, r, nm, rd32(r + 0x10), rd32(r + 0x14), rd32(r + 0x18), rd32(r + 0x1C))) end end
end
local plan = {}
local function at(sec, fn) table.insert(plan, {sec, fn, false}) end
at(25.5, function() snap("home before SD load") end)
at(26, function() LOG("press SD CARD LOAD"); setbtn("CPR_SEG1", 0x80, 1) end)
at(26.4, function() setbtn("CPR_SEG1", 0x80, 0) end)
at(28.5, function() snap("SD menu"); LOG("press LCDR1 (LOAD)"); setbtn("CPR_SEG5", 0x10, 1) end)
at(28.9, function() setbtn("CPR_SEG5", 0x10, 0) end)
at(32, function() snap("SD load browser"); LOG("press LCDR1 (LOAD execute)"); setbtn("CPR_SEG5", 0x10, 1) end)
at(32.4, function() setbtn("CPR_SEG5", 0x10, 0) end)
at(40, function() snap("after load"); dump_pool("t40_main", 0x502031A0)
  dump("t40_songrecords_501A5800.bin", 0x501A5800, 0x58C0)
  dump("t40_pagestore_501AB9A0.bin", 0x501AB9A0, 0x7F00)
  dump("t40_seqvars_5003D308.bin", 0x5003D308, 0x64) end)
-- SEQ1/SEQ2 showed that the SD LOAD itself ends on the SEQUENCER PLAY display (snapshot at
-- t=40), so pressing SEQUENCER PLAY then toggles it OFF (home display) and START/STOP starts
-- the rhythm instead.  SKIP_SEQPLAY=1 leaves the display as the load left it.
if os.getenv("SKIP_SEQPLAY") ~= "1" then
  at(T_PLAY, function() LOG("press SEQUENCER PLAY"); setbtn("CPR_SEG1", 0x08, 1) end)
  at(T_PLAY + 0.4, function() setbtn("CPR_SEG1", 0x08, 0) end)
end
at(T_PLAY + 3, function() snap("SEQUENCER PLAY display") end)
-- SEQ_RESET=1: manual p.83 step 4, SEQUENCER RESET (FILL IN 1 = CPL_SEG3 0x10) before START/STOP
if os.getenv("SEQ_RESET") == "1" then
  at(T_PLAY + 2, function() LOG("press SEQUENCER RESET (FILL IN 1)"); setbtn("CPL_SEG3", 0x10, 1) end)
  at(T_PLAY + 2.4, function() setbtn("CPL_SEG3", 0x10, 0) end)
end
at(T_PLAY + 4, function() LOG("press START/STOP"); setbtn("CPL_SEG0", 0x10, 1) end)
at(T_PLAY + 4.4, function() setbtn("CPL_SEG0", 0x10, 0) end)
at(T_PLAY + 4.8, function() snap("0.8 s after START/STOP") end)
at(T_PLAY + 6.5, function() dump("tplay_seqvars_5003D308.bin", 0x5003D308, 0x64) end)
for s = T_PLAY + 6, RUN_END, 6 do at(s, function() snap("periodic t=" .. s); dbg:command('printf "event decoder calls so far: %d\\n", temp0') end) end
at(RUN_END, function() dump_pool("tend_main", 0x502031A0) end)
local pending, lastn, ndisp = {}, 0, 0
_G._seq_sub = emu.add_machine_frame_notifier(function()
  local t = mach.time:as_double()
  for _, p in ipairs(plan) do
    if not p[3] and t >= p[1] then p[3] = true
      local ok, err = pcall(p[2]); if not ok then LOG("!! step error: " .. tostring(err)) end end
  end
  for i = #pending, 1, -1 do
    if t >= pending[i][1] then local pd = table.remove(pending, i); pcall(snap, "after PicDispatch " .. pd[2]) end
  end
  local cl = dbg.consolelog
  while lastn < #cl do lastn = lastn + 1; local line = cl[lastn]
    if line ~= "" then LOG(string.format("[%.2f] %s", t, line))
      local d = line:match("BP PicDispatch d0=(%x+)")
      if d then ndisp = ndisp + 1; table.insert(pending, {t + 0.6, d}) end end
  end
end)
LOG("seq_probe.lua armed")
