-- probe_chord.lua -- KN7000: reach MEMORY DUMP via the 1/4/5/8 UP+DOWN chord, log state.
-- Diagnostic only; the real harness is memdump_capture.lua.
local OUT = os.getenv("DG_OUT") or "/tmp/dg_probe.log"
local logf = io.open(OUT, "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end

local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local prog = cpu.spaces["program"]
local ioc  = mach.ioport

local function setbtn(p, mk, v)
  local port = ioc.ports[":cpanel:"..p]
  if not port then LOG("!! no port :"..p); return false end
  for _,f in pairs(port.fields) do if f.mask == mk then f:set_value(v); return true end end
  LOG(("!! no field %s mask %02X"):format(p, mk)); return false
end

-- balance/mixer column N -> {port, upmask, downmask}
local COL = {
  [1]={"CPC_SEG5",0x10,0x20}, [2]={"CPC_SEG5",0x40,0x80},
  [3]={"CPC_SEG8",0x01,0x02}, [4]={"CPC_SEG8",0x04,0x08},
  [5]={"CPC_SEG8",0x10,0x20}, [6]={"CPC_SEG8",0x40,0x80},
  [7]={"CPC_SEG9",0x01,0x02}, [8]={"CPC_SEG9",0x04,0x08},
  [9]={"CPC_SEG9",0x10,0x20}, [10]={"CPC_SEG9",0x40,0x80},
  [11]={"CPC_SEG10",0x01,0x02},[12]={"CPC_SEG10",0x04,0x08},
  [13]={"CPC_SEG10",0x10,0x20},[14]={"CPC_SEG10",0x40,0x80},
  [15]={"CPC_SEG11",0x01,0x02},[16]={"CPC_SEG11",0x04,0x08},
}

local HELD_UP, HELD_DN, HELD_BOTH = 0x50021FD8, 0x50021FDC, 0x50021FE0
local ADR = {0x500012EC,0x500012F0,0x500012F4,0x500012F8}
local SLOT = 0x5006B524

local function st()
  return ("up=%08X dn=%08X both=%08X | slot=%d A0=%08X A1=%08X A2=%08X A3=%08X"):format(
    prog:read_u32(HELD_UP), prog:read_u32(HELD_DN), prog:read_u32(HELD_BOTH),
    prog:read_u16(SLOT),
    prog:read_u32(ADR[1]), prog:read_u32(ADR[2]), prog:read_u32(ADR[3]), prog:read_u32(ADR[4]))
end

local LCD = 0x9ce00000
local function lcdhash()
  local h = 5381
  for i=0,153599,257 do h = ((h*33) + prog:read_u32(LCD + i*4)) & 0xffffffff end
  return h
end

local frame = 0
local plan = {}
local function at(f, fn) plan[f] = fn end

-- boot watch
for f=60,1200,120 do at(f, function() LOG(("t=%.1f f=%d hash=%08X %s"):format(frame/60, frame, lcdhash(), st())) end) end

-- chord: press one SEGMENT at a time, 60 frames apart
local seq = {
  {"CPC_SEG5", 0x30},   -- col1 UP|DOWN
  {"CPC_SEG8", 0x3C},   -- col4 UP|DOWN + col5 UP|DOWN
  {"CPC_SEG9", 0x0C},   -- col8 UP|DOWN
}
local T0 = 1260
for i,s in ipairs(seq) do
  local base = T0 + (i-1)*90
  at(base, function()
    LOG(("t=%.1f PRESS %s %02X"):format(frame/60, s[1], s[2]))
    for _,f in pairs(ioc.ports[":cpanel:"..s[1]].fields) do
      if (f.mask & s[2]) ~= 0 and (f.mask & (f.mask-1)) == 0 then f:set_value(1) end
    end
  end)
  at(base+30, function() LOG(("t=%.1f  after %s: %s"):format(frame/60, s[1], st())) end)
end
at(T0+3*90, function() LOG(("t=%.1f ALL HELD: %s hash=%08X"):format(frame/60, st(), lcdhash())) end)
at(T0+3*90+60, function() LOG(("t=%.1f still: %s hash=%08X"):format(frame/60, st(), lcdhash())) end)
-- release all
at(T0+3*90+90, function()
  for _,s in ipairs(seq) do
    for _,f in pairs(ioc.ports[":cpanel:"..s[1]].fields) do
      if (f.mask & s[2]) ~= 0 then f:set_value(0) end
    end
  end
  LOG(("t=%.1f RELEASED"):format(frame/60))
end)
for k=1,8 do
  at(T0+3*90+90+k*30, function() LOG(("t=%.1f post%d: %s hash=%08X"):format(frame/60,k,st(),lcdhash())) end)
end
at(T0+3*90+90+8*30+10, function() mach.video:snapshot(); LOG("snapshot taken") end)
at(T0+3*90+90+8*30+40, function() LOG("DONE"); if logf then logf:close() end; mach:exit() end)

DG_NOTIFIER = emu.add_machine_frame_notifier(function()
  frame = frame + 1
  local fn = plan[frame]
  if fn then fn() end
end)
LOG("probe_chord armed")
