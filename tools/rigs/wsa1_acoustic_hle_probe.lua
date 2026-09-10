-- wsa1_acoustic_hle_probe.lua : validate the L7A1429 RESEARCH HLE audio path.
--
-- Requires a build with CPPFLAGS=-DWSA1R_ENABLE_ACOUSTIC_HLE=1 (the device becomes a
-- device_sound_interface routed to the speakers).  After boot, it pokes the L7A1429's MAIN
-- TUNE register for a few channels over CPU 2's bus -- each such write is the device's note
-- event, exciting that channel's resonator -- then holds so the ring can be captured.
--
-- Validate:  run with -wavwrite OUT.wav -seconds_to_run N, then check the WAV
--   * has energy (RMS > 0), i.e. the model produced audio;
--   * rings near the note fundamental (A4 = 440 Hz for note 69);
--   * DECAYS (no key-off): later RMS < earlier RMS.
--
-- Env: NOTE (MIDI, default 69 = A4), AT (excite time s, default 20), CH (channel, default 0).
local NOTE = tonumber(os.getenv("NOTE") or "69")
local AT   = tonumber(os.getenv("AT") or "20")
local CH   = tonumber(os.getenv("CH") or "0")
local mach = manager.machine
local sp   = mach.devices[":cpu2"].spaces["program"]

-- (select, data) pair over IC3's port: +0 latches the register number, +2 the value.
local function wr(reg, val)
  sp:write_u16(0x104000, reg & 0xffff)
  sp:write_u16(0x104002, val & 0xffff)
end

local done = false
_G._ah = emu.register_frame_done(function()
  local t = mach.time.seconds + mach.time.attoseconds/1e18
  if not done and t >= AT then
    done = true
    -- re-excite ALL 64 channels at NOTE so the written pitch dominates the boot ring
    -- (the firmware's reset also excited every channel at the reset-image tune) -- this is
    -- the clean pitch check: the whole bank should now ring at NOTE's fundamental.
    for c = 0, 63 do
      wr(0x0040 + c, math.floor(NOTE * 256))
    end
    emu.print_info(string.format("### excited ALL 64 L7A1429 voices at note %d at t=%.1f", NOTE, t))
  end
end)
emu.print_info(string.format("### acoustic HLE probe loaded (NOTE=%d AT=%.1f CH=%d)", NOTE, AT, CH))
