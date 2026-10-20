-- host_iop_selftest.lua -- does the emulated effects-DSP host port answer as the DSP probes expect?
-- At t = $SELFTEST_AT (default 40 s, the kernel long since running) it drives the KN7000's host port from the
-- main CPU's bus exactly as the firmware's accessors do (index to 0x98000000, 16-bit halves through 0x9C000000,
-- low half first) and prints PROBE lines:
--   iop   IOP registers the kernel programs (SPORT DMA chain pointers 0x73/0x53/0x7B/0x5B/0x63/0x33/0x6B/0x3B,
--         the SPORT control registers) read through the host port, next to the SHARC's own register file;
--         they must agree, and the chain pointers must be non-zero
--   syscon SYSCON (0x00) through the host port: 0x410, what the firmware programs at 0x48407A56 (HBW 01, a 16-bit
--         host bus, LSW first), which the phase-2 probe requires before it writes anything
--   rb    phase-2 readbacks: IIEP0 (0x40), IMEP0 (0x41) = 1, CEP0 (0x42) = 4, then DMAC0 (0x1C) = 0xA5 (DEN | TRAN
--         | DTYPE 48-bit, the bits the TRM defines) and 12 reads of EPB0 (index 0x04), which must equal the four
--         48-bit program words at PM 0x8004-0x8007 (the kernel's IDLE and JUMP init) read straight from the
--         SHARC's program space; before each PM word DMAC0's FS bits (14-15) must read 11, EPB0 full, and after the
--         last 00, empty (the probe polls them before every EPB0 read); the same with DMAC0 = 0x45 (32-bit) for DM
--         0x9800-0x9803 (8 reads); then DMAC0 = 0xA0 (the firmware's own idle value)
-- and exits. It changes DSP state the way a probe would: run it on a throwaway session.
local mac = manager.machine
local sp = mac.devices[":maincpu"].spaces["program"]
local dsp = mac.devices[":dsp"]
local AT = tonumber(os.getenv("SELFTEST_AT") or "40")
local function idx(i) sp:write_u16(0x98000000, i) end
local function rd32(i) idx(i); local lo = sp:read_u16(0x9c000000); local hi = sp:read_u16(0x9c000000); return (hi << 16) | lo end
local function wr32(i, v) idx(i); sp:write_u16(0x9c000000, v & 0xffff); sp:write_u16(0x9c000000, (v >> 16) & 0xffff) end
local done = false
_G.ST = emu.add_machine_frame_notifier(function()
  if done or mac.time:as_double() < AT then return end
  done = true
  local bad = 0
  for _, r in ipairs({0x73, 0x53, 0x7b, 0x5b, 0x63, 0x33, 0x6b, 0x3b}) do
    local v = rd32(r)
    emu.print_error(string.format("PROBE iop %02x = %08x%s", r, v, v == 0 and "  (zero!)" or ""))
    if v == 0 then bad = bad + 1 end
  end
  local sc = rd32(0x00)
  emu.print_error(string.format("PROBE syscon = %08x %s", sc, sc == 0x410 and "ok" or "UNEXPECTED (want 00000410)"))
  if sc ~= 0x410 then bad = bad + 1 end
  wr32(0x40, 0x8004); wr32(0x41, 1); wr32(0x42, 4); wr32(0x1c, 0xa5)
  local pm = dsp.spaces["program"]
  local pnz = 0
  for k = 0, 3 do
    local fs = rd32(0x1c) & 0xc000
    if fs ~= 0xc000 then bad = bad + 1; emu.print_error(string.format("PROBE rb PM %04x: FS %x before the word, want c000", 0x8004 + k, fs)) end
    idx(0x04)
    local a = sp:read_u16(0x9c000000); local b = sp:read_u16(0x9c000000); local c = sp:read_u16(0x9c000000)
    local got = (c << 32) | (b << 16) | a
    local want = pm:read_u64(0x8004 + k) & 0xffffffffffff
    if want ~= 0 then pnz = pnz + 1 end
    emu.print_error(string.format("PROBE rb PM %04x host %012x direct %012x %s", 0x8004 + k, got, want, got == want and "ok" or "MISMATCH"))
    if got ~= want then bad = bad + 1 end
  end
  if pnz == 0 then bad = bad + 1; emu.print_error("PROBE rb PM: all four words zero, the PM comparison proves nothing") end
  local fs_end = rd32(0x1c) & 0xc000
  emu.print_error(string.format("PROBE rb FS before each PM word c000, after the last %x %s", fs_end, fs_end == 0 and "ok" or "MISMATCH"))
  if fs_end ~= 0 then bad = bad + 1 end
  wr32(0x40, 0x9800); wr32(0x41, 1); wr32(0x42, 4); wr32(0x1c, 0x45)
  idx(0x04)
  local dm = dsp.spaces["data"]
  local nz = 0
  for k = 0, 3 do
    local a = sp:read_u16(0x9c000000); local b = sp:read_u16(0x9c000000)
    local got = (b << 16) | a
    local want = dm:read_u32(0x9800 + k)
    if want ~= 0 then nz = nz + 1 end
    emu.print_error(string.format("PROBE rb DM %04x host %08x direct %08x %s", 0x9800 + k, got, want, got == want and "ok" or "MISMATCH"))
    if got ~= want then bad = bad + 1 end
  end
  if nz == 0 then bad = bad + 1; emu.print_error("PROBE rb DM: all four words zero, the DM comparison proves nothing") end
  wr32(0x1c, 0xa0)
  emu.print_error(string.format("PROBE selftest %s (%d problems)", bad == 0 and "PASS" or "FAIL", bad))
  mac:exit()
end)
