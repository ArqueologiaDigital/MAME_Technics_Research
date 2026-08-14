-- Does pressing a key-bed note make the FIRMWARE emit tone-generator voice
-- writes? Raw-bus write-tap on both TGs (unaffected by the driver's capture gate).
local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local tg_addr = {0,0}
local voice = 0
local idle  = 0
local watching = false
local seen = {}
local function tap(base, idx, label)
  prog:install_write_tap(base, base+3, "tg"..idx, function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then tg_addr[idx] = data & 0xffff end
    if (mask & 0xffff0000) ~= 0 then
      local a = tg_addr[idx]; local d = (data>>16) & 0xffff
      if (a & 0xff00) == 0xfc00 then idle = idle + 1
      elseif watching then
        voice = voice + 1
        if voice <= 60 then
          print(("[TGW] %s reg=%04X data=%04X pc=%08X"):format(label,a,d,cpu.state["CURPC"].value))
        end
        local cls = a & 0xfc00
        seen[cls] = (seen[cls] or 0) + 1
      end
    end
    return nil
  end)
end
tap(0x98040000, 1, "MAIN")
tap(0x98050000, 2, "SUB")

local function setkey(name, v)
  for _,f in pairs(mac.ioport.ports[":KEYS0"].fields) do
    if f.name == name then f:set_value(v); return true end end
  return false
end

local fr = 0
emu.add_machine_frame_notifier(function()
  fr = fr + 1
  if fr == 60*16 then watching = true; print("t=16 watching TG; press C4"); setkey("Key C4", 1)
  elseif fr == 60*18 then setkey("Key C4", 0); print("release C4")
  elseif fr == 60*19 then setkey("Key E4", 1)      -- try a couple more notes
  elseif fr == 60*21 then setkey("Key E4", 0)
  elseif fr == 60*22 then setkey("Key G4", 1)
  elseif fr == 60*24 then setkey("Key G4", 0)
  elseif fr == 60*26 then
    watching = false
    print(("RESULT: %d non-FC voice writes, %d idle(0xFC0x)"):format(voice, idle))
    local ks = {}; for k in pairs(seen) do ks[#ks+1]=k end; table.sort(ks)
    for _,k in ipairs(ks) do print(("  class %04X: %d writes"):format(k, seen[k])) end
    print(voice>0 and ">>> FIRMWARE DRIVES THE TG on keybed press" or ">>> no firmware voice writes (dormant / wrong path)")
  end
end)
print("keybed_trigger.lua armed")
