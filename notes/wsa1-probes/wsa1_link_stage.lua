-- Where does CPU 1's receive chain stop?
--   INT0_LinkByte 0xF8E47F -> arms uDMA ch3, drops busy
--   INTTC3_LinkDmaDone 0xF8E54F -> should raise busy again
local m = manager.machine
local sp1 = m.devices[":cpu1"].spaces["program"]
local n_int0, n_inttc3, n_dma3v = 0, 0, 0
local t = {}
t[#t+1] = sp1:install_read_tap(0xf8e47e, 0xf8e47f, "int0", function(o,d,k) n_int0=n_int0+1 return d end)
t[#t+1] = sp1:install_read_tap(0xf8e54e, 0xf8e54f, "tc3",  function(o,d,k) n_inttc3=n_inttc3+1 return d end)
-- DMA3V is internal I/O 0x7f; IIMC is 0x7c on this part's map
t[#t+1] = sp1:install_write_tap(0x00007e, 0x00007f, "dma3v", function(o,d,k) n_dma3v=n_dma3v+1 return d end)
_G.wsa1_stage_taps = t
local done=false
_G.wsa1_stage_rep = emu.add_machine_frame_notifier(function()
  if done or m.time.seconds < 90 then return end
  done=true
  emu.print_error(string.format("STAGE int0_handler=%d  dma3v_writes=%d  inttc3_handler=%d",
      n_int0, n_dma3v, n_inttc3))
end)
