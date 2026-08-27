-- Hold one key of every distinct SHAPE down, so a snapshot shows the pressed
-- wash for each of them at once.  Answers: does replacing the duplicated
-- pressed SVG with a <rect>/<disk> component still darken the key?
local held = {
  { ":cpanel:CP_SEG0", "Panel SEG0 SW0" },   -- mode_button
  { ":cpanel:CP_SEG0", "Panel SEG0 SW4" },   -- bank_button
  { ":cpanel:CP_SEG1", "Panel SEG1 SW0" },   -- numeric_button
  { ":cpanel:CP_SEG1", "Panel SEG1 SW2" },   -- numeric_button_large
  { ":cpanel:CP_SEG2", "Panel SEG2 SW4" },   -- under_lcd_button_bottom (PAGE down)
  { ":cpanel:CP_SEG2", "Panel SEG2 SW5" },   -- under_lcd_button_top   (PAGE up)
  { ":cpanel:CP_SEG3", "Panel SEG3 SW0" },   -- lcd_soft_key
  { ":cpanel:CP_SEG3", "Panel SEG3 SW5" },   -- wide_button
  { ":cpanel:CP_SEG8", "Panel SEG8 SW0" },   -- realtime_creator_button
  { ":cpanel:CP_SEG8", "Panel SEG8 SW1" },   -- realtime_creator_reset_button
}
local picked = {}
emu.add_machine_reset_notifier(function() picked = {} end)
local function resolve()
  for _, want in ipairs(held) do
    local port = manager.machine.ioport.ports[want[1]]
    if port then
      for name, field in pairs(port.fields) do
        if name:sub(1, #want[2]) == want[2] then picked[#picked+1] = field end
      end
    end
  end
  print(string.format("hold_buttons: resolved %d of %d fields", #picked, #held))
end
local n = 0
emu.register_frame_done(function()
  n = n + 1
  if n == 120 then resolve() end
  if n >= 120 then for _, f in ipairs(picked) do f:set_value(1) end end
end)
