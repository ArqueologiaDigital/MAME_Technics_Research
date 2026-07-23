-- inject.lua -- play a note on the KN5000 sub-CPU by injecting MIDI bytes straight
-- into its inter-CPU ring buffer (0x2B0D struct: +0 wr idx, +2 rd idx @0x2B0F,
-- +4 count @0x2B11, +6 data @0x2B13). The main CPU is wedged (dark LCD) so the
-- buffer is idle and ours to drive. MIDI_Dispatch runs continuously in the audio
-- loop and will parse [0x90,ch,note,vel] -> Voice_NoteOn -> ToneGen_WriteVoiceParams.
-- Watches subcpu 0x130000 (Felipe's ADSR candidate) and IC303 0x100000 over the note.
local RUNDIR = "/home/fsanches/compartilhado/kn7000_mame/kn5000_envrun"
local TAG    = os.getenv("TAG") or "inject"
local PROG   = tonumber(os.getenv("PROG") or "-1")   -- >=0 => send Program Change first
local NOTE   = tonumber(os.getenv("NOTE") or "60")
local VEL    = tonumber(os.getenv("VEL")  or "100")
local T_ARM  = tonumber(os.getenv("T_ARM") or "8.0")
local T_ON   = tonumber(os.getenv("T_ON")  or "8.3")
local T_OFF  = tonumber(os.getenv("T_OFF") or "9.8")
local T_END  = tonumber(os.getenv("T_END") or "10.8")
local logf = io.open(RUNDIR.."/inj_"..TAG..".log","w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local dbg  = mach.debugger
local sub  = mach.devices[":subcpu"]
local sp   = sub.spaces["program"]

sub.debug:wpset(sp, "w", 0x130000, 0x20, "1", 'printf "D130 %06X=%04X", wpaddr, wpdata; g')
dbg.execution_state = "run"
LOG(("armed TAG=%s prog=%d note=%d vel=%d"):format(TAG,PROG,NOTE,VEL))

local RB   = 0x2B0D          -- struct base
local RDIX = 0x2B0F          -- read index (RingBuf_ReadByte uses XWA+2)
local CNT  = 0x2B11          -- count
local DATA = 0x2B13          -- 4KB data
local function inject(bytes)
  local rd  = sp:read_u16(RDIX)
  local cnt = sp:read_u16(CNT)
  -- append bytes at the tail = (rd + cnt) so we don't overwrite unread data
  local tail = (rd + cnt) & 0xFFF
  for i=1,#bytes do
    sp:write_u8(DATA + ((tail + (i-1)) & 0xFFF), bytes[i])
  end
  sp:write_u16(CNT, cnt + #bytes)
  LOG(("inject %d bytes at tail=0x%03X (rd=0x%03X cnt=%d->%d): %s")
      :format(#bytes, tail, rd, cnt, cnt+#bytes, table.concat(bytes,",")))
end

local mark=0; local st={}
local function once(k) if st[k] then return false end st[k]=true; return true end
local function dumpfrom(m,l) local cl=dbg.consolelog; LOG(("---- %s [%d..%d] ----"):format(l,m+1,#cl)); for i=m+1,#cl do LOG(cl[i]) end end

_G._inj = emu.add_machine_frame_notifier(function()
  local ok,err = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds/1e18
    if t>=T_ARM and once("arm") then
      mach.video:snapshot()
      local cl=dbg.consolelog; local n=0
      for i=1,#cl do local s=cl[i]; if type(s)=="string" and s:find("D130") then n=n+1 end end
      LOG("BOOT D130 count="..n); mark=#cl
      LOG(("ringbuf pre: rd=0x%03X wr=0x%03X cnt=%d"):format(sp:read_u16(RDIX), sp:read_u16(RB), sp:read_u16(CNT)))
      sub.debug:wpset(sp, "w", 0x100000, 4, "1", 'printf "IC303 %06X=%04X", wpaddr, wpdata; g')
      LOG("IC303 wp armed")
    end
    if t>=T_ON and once("on") then
      if PROG>=0 then inject({0xC0, 0x00, PROG & 0x7f}) end
      inject({0x90, 0x00, NOTE & 0x7f, VEL & 0x7f})
      LOG(("NOTE ON @%.3f"):format(t))
    end
    if t>=(T_ON+T_OFF)/2 and once("mid") then
      mach.video:snapshot(); LOG("mid snap; ringbuf cnt="..sp:read_u16(CNT))
    end
    if t>=T_OFF and once("off") then
      inject({0x90, 0x00, NOTE & 0x7f, 0x00})   -- vel 0 = note off
      LOG(("NOTE OFF @%.3f"):format(t))
    end
    if t>=T_END and once("end") then
      dumpfrom(mark,"PLAY WINDOW"); mach.video:snapshot(); LOG("DONE")
    end
  end)
  if not ok then LOG("ERR "..tostring(err)) end
end)
