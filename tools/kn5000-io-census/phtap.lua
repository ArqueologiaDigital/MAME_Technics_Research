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
