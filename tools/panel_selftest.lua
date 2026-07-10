-- KN7000 Panel SW & LED self-test enabler (service manual 8.5).
-- The diagnostic Panel SW & LED test is gated by RAM flag 0x5006BFB2: when the panel dispatcher
-- (PanelButtonDispatch 0x484ADB59) reads it as 1, every panel-button press routes to the InOut
-- test handler 0x484A0CB0, which lights that switch's indicator LED (from PanelSwitchClassTable
-- 0x4860C9F4) instead of running the button's normal function. LEDs light ~1 s after the press and
-- ACCUMULATE (pressing every button lights every LED = the real test). We hold the flag = 1 every
-- frame. (We can't draw the test SCREEN: the boot key-combo is read by the panel/key sub-CPU, not
-- modeled at power-on -- but this reproduces the button->LED behaviour, which is the useful part.)
-- Usage: ./run.sh -window -autoboot_script tools/panel_selftest.lua ; then press panel buttons and
-- watch each one's LED light. To reset, un-press and re-launch.
_G.kn_pt = _G.kn_pt or {}
local prg = manager.machine.devices[":maincpu"].spaces["program"]
_G.kn_pt.notifier = emu.add_machine_frame_notifier(function()
  prg:write_u8(0x5006BFB2, 0x01)   -- hold the panel-test flag on
end)
