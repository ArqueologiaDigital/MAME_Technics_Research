# KN7000 panel — input-sweep tooling & method (2026-07-07)

Reusable techniques for mapping the remaining panel buttons to their input bits. Built while
resolving the user's "no visual feedback" list.

## Screen-change detector (works with `-video none`)
The LCD is MAME screen `:screen` (640x240). `scr:pixel(x,y)` returns an RGB int and works even
without a video window, so it's ENFILE/hang-proof. Hash a sparse grid to detect screen changes:
```lua
local scr  -- for t,s in pairs(manager.machine.screens) do scr=s end
local function shash()
  local h=2166136261
  for y=20,235,55 do for x=40,620,80 do
    local ok,p=pcall(function() return scr:pixel(x,y) end)
    if ok then h=((h ~ (p&0xffffff))*16777619)&0xffffffff end
  end end
  return h
end
```
home hash ≠ any menu's hash, so `shash()~=home` == "this bit opened something".

## Screen capture without the (hanging) video path
`manager.machine.video:snapshot()` HANGS in this environment (stale procs + starved virtiofs
cache). Instead dump the framebuffer to a PPM via `scr:pixel`, then `convert` to PNG:
```lua
local f=io.open(out,"wb"); f:write("P6\n640 240\n255\n"); local t={}
for y=0,239 do for x=0,639 do local p=scr:pixel(x,y)
  t[#t+1]=string.char((p>>16)&0xff,(p>>8)&0xff,p&0xff) end end
f:write(table.concat(t)); f:close()
```
scratchpad/sdump.lua does this (press PBSEG/PBMASK at frame 5, dump PBOUT at frame 70). Reliable.
Always `pkill -9 -f 'kn7000 kn7000'; drop-caches` before a run.

## CAVEAT: single-boot sweeps are contaminated (no reset-to-home)
A one-boot sweep pressing bits in sequence is UNRELIABLE past the first bit: once a bit opens a
screen, later bits are pressed from *that* screen (the panel is a screen stack), and modal screens
(DEMONSTRATION, HELP, APC SELECT) trap input. So only the very first press is a clean "from-home"
result. There is no known EXIT/home bit yet to reset between presses.
=> To find a button cleanly, do ONE FRESH BOOT per bit (scratchpad/mp1.lua or sdump.lua). ~75 s per
boot, so sweep the ~99 unmapped bits a chunk at a time across ticks. hsweep.lua's list of bits that
changed *any* screen is a candidate set, but each must be re-checked from a fresh boot (many are
no-ops from home — e.g. SEG10 0x02 flagged in the sweep but is a no-op from home).

## Findings so far
- **APC MODE = SEG03 0x02** — opens the "APC SELECT" screen (BASIC/FINGERED/PIANIST, MEMORY/ON
  BASS/LEFT HOLD, COUNT INTRO, CHORD FINDER). Was decorative; now bound. (fresh-boot dump)
- SEG03 0x04, SEG10 0x02 = no-op from home (checked, not buttons that open screens).

## Still to find (user "no visual feedback"; open screens => findable by fresh-boot dump)
APC SET + lower OFF/ON; PART EFFECT + GLOBAL EFFECT; BANK VIEW / NEXT BANK / PANEL MEMORY;
CUSTOM PANEL / CUSTOMIZE / FAVORITES; SEQUENCER PLAY / EASY REC; SD LOAD; DISPLAY HOLD; EXIT;
PAGE UP/DOWN. **EXIT = SEG20 0x01 (FOUND — see panel-dispatch-table.md)** — now enables clean single-boot sweeps: press EXIT between candidates to reset to home.
Likely in SEG04-SEG07 / SEG0F (masked in the sweep by the SEG03 0x04 contamination).
