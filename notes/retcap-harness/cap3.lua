-- Bulletproof per-effect map: for each effect button, snapshot the FULL group-0x20 file,
-- toggle it once, snapshot again, print the diff. Isolated + full-range (ch00-3F, all regs).
local mac = manager.machine
local prog = mac.devices[":maincpu"].spaces["program"]
local OUT = "/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/c6cf97f4-b4f1-4ba1-adc0-85474706b167/scratchpad/retcap"
local logf = io.open(OUT .. "/cap3.log", "w")
local function L(s) logf:write(s .. "\n"); logf:flush() end
local function T() local t = mac.time; return t.seconds + t.attoseconds / 1e18 end
local function setbtn(seg, mk, v)
  for _, f in pairs(mac.ioport.ports[":" .. seg].fields) do if f.mask == mk then f:set_value(v) end end
end
_G.k = {}
local latch = 0
local reg = {}
local function nm(a) return string.format("ch%02X.r%X(0x%04X)", (a>>4)&0x3F, a&0xF, a) end
_G.k[#_G.k+1] = prog:install_write_tap(0x98050000, 0x98050003, "t",
  function(off, data, mask)
    if (mask & 0x0000FFFF) ~= 0 then latch = data & 0xFFFF; return end
    if (mask & 0xFFFF0000) == 0 then return end
    local a = latch
    if (a & 0xFC00) == 0x8000 then reg[a] = (data >> 16) & 0xFFFF end
  end)
local function snap() local s={} for a=0x8000,0x83FF do if reg[a] then s[a]=reg[a] end end return s end
local function diff(before, after, tag)
  L("== "..tag.." ==")
  local any=false
  for a=0x8000,0x83FF do
    if before[a]~=after[a] then L(string.format("   %-22s : 0x%04X -> 0x%04X", nm(a), before[a] or 0, after[a] or 0)); any=true end
  end
  if not any then L("   (no group-0x20 change)") end
end
local btns = {{"REVERB","SEG0F",0x04},{"SOUNDDSP","SEG0F",0x08},{"MULTI","SEG10",0x04},{"DIGEFFECT","SEG10",0x08},{"CHORUS","SEG11",0x04}}
local plan = {}
local t0 = 24.0
local pend = nil
for _, b in ipairs(btns) do
  plan[#plan+1] = {t0,     function() pend = snap(); setbtn(b[2],b[3],1) end}
  plan[#plan+1] = {t0+0.25,function() setbtn(b[2],b[3],0) end}
  plan[#plan+1] = {t0+1.7, function() diff(pend, snap(), b[1].." toggle ("..b[2].." "..string.format("0x%02X",b[3])..")") end}
  t0 = t0 + 2.5
end
plan[#plan+1] = {t0+0.5, function() L("DONE"); logf:close(); mac:exit() end}
local pi=1
_G.k[#_G.k+1] = emu.add_machine_frame_notifier(function()
  local t=T(); while pi<=#plan and t>=plan[pi][1] do plan[pi][2](); pi=pi+1 end
end)
print("[CAP3] armed")
