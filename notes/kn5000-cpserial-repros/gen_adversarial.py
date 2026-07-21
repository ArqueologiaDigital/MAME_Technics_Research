#!/usr/bin/env python3
"""Adversarial press-schedule generator for the KN5000 CP-serial option-A skeptic pass.

Same lua skeleton as notes/kn5000-cpserial-repros/*.lua (deterministic, emulated-time driven),
same 4-press liveness tail so results are directly comparable.
"""
import os, sys

HEAD = r"""
local mac = manager.machine
local function log(s) emu.print_error(s) end
local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end
local function press(t, tag, mask, desc, hold)
  hold = hold or 0.25
  at(t, desc, function()
    local p = mac.ioport.ports[tag]
    if not p then log("NO PORT "..tag) return end
    for _, f in pairs(p.fields) do if f.mask == mask then f:set_value(1) end end
  end)
  at(t + hold, "", function()
    local p = mac.ioport.ports[tag]
    if not p then return end
    for _, f in pairs(p.fields) do if f.mask == mask then f:clear_value() end end
  end)
end
local shots = 0
local function snap(t, label)
  at(t, "", function()
    mac.video:snapshot(); shots = shots + 1
    log(("SNAP#%04d %s t=%.3f"):format(shots-1, label, mac.time.seconds + mac.time.attoseconds/1e18))
  end)
end
"""

TAIL = r"""
-- The repro luas in notes/kn5000-cpserial-repros/ rely on their actions being emitted in
-- strictly increasing time order.  Some schedules here press several buttons AT THE SAME
-- INSTANT, which interleaves press/release pairs, so sort explicitly.  (Without this the
-- second and later buttons of a simultaneous group get pressed and released in the same
-- dispatch, i.e. invisibly to the panel's 2-scan / 14 ms confirmation filter.)
table.sort(acts, function(a, b) return a.t < b.t end)
local i = 1
emu.register_periodic(function()
  local nw = mac.time.seconds + mac.time.attoseconds/1e18
  while i <= #acts and nw >= acts[i].t do
    local a = acts[i]; i = i + 1
    local ok, err = pcall(a.fn)
    if not ok then log(("ERR t=%.3f %s: %s"):format(nw, tostring(a.desc), tostring(err)))
    elseif a.desc ~= "" then log(("[%8.3f] %s"):format(nw, a.desc)) end
  end
end)
log("harness armed")
"""


def press(t, tag, mask, desc, hold=0.25):
    return 'press(%.3f, ":cpanel:%s", 0x%02X, "%s", %.3f)\n' % (t, tag, mask, desc, hold)


def snap(t, label):
    return 'snap(%.3f, "%s")\n' % (t, label)


def liveness(t0):
    """The exact liveness tail used by a1/b1/b3: pre, pre2, DISK, SOUND, PIANO, ORCHPAD."""
    s = ""
    s += snap(t0, "pre")
    s += snap(t0 + 1.0, "pre2")
    s += press(t0 + 2.0, "CPR_SEG10", 0x20, "LIVE MENU:DISK")
    s += snap(t0 + 4.0, "disk")
    s += press(t0 + 5.0, "CPR_SEG10", 0x04, "LIVE MENU:SOUND")
    s += snap(t0 + 7.0, "sound")
    s += press(t0 + 8.0, "CPR_SEG2", 0x01, "LIVE PIANO")
    s += snap(t0 + 10.0, "piano")
    s += press(t0 + 11.0, "CPR_SEG1", 0x02, "LIVE ORCHPAD")
    s += snap(t0 + 13.0, "orch")
    s += 'at(%.3f, "done", function() log("RUN DONE"); mac:exit() end)\n' % (t0 + 14.0)
    return s


SOUND = [("CPR_SEG2", 0x01, "PIANO"), ("CPR_SEG2", 0x02, "GUITAR"),
         ("CPR_SEG2", 0x04, "STRINGS"), ("CPR_SEG2", 0x08, "BRASS"),
         ("CPR_SEG2", 0x10, "FLUTE"), ("CPR_SEG2", 0x20, "SAX"),
         ("CPR_SEG1", 0x01, "ORGAN"), ("CPR_SEG1", 0x02, "ORCHPAD"),
         ("CPR_SEG1", 0x04, "SYNTH"), ("CPR_SEG1", 0x08, "BASS"),
         ("CPR_SEG1", 0x80, "DRUMKITS")]


def write(name, body):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lua", name + ".lua")
    open(p, "w").write(HEAD + body + TAIL)
    print(p)


# ---------------------------------------------------------------- x_rhythm
# Rhythm running => the beat/FILL LEDs flash continuously => the main CPU is
# transmitting panel COMMANDS most of the time, i.e. IOC=0 / receiver CLOSED.
# Option A makes the panel wait for the receiver, so this is the natural
# starvation test.  Presses go in while the accompaniment runs.
b = ""
b += press(24.0, "CPR_SEG8", 0x20, "START/STOP (rhythm on)", 0.25)
t = 26.0
for k in range(40):
    tag, mask, nm = SOUND[k % len(SOUND)]
    b += press(t, tag, mask, "R%d %s" % (k, nm), 0.10)
    t += 0.5
b += press(t + 0.5, "CPL_SEG2", 0x01, "FILL IN 1", 0.25)
b += press(t + 1.5, "CPL_SEG4", 0x02, "VARIATION 2", 0.25)
b += press(t + 2.5, "CPR_SEG8", 0x20, "START/STOP (rhythm off)", 0.25)
write("x_rhythm", b + liveness(t + 5.0))

# ---------------------------------------------------------------- x_rhythm2
# Same, but the presses keep coming for much longer and the rhythm is never
# stopped: if the CPU's command traffic starves the panel's idle window, this
# is where the queue grows and the abandon/retry loop should show up.
b = ""
b += press(24.0, "CPR_SEG8", 0x20, "START/STOP (rhythm on)", 0.25)
t = 26.0
for k in range(120):
    tag, mask, nm = SOUND[k % len(SOUND)]
    b += press(t, tag, mask, "R%d %s" % (k, nm), 0.08)
    t += 0.25
write("x_rhythm2", b + liveness(t + 2.0))

# ---------------------------------------------------------------- x_multi
# MANY SEGMENTS CHANGING IN THE SAME 7 ms SCAN.  Each changed segment is its own
# 2-byte packet, so this is the direct attack on queue depth / burst delivery /
# packet ordering.  8 buttons in 8 different segments, pressed and released
# together, 30 times.
b = ""
MULTI = [("CPR_SEG1", 0x02), ("CPR_SEG2", 0x01), ("CPR_SEG3", 0x01), ("CPR_SEG4", 0x08),
         ("CPR_SEG6", 0x01), ("CPR_SEG8", 0x80), ("CPL_SEG0", 0x01), ("CPL_SEG6", 0x01)]
t = 30.0
for k in range(30):
    for (tag, mask) in MULTI:
        b += press(t, tag, mask, "M%d %s/%02X" % (k, tag, mask), 0.12)
    t += 0.6
write("x_multi", b + liveness(t + 2.0))

# ---------------------------------------------------------------- x_flood
# 200 presses at 20 Hz.  Faster than the 143 Hz scan can confirm (2 stable
# scans = 14 ms) but slow enough that each is seen; the point is sustained
# back-pressure on the delivery path.
b = ""
t = 30.0
for k in range(200):
    tag, mask, nm = SOUND[k % len(SOUND)]
    b += press(t, tag, mask, "F%d %s" % (k, nm), 0.03)
    t += 0.05
write("x_flood", b + liveness(t + 3.0))

# ---------------------------------------------------------------- x_boot
# Heavy pressing THROUGH THE WHOLE BOOT, which is the configuration Felipe's
# ground truth is about ("the real panel does not get corrupted by button
# presses during the boot sequence").
b = ""
t = 2.0
k = 0
while t < 21.0:
    tag, mask, nm = SOUND[k % len(SOUND)]
    b += press(t, tag, mask, "B%d %s" % (k, nm), 0.12)
    t += 0.3
    k += 1
write("x_boot", b + liveness(24.0))

# ---------------------------------------------------------------- x_menu
# Screen transitions: every menu entry/exit repaints the LCD and reprograms
# LEDs, i.e. a burst of CPU->panel commands with the receiver closed.
b = ""
t = 24.0
MENUS = [("CPR_SEG10", 0x20, "MENU:DISK"), ("CPR_SEG10", 0x04, "MENU:SOUND"),
         ("CPR_SEG10", 0x08, "MENU:CONTROL"), ("CPR_SEG10", 0x10, "MENU:MIDI")]
for k in range(24):
    tag, mask, nm = MENUS[k % len(MENUS)]
    b += press(t, tag, mask, "MN%d %s" % (k, nm), 0.15)
    t += 0.45
    b += press(t, "CPL_SEG7", 0x08, "EXIT", 0.15)
    t += 0.45
write("x_menu", b + liveness(t + 2.0))

# ---------------------------------------------------------------- x_long
# LONG SOAK: ~4 emulated minutes of drifting-interval presses.  Degradation in
# this family has shown up late before (option C's b3 only died at 220 presses).
b = ""
t = 26.0
k = 0
dt = 0.31
while t < 260.0:
    tag, mask, nm = SOUND[k % len(SOUND)]
    b += press(t, tag, mask, "L%d %s" % (k, nm), 0.09)
    t += dt
    dt += 0.011
    if dt > 1.2:
        dt = 0.17
    k += 1
b += "log('x_long presses = %d')\n" % k
write("x_long", b + liveness(t + 2.0))

# ---------------------------------------------------------------- x_idle
# a1's exact strand-provoking burst, then a LONG idle, then liveness.  Under
# the shipped build the link never recovers; under A there should be nothing to
# recover from, and nothing should decay during the idle either.
b = ""
t = 30.0
for k in range(90):
    tag, mask, nm = SOUND[k % len(SOUND)]
    b += press(t, tag, mask, "I%d %s" % (k, nm), 0.07)
    t += 0.15
write("x_idle", b + liveness(150.0))

# ---------------------------------------------------------------- x_simN
# MINIMISATION of x_multi: how many buttons pressed AT THE SAME INSTANT does it
# take?  Same cadence (0.6 s apart, held 0.12 s), only the group size changes.
SIM = [("CPR_SEG2", 0x01), ("CPR_SEG1", 0x02), ("CPL_SEG0", 0x01), ("CPR_SEG4", 0x08),
       ("CPR_SEG6", 0x01), ("CPR_SEG8", 0x80), ("CPR_SEG3", 0x01), ("CPL_SEG6", 0x01)]
for n in (2, 3, 4):
    b = ""
    t = 30.0
    for k in range(20):
        for (tag, mask) in SIM[:n]:
            b += press(t, tag, mask, "S%d %s/%02X" % (k, tag, mask), 0.12)
        t += 0.6
    write("x_sim%d" % n, b + liveness(t + 2.0))

# ------------------------------------------------------------- x_rateNN
# Rate sweep between the two known points: a1 (0.15 s = 6.7 Hz) SURVIVES under
# option A, x_flood (0.05 s = 20 Hz) DIES.  Single presses only, no simultaneity.
for ms, hold in ((75, 0.05), (100, 0.06), (125, 0.07)):
    b = ""
    t = 30.0
    for k in range(160):
        tag, mask, nm = SOUND[k % len(SOUND)]
        b += press(t, tag, mask, "R%d %s" % (k, nm), hold)
        t += ms / 1000.0
    write("x_rate%03d" % ms, b + liveness(t + 3.0))
