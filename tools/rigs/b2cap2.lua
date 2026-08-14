-- b2cap2.lua -- cold CHORUS/MULTI toggle: capture EVERYTHING (all sub+main TG writes,
-- DSP index/data port writes) to see every hardware-visible effect of the toggle.
local function press(p, mm, v)
  local pp = manager.machine.ioport.ports[p]
  for _, f in pairs(pp.fields) do if f.mask == mm then f:set_value(v) end end
end
local st, installed = 0, false
local latch = { [0]=0, [1]=0 }
local dspidx = 0
_G._k = _G._k or {}
local function now() local mt = manager.machine.time; return mt.seconds + mt.attoseconds/1e18 end
local active = false
_G._b2 = emu.add_machine_frame_notifier(function()
  local m = manager.machine
  local t = now()
  if not installed and t > 16.0 then
    installed = true
    local prog = m.devices[":maincpu"].spaces["program"]
    local function tgtap(base, tgi, name)
      return prog:install_write_tap(base, base + 3, name, function(off, data, mask)
        if not active then return end
        if (mask & 0x0000FFFF) ~= 0 then latch[tgi] = data & 0xFFFF end
        if (mask & 0xFFFF0000) ~= 0 then
          emu.print_error(string.format("[b2c] t=%8.3f TG%d addr=%04X data=%04X", now(), tgi, latch[tgi], (data>>16)&0xFFFF))
        end
      end)
    end
    _G._k[1] = tgtap(0x98040000, 0, "c2tg0")
    _G._k[2] = tgtap(0x98050000, 1, "c2tg1")
    _G._k[3] = prog:install_write_tap(0x98000000, 0x98000003, "c2di", function(off, data, mask)
      if not active then return end
      emu.print_error(string.format("[b2c] t=%8.3f DSPIDX data=%08X mask=%08X", now(), data, mask))
    end)
    _G._k[4] = prog:install_write_tap(0x9c000000, 0x9c000003, "c2dd", function(off, data, mask)
      if not active then return end
      emu.print_error(string.format("[b2c] t=%8.3f DSPDAT data=%08X mask=%08X", now(), data, mask))
    end)
    emu.print_error("[b2c] taps installed")
  end
  local seq = {
    {19.5, function() active = true end},
    {20.0, function() press(":cpanel:CPR_SEG5", 0x04, 1); emu.print_error("[b2c] === COLD CHORUS DOWN ===") end},
    {20.4, function() press(":cpanel:CPR_SEG5", 0x04, 0) end},
    {21.5, function() emu.print_error("[b2c] === COLD MULTI DOWN ===");  press(":cpanel:CPR_SEG4", 0x04, 1) end},
    {21.9, function() press(":cpanel:CPR_SEG4", 0x04, 0) end},
    {23.0, function() active = false; emu.print_error("[b2c] === capture off ===") end},
  }
  local step = seq[st + 1]
  if step and t > step[1] then st = st + 1; step[2]() end
end)
