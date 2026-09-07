-- Verify the deterministic effect trigger: poke CPU2 twin program + change flag,
-- confirm the firmware resolves it and re-uploads to the DSP.
local mac = manager.machine
local c2  = mac.devices[":cpu2"]
local sp  = c2 and c2.spaces["program"] or nil
local function dsp(d) local dev=mac.devices[":dsp"..d]; local ir,cr=dev.spaces["iram"],dev.spaces["cram"]
  local i=0; for w=0,383 do for k=0,4 do if ir:read_u8(w*5+k)~=0 then i=i+1;break end end end
  local is=0; for w=0,383*5-1 do is=(is+ir:read_u8(w)*(w+1))&0xffffffff end
  local c,cs=0,0; for x=0,255 do local v=cr:read_u32(x)&0xffffff; if v~=0 then c=c+1 end; cs=(cs+v*(x+1))&0xffffffff end
  return string.format("I=%d/%08X C=%d/%08X",i,is,c,cs) end
local function state()
  return string.format("twin0=%d live0=%d rec0=%d flag=%02X",
    sp:read_u8(0x7E7E), sp:read_u8(0x856E), sp:read_u8(0x8586), sp:read_u8(0x7ECC)) end
local function snap(t) print(string.format("[%-12s] %s | d0(IC6) %s | d2(IC30) %s",t,state(),dsp(0),dsp(2))) end

local acts={}; local function A(f,fn) acts[#acts+1]={f=f,fn=fn} end
A(900, function() if not sp then print("NO :cpu2 program space!"); return end
                  print("cpu2 space OK"); snap("baseline") end)
-- Load CHORUS (effect 1) into unit0 (IC6)
A(950, function() print("-> poke twin0=1 (CHORUS), flag|=0x02"); sp:write_u8(0x7E7E,1); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x02) end)
A(1010,function() snap("after N=1 t+1s") end)
A(1130,function() snap("after N=1 t+3s") end)
-- Load SINGLE DELAY (effect 9) into unit0
A(1200,function() print("-> poke twin0=9, flag|=0x02"); sp:write_u8(0x7E7E,9); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x02) end)
A(1320,function() snap("after N=9 t+2s") end)
-- Load GATED REVERB (effect 8)
A(1400,function() print("-> poke twin0=8, flag|=0x02"); sp:write_u8(0x7E7E,8); sp:write_u8(0x7ECC, sp:read_u8(0x7ECC)|0x02) end)
A(1520,function() snap("after N=8 t+2s") end)
A(1560,function() print("TWIN DONE") end)

_G._f=0
_G._h=emu.add_machine_frame_notifier(function() _G._f=_G._f+1
  for _,a in ipairs(acts) do if a.f==_G._f then a.fn() end end end)
