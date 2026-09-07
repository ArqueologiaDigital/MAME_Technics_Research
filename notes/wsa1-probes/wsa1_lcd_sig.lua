-- Compute a lua-readable SIGNATURE of the WSA1R SED1330 display RAM, to tell
-- screens apart. The panel draws glyphs as GRAPHICS (font plotter 0xF8EDAC),
-- so there is no ASCII text region: the signature is a byte checksum of the
-- graphics layers. Geometry (firmware's own, LCD_Init_SED1330 0xF8E819):
--   SYSTEM SET 30 07 00 27 35 EF 28 00 -> 8 px/byte, AP=40, 240 lines
--   SCROLL     -> SAD1=0x0000 (glyph layer), SAD2=0x2600 (highlight), SAD3=0x4C00
local AP   = 40
local ROWS = 240
local L0, L1, L2 = 0x0000, 0x2600, 0x4C00
local m  = manager.machine
local vr = m.devices[":lcdc"].spaces["videoram"]

local function fnv(base, n)      -- FNV-1a over n bytes from base; also nonzero count
  local h, nz = 2166136261, 0
  for a = base, base + n - 1 do
    local b = vr:read_u8(a)
    if b ~= 0 then nz = nz + 1 end
    h = (h ~ b) & 0xffffffff
    h = (h * 16777619) & 0xffffffff
  end
  return h, nz
end

local function report(tag)
  local span = ROWS * AP                     -- 9600 bytes per layer
  local h0,n0 = fnv(L0, span)
  local h1,n1 = fnv(L1, span)
  local h2,n2 = fnv(L2, span)
  local hall,_ = fnv(0x0000, 0x7180)         -- SAD3 + 240*AP, the highest addr any layer reaches
  print(string.format(
    "SIG %s t=%.2f  L0=%08X/%d  L1=%08X/%d  L2=%08X/%d  ALL=%08X",
    tag, m.time:as_double(), h0,n0, h1,n1, h2,n2, hall))
end

_G.shots = {[10]=false,[20]=false,[30]=false,[45]=false,[60]=false}
_G.sig_sub = emu.add_machine_frame_notifier(function ()
  local t = m.time:as_double()
  for k,done in pairs(_G.shots) do
    if not done and t >= k then _G.shots[k]=true; report(tostring(k).."s") end
  end
end)
print("WSA1R LCD signature probe armed (videoram space, layers 0x0000/0x2600/0x4C00)")
