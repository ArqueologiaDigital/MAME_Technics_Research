-- remote.lua -- drive a running instrument from a command file, one step at a time.
-- rig-machine: any (kn5000, kn6000, kn7000, ...)
--
-- QUESTION IT SERVES: walking a menu whose soft-key layout is not known in advance (DISK >
-- FORMAT, for one), where each press has to be chosen after seeing the screen the previous
-- one produced. A fixed press schedule cannot do that; this rig waits for instructions.
--
-- Every frame it reads $REMOTE_CMD and runs the lines it has not run yet, in order. After each
-- line it appends "OK <n> <line>" (or "ERR <n> <line>: <reason>") to $REMOTE_CMD.log, with the
-- emulated time, so the caller can tell when a step has been carried out.
--
-- commands (one per line; blank lines and lines starting with # are skipped):
--   press PORT MASK [SECONDS]  hold a panel button (port tag as in the driver's cpanel, mask in
--                              hex) for SECONDS of emulated time (default 0.3), then release
--   snap                       save a snapshot (into -snapshot_directory)
--   wait SECONDS               run SECONDS of emulated time before the next line
--   create PATH                create a new, blank (unformatted) disk in the floppy drive; the
--                              extension picks the format MAME writes when the disk is ejected
--                              (.img = raw sectors, .mfi = MAME's flux-level format)
--   load PATH                  insert an existing disk image
--   unload                     eject the disk (this is when a created or modified image is saved)
--   info                       log whether the drive holds a disk, and its file name
--   lua CODE                   run CODE (one line of Lua) in the machine, e.g. to install a tap;
--                              keep handles in _G or they are garbage-collected
--   exit                       eject nothing, quit MAME (images still in a drive are saved)
--
-- run (from the repo root; the rig keeps running until "exit"):
--   REMOTE_CMD=$HOME/compartilhado/tmp/x/cmd.txt ./tools/rig.sh remote kn5000 -s 0 -- \
--       -snapshot_directory $HOME/compartilhado/tmp/x/snap
local mac = manager.machine
local CMD = assert(os.getenv("REMOTE_CMD"), "set REMOTE_CMD")
local FLOP = os.getenv("REMOTE_FLOPPY") or ":fdc:0:35hd"

local function now() return mac.time.seconds + mac.time.attoseconds / 1e18 end

local function field(tag, mask)
  local p = mac.ioport.ports[":cpanel:" .. tag] or mac.ioport.ports[":" .. tag]
  if not p then return nil end
  for _, f in pairs(p.fields) do if f.mask == mask then return f end end
end

local function report(s)
  local f = io.open(CMD .. ".log", "a")
  if f then f:write(string.format("[%.2f] %s\n", now(), s)); f:close() end
  emu.print_error("REMOTE " .. s)
end

_G.RM = { done = 0, busy_until = 0, release = nil }

local function run(n, line)
  local w = {}
  for x in line:gmatch("%S+") do w[#w + 1] = x end
  local c = w[1]
  if c == "press" then
    local f = field(w[2], tonumber(w[3], 16))
    if not f then return "no such button" end
    f:set_value(1)
    _G.RM.release = { f, now() + (tonumber(w[4] or "") or 0.3) }
    _G.RM.busy_until = _G.RM.release[2]
  elseif c == "snap" then
    mac.video:snapshot()
  elseif c == "wait" then
    _G.RM.busy_until = now() + tonumber(w[2])
  elseif c == "create" then
    local err = mac.images[FLOP]:create(w[2])        -- nil on success, else the message
    if err then return tostring(err) end
  elseif c == "load" then
    local err = mac.images[FLOP]:load(w[2])
    if err then return tostring(err) end
  elseif c == "unload" then
    mac.images[FLOP]:unload()
  elseif c == "lua" then
    local chunk, err = load(line:gsub("^%s*lua%s+", ""))
    if not chunk then return err end
    chunk()
  elseif c == "info" then
    local im = mac.images[FLOP]
    report(string.format("INFO %s exists=%s filename=%s", FLOP, tostring(im.exists),
      tostring(im.filename)))
  elseif c == "exit" then
    mac:exit()
  else
    return "unknown command"
  end
end

_G.RM.h = emu.add_machine_frame_notifier(function()
  local R = _G.RM
  if R.release and now() >= R.release[2] then R.release[1]:set_value(0); R.release = nil end
  if now() < R.busy_until then return end
  local f = io.open(CMD, "r")
  if not f then return end
  local lines = {}
  for l in f:lines() do lines[#lines + 1] = l end
  f:close()
  while R.done < #lines and now() >= R.busy_until do
    R.done = R.done + 1
    local line = lines[R.done]
    if line:match("%S") and not line:match("^%s*#") then
      local ok, err = pcall(run, R.done, line)
      if not ok then report(string.format("ERR %d %s: %s", R.done, line, err))
      elseif err then report(string.format("ERR %d %s: %s", R.done, line, err))
      else report(string.format("OK %d %s", R.done, line)) end
    end
  end
end)
