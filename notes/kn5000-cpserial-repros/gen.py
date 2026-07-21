#!/usr/bin/env python3
"""Generate a kn5000 panel-stress lua for a given phase configuration.

Every generated script ends with the SAME instrument-independent liveness
sequence so snapshots are directly comparable between configurations.
"""
import sys, json, os

HDR = r'''
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
'''

FTR = r'''
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
'''

# sound-group buttons, right panel (each opens/refreshes a sound list = visible)
RIGHT = [
    ("CPR_SEG2", 0x01, "PIANO"), ("CPR_SEG2", 0x02, "GUITAR"),
    ("CPR_SEG2", 0x04, "STRINGS"), ("CPR_SEG2", 0x08, "BRASS"),
    ("CPR_SEG2", 0x10, "FLUTE"), ("CPR_SEG2", 0x20, "SAX"),
    ("CPR_SEG1", 0x01, "ORGAN"), ("CPR_SEG1", 0x02, "ORCHPAD"),
    ("CPR_SEG1", 0x04, "SYNTH"), ("CPR_SEG1", 0x08, "BASS"),
    ("CPR_SEG1", 0x80, "DRUMKITS"),
]
# left panel rhythm-group buttons
LEFT = [
    ("CPL_SEG0", 0x01, "STDROCK"), ("CPL_SEG0", 0x02, "RNR"),
    ("CPL_SEG0", 0x04, "POPBALLAD"), ("CPL_SEG0", 0x08, "FUNK"),
    ("CPL_SEG0", 0x10, "SOUL"), ("CPL_SEG0", 0x20, "BIGBAND"),
    ("CPL_SEG0", 0x40, "JAZZ"),
]


def build(cfg):
    out = [HDR]
    a = out.append
    # ---- boot-window presses -------------------------------------------
    bw = cfg.get("bootwin", [])
    for k, (t, which) in enumerate(bw):
        tag, mask, name = (RIGHT + LEFT)[which % len(RIGHT + LEFT)]
        a('press(%.3f, ":cpanel:%s", 0x%02x, "BW%d %s", %.3f)\n' % (t, tag, mask, k, name, cfg.get("hold", 0.25)))
    # ---- late burst -----------------------------------------------------
    lb = cfg.get("late", None)
    tend = cfg.get("tend", 30.0)
    if lb:
        start, interval, count, pool = lb["start"], lb["interval"], lb["count"], lb["pool"]
        t = start
        for k in range(count):
            if pool == "both":
                tag, mask, name = RIGHT[k % len(RIGHT)]
                a('press(%.3f, ":cpanel:%s", 0x%02x, "L%d %s", %.3f)\n' % (t, tag, mask, k, name, cfg.get("hold", 0.25)))
                tag2, mask2, name2 = LEFT[k % len(LEFT)]
                a('press(%.3f, ":cpanel:%s", 0x%02x, "L%db %s", %.3f)\n' % (t + cfg.get("skew", 0.0), tag2, mask2, k, name2, cfg.get("hold", 0.25)))
            else:
                src = RIGHT if pool == "right" else LEFT
                tag, mask, name = src[k % len(src)]
                a('press(%.3f, ":cpanel:%s", 0x%02x, "L%d %s", %.3f)\n' % (t, tag, mask, k, name, cfg.get("hold", 0.25)))
            t += interval
        tend = max(tend, t + 1.0)
    # ---- phase-drift burst: interval creeps so one run samples many phases
    dr = cfg.get("drift", None)
    if dr:
        t = dr["start"]
        iv = dr["iv0"]
        for k in range(dr["count"]):
            tag, mask, name = RIGHT[k % len(RIGHT)]
            a('press(%.4f, ":cpanel:%s", 0x%02x, "D%d %s", %.3f)\n' % (t, tag, mask, k, name, cfg.get("hold", 0.07)))
            t += iv
            iv += dr["step"]
        tend = max(tend, t + 1.0)

    # ---- extra soak presses --------------------------------------------
    soak = cfg.get("soak", None)
    if soak:
        t = soak["start"]
        for k in range(soak["count"]):
            tag, mask, name = RIGHT[k % len(RIGHT)]
            a('press(%.3f, ":cpanel:%s", 0x%02x, "S%d %s", %.3f)\n' % (t, tag, mask, k, name, cfg.get("hold", 0.25)))
            t += soak["interval"]
        tend = max(tend, t + 1.0)

    # ---- uniform liveness tail -----------------------------------------
    L = tend
    a('snap(%.3f, "pre")\n' % (L + 0.0))
    a('snap(%.3f, "pre2")\n' % (L + 1.0))
    a('press(%.3f, ":cpanel:CPR_SEG10", 0x20, "LIVE MENU:DISK")\n' % (L + 2.0))
    a('snap(%.3f, "disk")\n' % (L + 4.0))
    a('press(%.3f, ":cpanel:CPR_SEG10", 0x04, "LIVE MENU:SOUND")\n' % (L + 5.0))
    a('snap(%.3f, "sound")\n' % (L + 7.0))
    a('press(%.3f, ":cpanel:CPR_SEG2", 0x01, "LIVE PIANO")\n' % (L + 8.0))
    a('snap(%.3f, "piano")\n' % (L + 10.0))
    a('press(%.3f, ":cpanel:CPR_SEG1", 0x02, "LIVE ORCHPAD")\n' % (L + 11.0))
    a('snap(%.3f, "orch")\n' % (L + 13.0))
    a('at(%.3f, "done", function() log("RUN DONE"); mac:exit() end)\n' % (L + 14.0))
    a(FTR)
    return "".join(out)


if __name__ == "__main__":
    cfg = json.loads(sys.argv[1])
    sys.stdout.write(build(cfg))
