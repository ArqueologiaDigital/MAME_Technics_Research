local mac=manager.machine; local cpu=mac.devices[":maincpu"]; local prog=cpu.spaces["program"]
_G._keep={}
local curidx=0; local addrbuf={}; local pending_addr=nil; local blocks={}; local bulk=0
-- index port 0x98000000 (write sets the DSP register index)
_G._keep[1]=prog:install_write_tap(0x98000000,0x98000003,"idx",function(off,data,mask)
  if (mask&0xffff)~=0 then curidx=data&0xffff end
  return nil end)
-- data port 0x9C000000
_G._keep[2]=prog:install_write_tap(0x9c000000,0x9c000003,"dat",function(off,data,mask)
  if (mask&0xffff)==0 then return nil end
  local d=data&0xffff
  if curidx==0x40 then addrbuf[#addrbuf+1]=d
    if #addrbuf==2 then pending_addr=(addrbuf[2]<<16)|addrbuf[1]; addrbuf={} end   -- little: first=low
  elseif curidx==0x1c then
    local mode = (d==0xa1) and "PM" or (d==0x41) and "DM" or (d==0xa0) and "END" or string.format("cmd%02X",d)
    if mode=="PM" or mode=="DM" then
      blocks[#blocks+1]={addr=pending_addr or -1, mode=mode, words=bulk}
    end
    bulk=0
  else
    -- bulk data streamed while idx not a control reg
    bulk=bulk+1
  end
  return nil end)
_G._keep[3]=emu.add_machine_frame_notifier(function()
  if mac.time.seconds>=12 and not _G.done then _G.done=true
    print(("== DSP upload blocks captured: %d =="):format(#blocks))
    local seen={}
    for i,b in ipairs(blocks) do
      if i<=40 then print(("  block %2d: %s @ 0x%06X"):format(i,b.mode,b.addr>=0 and b.addr or 0)) end
      seen[string.format("%s@0x%X",b.mode,b.addr>=0 and b.addr or 0)]=true
    end
    print("== distinct (mode@addr) targets ==")
    local ks={}; for k in pairs(seen) do ks[#ks+1]=k end; table.sort(ks)
    for _,k in ipairs(ks) do print("  "..k) end
  end
end)
print("dspup armed")
