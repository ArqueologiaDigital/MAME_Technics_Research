local cpu = manager.machine.devices[":maincpu"]
local mem = cpu.spaces["program"]
local done=false
emu.register_frame_done(function()
  if manager.machine.time.seconds >= 14 and not done then
    done=true
    local out=io.open("kn6_g.log","w")
    for a=0x5024F400,0x5024F7FF,16 do
      local b,t={},{}
      for i=0,15 do local v=mem:read_u8(a+i); b[#b+1]=string.format("%02x",v); t[#t+1]=(v>=32 and v<127) and string.char(v) or "." end
      out:write(string.format("%08X: %s |%s|\n",a,table.concat(b," "),table.concat(t)))
    end
    out:close(); print("G done"); manager.machine:exit()
  end
end)
