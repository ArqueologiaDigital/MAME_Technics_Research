-- QUESTION: is CPU1's 8-bit Timer 1 (vector 0xFFFF44 = INTT1, the 488 Hz tick
-- that writes RAM 0x80) programmed identically in the two builds?
-- Logs every write to CPU1's SFR page 0x00-0x7F in order, with the writing PC.
local m = manager.machine
local cpu = m.devices[":cpu1"]
local sp = cpu.spaces["program"]
local STOP = tonumber(os.getenv("STOP_AT") or "3")
local names = {[0x20]="TRUN",[0x22]="TREG0",[0x23]="TREG1",[0x24]="T01MOD",[0x25]="TFFCR",
  [0x26]="TREG2",[0x27]="TREG3",[0x28]="T23MOD",[0x29]="TRDC",[0x13]="P7",[0x1e]="PA",[0x1f]="PB",
  [0x2c]="PACR",[0x2d]="PAFC",[0x2e]="PBCR",[0x2f]="PBFC",[0x70]="INTE0AD",[0x71]="INTE45",
  [0x72]="INTE67",[0x73]="INTET10",[0x74]="INTET32",[0x75]="INTET54",[0x76]="INTET76",
  [0x77]="INTES0",[0x78]="INTES1",[0x79]="INTETC10",[0x7a]="INTETC32",[0x7b]="IIMC",
  [0x7c]="DMA0V",[0x7d]="DMA1V",[0x7e]="DMA2V",[0x7f]="DMA3V"}
local seen = {}
_G.wsa1_sfr_tap = sp:install_write_tap(0x00, 0x2f, "sfr", function (offset, data, mask)
  local k = string.format("%02X=%02X@%06X", offset, data & 0xff, cpu.state["CURPC"].value)
  if seen[k] then return end
  seen[k] = true
  emu.print_error(string.format("SFR %02X (%-7s) <- %02X   pc=%06X  t=%.3f",
    offset, names[offset] or "?", data & 0xff, cpu.state["CURPC"].value, m.time:as_double()))
end)
_G.wsa1_sfr = emu.add_machine_frame_notifier(function ()
  if m.time:as_double() >= STOP then m:exit() end
end)
