-- Turn ON the "Effects DSP host stub" machine-config switch, then framebuffer-hash
-- at t>=16s (emu.add_machine_frame_notifier API).
--
-- NOTE: setting a CONFIG field via Lua set_value() is TIMING-SENSITIVE -- it may
-- land after the firmware's DSP boot probe, leaving the DSP still gated for that
-- run. The DETERMINISTIC way to enable the stub is the config file (switch ON
-- from machine init): put in cfg/kn7000.cfg
--   <port tag=":CONFIG" type="CONFIG" mask="1" defvalue="0" value="1" />
-- or toggle it in MAME's Tab -> "Machine Configuration" menu. (MAME also
-- persists this switch to cfg/ on exit, so clear it there between OFF/ON tests.)
local mac = manager.machine
for _,f in pairs(mac.ioport.ports[":CONFIG"].fields) do
  if f.mask == 0x01 then f:set_value(1); print("CONFIG bit0 set -> DSP stub ON") end
end
local sp = mac.devices[":maincpu"].spaces["program"]
local fired = false
_onsub = emu.add_machine_frame_notifier(function()
  if fired or mac.time.seconds < 16 then return end
  fired = true
  local h, nz = 0, 0
  for a = 0x9ce00000, 0x9ce00000 + 640*240*2 - 1, 64 do
    local v = sp:read_u32(a); h=(h*131+v)&0xffffffff; if v~=0 then nz=nz+1 end
  end
  print(string.format("ON_FBHASH %08x nonzero=%d t=%d", h, nz, mac.time.seconds))
end)
