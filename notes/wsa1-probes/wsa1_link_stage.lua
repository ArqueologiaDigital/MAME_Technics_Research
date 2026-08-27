-- ⚠ SUPERSEDED 2026-08-27, AND ALL THREE OF ITS COUNTERS WERE WRONG.  Kept only
-- because its numbers are quoted in older notes; use wsa1_udma3_audit.lua.
--
-- Every tap below covers more than the thing it names:
--   * 0xF8E54E-0xF8E54F is called "INTTC3" but 0xF8E54E is INTTC2_uDMA2Done's
--     `reti`, and tlcs900_device::RDOP() prefetches m_pc+3 (tlcs900.cpp:81-99),
--     so INTTC2's last four bytes read BOTH addresses.  Its "12" was 6 INTTC2
--     returns x 2 reads.  The exact count -- reads of the selector word
--     0x6007DA, whose only reader in any of the three images is 0xF8E555 -- is
--     ZERO: INTTC3_LinkDmaDone never ran at all.
--   * 0xF8E47E-0xF8E47F is called "INT0" but 0xF8E47E is the previous routine's
--     `ret`.
--   * 0x7E-0x7F is called "DMA3V" but 0x7E is DMA2V, which the transmit block
--     arms from nine sites (wsa1_udma3_xref.py lists them).  Its "11" was
--     DMA2V + DMA3V.
-- The measured, unaliased picture is in README.md under wsa1_udma3_audit.lua.
--
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
