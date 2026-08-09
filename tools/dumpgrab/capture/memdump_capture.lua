-- memdump_capture.lua -- KN7000 MEMORY DUMP capture harness (MAME autoboot script).
--
-- Boots kn7000, opens the hidden MEMORY DUMP viewer with the 1/4/5/8 UP+DOWN chord, dials a
-- chosen start address, sweeps N pages with the "orange button" (balance column 6 = +0x100),
-- and records the result as a movie AND/OR as one PNG per frame, plus a MANIFEST that ties
-- every recorded frame to the address the firmware had loaded at that moment.
--
-- Driven entirely by environment variables so capture.sh owns the policy:
--   DG_DIR      directory holding memdump_lib.lua                     (required)
--   DG_OUT      log file                                              (default /tmp/dg.log)
--   DG_MANIFEST manifest CSV path                                     (default $DG_DIR/manifest.csv)
--   DG_META     manifest JSON summary path                            (default alongside CSV)
--   DG_START    start address, hex                                    (default 0x48400000)
--   DG_PAGES    number of pages to sweep                              (default 32)
--   DG_MODE     "hold" = hold the orange button and let the firmware auto-repeat
--               "tap"  = discrete taps of DG_HOLD frames + DG_GAP frames    (default hold)
--   DG_HOLD     tap-mode hold in frames                               (default 8)
--   DG_GAP      tap-mode gap  in frames                               (default 8)
--   DG_SNAP     "all" = one PNG per frame of the sweep window
--               "page" = one PNG per page (taken when the address changes + DG_SNAPDELAY)
--               "none"                                                (default all)
--   DG_SNAPDELAY frames to wait after a page change before the "page" snapshot (default 4)
--   DG_MOVIE    "avi" | "mng" | "none"                                (default avi)
--   DG_MOVIEPATH absolute movie path (extension added by MAME)
--   DG_PRERUN   frames of recording before the sweep starts           (default 30)
--   DG_POSTRUN  frames of recording after the sweep ends              (default 60)
--
-- NOTE ON MOVIES: MAME's video_manager::begin_recording() clears any existing recording,
-- so AVI and MNG cannot be produced in the same run. Ask for one per run.

local DIR = os.getenv("DG_DIR") or "."
local L   = dofile(DIR .. "/memdump_lib.lua")
local LOG = L.LOG

local function env(k, d) local v = os.getenv(k); if v == nil or v == "" then return d end return v end
local function envn(k, d) return tonumber(env(k, tostring(d))) end

local START     = tonumber(env("DG_START", "0x48400000")) or 0x48400000
local PAGES     = envn("DG_PAGES", 32)
local MODE      = env("DG_MODE", "hold")
local HOLD      = envn("DG_HOLD", 8)
local GAP       = envn("DG_GAP", 8)
local SNAP      = env("DG_SNAP", "all")
local SNAPDELAY = envn("DG_SNAPDELAY", 4)
local MOVIE     = env("DG_MOVIE", "avi")
local MOVIEPATH = env("DG_MOVIEPATH", "/tmp/dg_movie")
local PRERUN    = envn("DG_PRERUN", 30)
local POSTRUN   = envn("DG_POSTRUN", 60)
local MANIFEST  = env("DG_MANIFEST", DIR .. "/manifest.csv")
local META      = env("DG_META", (MANIFEST:gsub("%.csv$", "") .. ".json"))

----------------------------------------------------------------- manifest state
local rows      = {}          -- {relframe, absframe, seconds, addr, snapidx}
local snapidx   = -1          -- index of the NEXT snapshot MAME will write
local recording = false
local relframe  = -1

-- per-frame sampler: installed as L.onframe so it runs BEFORE the coroutine step,
-- i.e. it observes the state that produced the frame MAME has just emitted.
local function sample(take_snapshot)
  if not recording then return end
  relframe = relframe + 1
  local si = -1
  if take_snapshot then
    snapidx = snapidx + 1
    si = snapidx
    L.mach.video:snapshot()
  end
  rows[#rows + 1] = { relframe, L.frame, L.mach.time.seconds, L.addr(), si }
end

local snap_all = (SNAP == "all")
L.onframe = function() sample(snap_all) end

----------------------------------------------------------------- main
local function main()
  -- 1. wait for the boot to settle (LCD hash stable for 90 frames, after t>=15 s)
  local last, stable = -1, 0
  L.waituntil(function()
    if L.mach.time.seconds < 15 then return false end
    local h = L.lcdhash()
    if h == last then stable = stable + 1 else stable = 0; last = h end
    return stable >= 90
  end, 3600)
  LOG(("BOOT settled t=%.2fs frame=%d"):format(L.mach.time.seconds, L.frame))

  -- 2. open the hidden viewer
  if not L.open_memdump(60) then LOG("ABORT: chord did not fire"); L.mach:exit(); return end
  LOG(("OPEN slot=%d ADR=%08X"):format(L.slot(), L.addr()))

  -- 3. dial the start address
  local ok, n = L.dial_to(START, 20, 20)
  LOG(("DIAL -> %08X in %d presses (%s)"):format(L.addr(), n, ok and "exact" or "FAILED"))
  if not ok then LOG("ABORT: could not dial start address"); L.mach:exit(); return end
  L.waitf(60)

  -- 4. start recording
  if MOVIE ~= "none" then
    L.mach.video:begin_recording(MOVIEPATH, MOVIE)
    LOG(("RECORD %s -> %s (is_recording=%s)"):format(MOVIE, MOVIEPATH, tostring(L.mach.video.is_recording)))
  end
  local sw, sh = L.mach.video:snapshot_size()
  LOG(("SNAPSIZE %dx%d  snap_native=%s"):format(sw, sh, tostring(L.mach.video.snap_native)))
  recording = true
  L.waitf(PRERUN)

  -- 5. sweep -------------------------------------------------------------------
  local first = L.addr()
  local target = (first + PAGES * 0x100) & 0xffffffff
  local t0 = L.frame
  if MODE == "hold" then
    -- hold the orange button; the firmware's own key auto-repeat walks the pages
    local c = L.COL[6]
    L.setbtn(c[1], c[2], 1)
    -- stop on "reached or passed": robust even if a repeat tick were ever missed by the poll
    local reached = L.waituntil(function()
      return ((L.addr() - first) & 0xffffffff) >= (PAGES * 0x100)
    end, PAGES * 120 + 600)
    L.setbtn(c[1], c[2], 0)
    LOG(("SWEEP hold: %08X -> %08X in %d frames (%s)"):format(
        first, L.addr(), L.frame - t0, reached and "reached target" or "TIMEOUT"))
  else
    for _ = 1, PAGES do L.tap(6, 1, HOLD, GAP) end
    LOG(("SWEEP tap: %08X -> %08X in %d frames (hold=%d gap=%d)"):format(
        first, L.addr(), L.frame - t0, HOLD, GAP))
  end
  L.waitf(POSTRUN)
  recording = false

  if MOVIE ~= "none" then L.mach.video:end_recording(); LOG("RECORD stopped") end

  -- 6. manifest ----------------------------------------------------------------
  -- One row per recorded frame. relframe is the 0-based index INTO THE MOVIE, absframe the
  -- emulated frame number, addr the viewer's live address cell (= the page the firmware was
  -- displaying/painting), snap the PNG index if one was taken on that frame (-1 otherwise).
  local mf = io.open(MANIFEST, "w")
  mf:write("relframe,absframe,seconds,addr,snap\n")
  for _, r in ipairs(rows) do
    mf:write(("%d,%d,%.6f,0x%08X,%d\n"):format(r[1], r[2], r[3], r[4], r[5]))
  end
  mf:close()

  -- per-page summary: first/last frame each address was live for
  local pages, order = {}, {}
  for _, r in ipairs(rows) do
    local a = r[4]
    if not pages[a] then pages[a] = { first = r[1], last = r[1], n = 0, snaps = {} }; order[#order + 1] = a end
    local p = pages[a]
    if r[1] < p.first then p.first = r[1] end
    if r[1] > p.last then p.last = r[1] end
    p.n = p.n + 1
    if r[5] >= 0 then p.snaps[#p.snaps + 1] = r[5] end
  end
  local jf = io.open(META, "w")
  jf:write("{\n")
  jf:write(('  "machine": "kn7000",\n'))
  jf:write(('  "screen_w": %d, "screen_h": %d, "fps": 60,\n'):format(sw, sh))
  jf:write(('  "start_addr": "0x%08X", "pages_requested": %d,\n'):format(START, PAGES))
  jf:write(('  "mode": "%s", "hold_frames": %d, "gap_frames": %d,\n'):format(MODE, HOLD, GAP))
  jf:write(('  "snap_mode": "%s", "movie": "%s", "movie_path": "%s",\n'):format(SNAP, MOVIE, MOVIEPATH))
  jf:write(('  "frames_recorded": %d, "distinct_pages": %d,\n'):format(#rows, #order))
  jf:write('  "pages": [\n')
  for i, a in ipairs(order) do
    local p = pages[a]
    jf:write(('    {"addr":"0x%08X","first_frame":%d,"last_frame":%d,"frames":%d,"snaps":[%s]}%s\n')
      :format(a, p.first, p.last, p.n, table.concat(p.snaps, ","), (i < #order) and "," or ""))
  end
  jf:write("  ]\n}\n")
  jf:close()

  local durs = {}
  for _, a in ipairs(order) do durs[#durs + 1] = pages[a].n end
  table.sort(durs)
  LOG(("MANIFEST %d frames, %d distinct pages; frames-per-page min=%d median=%d max=%d")
    :format(#rows, #order, durs[1] or 0, durs[(#durs + 1) // 2] or 0, durs[#durs] or 0))
  LOG("CAPTURE DONE")
  if L.logf then L.logf:close() end
  L.mach:exit()
end

-- "page" snapshot mode: snapshot SNAPDELAY frames after the address changes and every 8 frames
-- after that, for as long as the address holds. build_goldens() in analyze_repaint.py keeps the
-- LAST snapshot of each address, so the golden is always a fully settled repaint no matter how
-- long the firmware takes -- without having to know the page period in advance.
if SNAP == "page" then
  local lastaddr, stable = nil, -1
  L.onframe = function()
    if not recording then return end
    local a = L.addr()
    if a ~= lastaddr then lastaddr = a; stable = 0 else stable = stable + 1 end
    local take = (stable >= SNAPDELAY) and (((stable - SNAPDELAY) % 8) == 0)
    sample(take)
  end
end

L.run(main)
LOG("memdump_capture armed")
