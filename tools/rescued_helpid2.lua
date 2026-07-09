local scr
local BITS={{"SEG04",0x01},{"SEG06",0x01},{"SEG07",0x01},{"SEG0F",0x01},{"SEG10",0x01},
  {"SEG10",0x02},{"SEG11",0x01},{"SEG12",0x80},{"SEG13",0x01},{"SEG13",0x04}}
local STRIP=24; local W=640; local rows={}
local function capture() for y=2,2+STRIP-1 do local r={}; for x=0,W-1 do local p=scr:pixel(x,y); r[#r+1]=string.char((p>>16)&0xff,(p>>8)&0xff,p&0xff) end; rows[#rows+1]=table.concat(r) end end
local function press(s,m,v) local p=manager.machine.ioport.ports[":"..s]; if not p then return end; for n,f in pairs(p.fields) do if f.mask==m then f:set_value(v); return end end end
local cb,sc=0,nil; local BASE=26; local SLOT=26
emu.register_frame_done(function()
  cb=cb+1
  if manager.machine.time.seconds<15 then return end
  if not scr then for t,s in pairs(manager.machine.screens) do scr=s end end
  if not sc then sc=cb end
  local rel=cb-sc
  if rel<15 then press("SEG08",0x08,1); return    -- enter HELP mode (hold 15f)
  elseif rel==16 then press("SEG08",0x08,0); return end
  local idx=math.floor((rel-BASE)/SLOT)+1
  if idx<1 then return end
  if idx>#BITS then
    local f=io.open(os.getenv("PBOUT"),"wb"); f:write(string.format("P6\n%d %d\n255\n",W,#rows)); f:write(table.concat(rows)); f:close()
    io.stderr:write("DONE rows="..#rows.."\n"); manager.machine:exit(); return end
  local b=BITS[idx]; local fr=(rel-BASE)%SLOT
  if fr==2 then press(b[1],b[2],1)
  elseif fr==16 then press(b[1],b[2],0)
  elseif fr==22 then capture(); io.stderr:write(string.format("row%d = %s.%02X\n",idx,b[1],b[2])) end
end)
