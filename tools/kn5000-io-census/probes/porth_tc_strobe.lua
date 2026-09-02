-- Witness the FDC Terminal Count strobe on main-CPU Port H bit 0.
-- Held in a GLOBAL: a tap kept in a local is collected and silently stops firing.
ph_hi, ph_lo, ph_tap = 0, 0, nil
local sp = manager.machine.devices[":maincpu"].spaces["program"]
ph_tap = sp:install_write_tap(0x44, 0x47, "phtap", function(off, data, mask)
    if (mask & 0xff) ~= 0 and (data & 1) ~= 0 then ph_hi = ph_hi + 1 else ph_lo = ph_lo + 1 end
    return data
end)
ph_stop = emu.add_machine_stop_notifier(function()
    print(string.format("PH.0 strobe: %d rising, %d falling", ph_hi, ph_lo))
end)
print("phtap armed")

-- Measured 2026-09-03, kn5000 v10 BIOS, no floppy in the drive, 45 s run:
--     PH.0 strobe: 1 rising, 2 falling
-- The two falling edges are boot_hw_init.s:60 (`ldio 0x44, 0x00`) and the
-- clearing half of FDC_Pulse_PH0; the single rising edge is its setting half.
-- So the strobe reaches the FDC once even with no disk inserted -- before
-- porth_write() was bound it reached nothing at all.
--
--     cd ~/compartilhado/kn7000-emulator && ./kn7000 kn5000 -rompath ./roms \
--         -skip_gameinfo -window -nomaximize -seconds_to_run 45 \
--         -autoboot_script ../kn7000_mame/tools/kn5000-io-census/probes/porth_tc_strobe.lua
