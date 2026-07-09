-- Stage-2 tone-generator diagnostic for the KN7000 driver.
-- Answers: when a keybed note is pressed, does the FIRMWARE emit TG voice writes?
-- Findings (2026-07-09): NO. The note is consumed from the FIFO (0x98050004) by
-- the program.asm reader at PC 0x484480A2 and turned into a per-key struct by
-- 0x4844812D, but region2's flush (0x487eff80) emits only idle 0xFC0x refreshes.
-- No pitch/key-on/param write of any class happens during the press window.
--
-- Usage: mame kn7000 ... -autoboot_delay 0 -autoboot_script stage2_tg_diagnostic.lua
-- (NEVER pass -video none.)  Retains all tap/notifier handles in _G so GC does
-- not silently unsubscribe them; program space is 32-bit so taps span base..base+3.
local mac=manager.machine; local cpu=mac.devices[":maincpu"]; local prog=cpu.spaces["program"]
_G._keep={}
local tg_addr={0,0}; local voice=0; local idle=0; local watching=false
local classhist={}; local pollpc={}; local consumepc={}
local function wtap(base,idx,label)
  _G._keep[#_G._keep+1]=prog:install_write_tap(base,base+3,"tgw"..idx,function(off,data,mask)
    if (mask & 0x0000ffff)~=0 then tg_addr[idx]=data & 0xffff end
    if (mask & 0xffff0000)~=0 then
      local a=tg_addr[idx]; local cls=a&0xfc0f
      if watching then classhist[cls]=(classhist[cls] or 0)+1 end
      if (a & 0xff00)==0xfc00 then if watching then idle=idle+1 end
      elseif watching then voice=voice+1 end
    end
    return nil
  end)
end
wtap(0x98040000,1,"MAIN"); wtap(0x98050000,2,"SUB")
_G._keep[#_G._keep+1]=prog:install_read_tap(0x98050004,0x98050007,"fifo",function(off,data,mask)
  if watching and (mask & 0xffff)~=0 then
    local pc=cpu.state["CURPC"].value; pollpc[pc]=(pollpc[pc] or 0)+1
    if (data & 0xffff)~=0xffff then consumepc[pc]=(consumepc[pc] or 0)+1 end
  end
  return nil
end)
local function setkey(name,v) for fn,f in pairs(mac.ioport.ports[":KEYS0"].fields) do if fn==name then f:set_value(v);return true end end end
local step=0
_G._keep[#_G._keep+1]=emu.add_machine_frame_notifier(function()
  local t=mac.time.seconds
  if step==0 and t>=16 then step=1; watching=true; setkey("Key C4",1); print("t=16 press C4")
  elseif step==1 and t>=18 then step=2; setkey("Key C4",0); setkey("Key E4",1)
  elseif step==2 and t>=20 then step=3; setkey("Key E4",0); setkey("Key G4",1)
  elseif step==3 and t>=22 then step=4; setkey("Key G4",0)
  elseif step==4 and t>=24 then step=5; watching=false
    print(("RESULT voiceWrites=%d idle=%d"):format(voice,idle))
    print("-- FIFO poll PCs --"); for pc,c in pairs(pollpc) do print(("  pc=%08X polls=%d consumed=%d"):format(pc,c,consumepc[pc] or 0)) end
    print("-- non-idle classes seen while watching --")
    local ks={}; for k in pairs(classhist) do ks[#ks+1]=k end; table.sort(ks)
    for _,k in ipairs(ks) do print(("  class %04X : %d"):format(k,classhist[k])) end
  end
end)
print("stage2_tg_diagnostic armed")
