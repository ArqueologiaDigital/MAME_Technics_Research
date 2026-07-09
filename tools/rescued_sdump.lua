local seg=os.getenv("PBSEG"); local mask=tonumber(os.getenv("PBMASK")); local out=os.getenv("PBOUT")
local function press(s,m,v) local p=manager.machine.ioport.ports[":"..s]; for n,f in pairs(p.fields) do if f.mask==m then f:set_value(v); return end end end
local scr
local function dump(fn)
  local f=io.open(fn,"wb"); f:write("P6\n640 240\n255\n")
  local t={}
  for y=0,239 do for x=0,639 do local p=scr:pixel(x,y); t[#t+1]=string.char((p>>16)&0xff,(p>>8)&0xff,p&0xff) end end
  f:write(table.concat(t)); f:close()
end
local cb,sc=0,nil
emu.register_frame_done(function()
  cb=cb+1
  if manager.machine.time.seconds<15 then return end
  if not scr then for tt,s in pairs(manager.machine.screens) do scr=s end end
  if not sc then sc=cb end
  local rel=cb-sc
  if rel==5 then press(seg,mask,1)
  elseif rel==70 then dump(out); io.stderr:write("DUMPED\n"); manager.machine:exit() end
end)
