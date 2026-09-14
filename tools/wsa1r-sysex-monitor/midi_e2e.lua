-- midi_e2e.lua -- END-TO-END proof that a SysEx arriving over MIDI reaches the monitor.
--
-- Run with a SysEx-carrying MIDI file on `mdin' (see make_sysex_mid.py):
--   ./kn7000 wsa1r -rompath <patched> -skip_gameinfo -window \
--       -mdin <ident.mid> -mdout "Midi Through Port-0" \
--       -autoboot_script tools/wsa1r-sysex-monitor/midi_e2e.lua -seconds_to_run 9
--
-- It installs READ TAPS on single instruction addresses.  An instruction fetch is a read of the
-- program space, so a tap firing at an address proves the CPU EXECUTED there -- non-invasive, and
-- it needs no debugger.  Four probes, chosen so that each distinguishes a different failure:
--
--   STOCK  0xFBA259  the stock forwarding path      -- fires for ordinary SysEx traffic,
--                                                      so "the hook is reached at all" is visible
--                                                      even if our message never arrives
--   CLAIM  0xFBA266  `.Lclaim'                      -- the marker 0x7D was recognised
--   IDENT  0xFBA271  `.Lours' IDENT path            -- the command byte 0x01 was dispatched
--   SEND   0xF40ED4  the firmware's TX primitive    -- a reply was actually handed to the firmware
--
-- ⚠⚠ RUN LENGTH: MAME's `midiin' deliberately delays a FILE's playback --
--    `m_sequence_start = std::max(machine().time(), attotime(10, 0))', commented "at least 10
--    seconds after starting to allow the keyboards to initialize".  A run shorter than that
--    plays NOTHING, and the first version of this rig reported a clean "no bytes arrived" for
--    exactly that reason.  Give it >= 13 seconds.
--
-- ⚠ RULE 13, applied to microcode: the STOCK probe is the control.  If NOTHING fires, the failure
-- is upstream (the UART, the file, the parser) and says nothing about the monitor.
local mach = manager.machine
local cpu  = mach.devices[":cpu1"]
local prog = cpu.spaces["program"]

local hit = { RXBYTE = 0, SXSTART = 0, STOCK = 0, CLAIM = 0, IDENT = 0, SEND = 0 }
local taps = {}

-- ⚠ A tap range must be BUS-WIDTH ALIGNED.  CPU 1's program space is 16 bits wide, so an odd
-- start address is rejected outright ("start address has low bits set, did you mean ...").
-- Align down and cover the whole word.  Consequence to keep in mind when reading the counts: the
-- tap fires on a fetch of EITHER byte of that word, so a probe can also be tripped by an
-- instruction ending in the low byte.  That is harmless for "did this path run at all", which is
-- the only question asked here.
local function probe(name, addr)
  local lo = addr & ~1
  taps[#taps+1] = prog:install_read_tap(lo, lo + 1, name, function(offset, data, mask)
    hit[name] = hit[name] + 1
    if hit[name] == 1 then
      emu.print_error(string.format("### FIRST HIT  %-6s @0x%06X (word 0x%06X)  t=%.3fs",
          name, addr, lo, mach.time.seconds + mach.time.attoseconds / 1e18))
    end
    return data
  end)
end

-- ⚠ THE UPSTREAM CONTROL, and it must come first.  If no MIDI byte reaches the CPU at all then
-- nothing downstream means anything -- RULE 13 for this rig.  MIDI_RX_Byte (0xFA5496) is the
-- UART receive handler: every incoming byte passes through it.
probe("RXBYTE", 0xFA5496)
probe("SXSTART", 0xFA584D)      -- MIDI_RX_SysExStart: an F0 arrived and was seen
probe("STOCK", 0xFBA259)
probe("CLAIM", 0xFBA266)
probe("IDENT", 0xFBA271)
probe("SEND",  0xF40ED4)

_G._taps = taps                       -- ⚠ hold them: a collected tap silently stops firing

local reported = false
_G._e2e = emu.register_frame_done(function()
  local ok, err = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds / 1e18
    if t >= 13.0 and not reported then
      reported = true
      emu.print_error("### ================ RESULT ================")
      emu.print_error(string.format("### RXBYTE %6d   (UPSTREAM CONTROL: any MIDI byte at all)", hit.RXBYTE))
      emu.print_error(string.format("### SXSTART%6d   (an F0 reached the SysEx parser)", hit.SXSTART))
      emu.print_error(string.format("### STOCK  %6d   (the hook is reached at all)", hit.STOCK))
      emu.print_error(string.format("### CLAIM  %6d   (our marker 0x7D recognised)", hit.CLAIM))
      emu.print_error(string.format("### IDENT  %6d   (command 0x01 dispatched)", hit.IDENT))
      emu.print_error(string.format("### SEND   %6d   (reply handed to the firmware's TX)", hit.SEND))
      emu.print_error(string.format("### (0xA9) = 0x%02X", prog:read_u8(0x00A9)))
      if hit.CLAIM > 0 and hit.IDENT > 0 and hit.SEND > 0 then
        emu.print_error("### ✅ END-TO-END PASS -- SysEx over MIDI reached the monitor and it replied")
      elseif hit.RXBYTE == 0 then
        emu.print_error("### ⛔ NO MIDI BYTE REACHED THE CPU -- the failure is the INPUT PATH")
        emu.print_error("###    (midiin file/port, the bit-serial bridge, or baud) -- NOT the monitor")
      elseif hit.SXSTART == 0 then
        emu.print_error("### ⛔ bytes arrive but no F0 reached the SysEx parser")
      else
        emu.print_error("### ⛔ partial -- see which probe stopped")
      end
    end
  end)
  if not ok then emu.print_error("### LUA ERR " .. tostring(err)) end
end)
emu.print_error("### midi_e2e loaded: 4 execution taps installed")
