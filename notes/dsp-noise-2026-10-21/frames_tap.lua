-- frames_tap.lua -- loaded by passage.lua when NP_EXTRA points at it: how many frames does the SHARC kernel finish
-- each emulated second, and does it write the panel reverb's return every frame?
-- QUESTION IT SERVES (README.md here, "DRC and interpreter"): the interpreter's output with REVERB on is full of
-- held samples and broadband noise, the DRC's is not. Does the interpreter's kernel skip frames?
-- Counts per emulated second, logged as "FRAMES t=<s> iostat=<n> ret0=<n> ret0_changed=<n>" in passage.txt:
--   iostat        writes to IOSTAT (DM 0x2F): rec04 writes it twice a frame (FLAG4 high at the start, low at the end)
--   ret0          writes to DM 0xC342, unit 0's (REVERB's) left return, the word the driver's tick reads every frame
--   ret0_changed  those writes whose value differs from the previous one
-- A kernel that finishes every frame gives iostat 88,200 and ret0 44,100. (If ret0 stays 0 under the DRC, the
-- recompiler reaches internal RAM without the tap: then only iostat counts.)
local M = manager.machine
local dm = M.devices[":dsp"].spaces["data"]
local C = { io = 0, r = 0, rc = 0, last = nil }
_G.FT = C
C.t1 = dm:install_write_tap(0x2F, 0x2F, "ft_iostat", function(o, d, m) C.io = C.io + 1; return d end)
C.t2 = dm:install_write_tap(0xC342, 0xC342, "ft_ret0", function(o, d, m)
  C.r = C.r + 1
  if d ~= C.last then C.rc = C.rc + 1; C.last = d end
  return d
end)
_G.NP_EXTRA_SECOND = function(s, W)
  W("FRAMES t=%d iostat=%d ret0=%d ret0_changed=%d", s, C.io, C.r, C.rc)
  C.io, C.r, C.rc = 0, 0, 0
end
