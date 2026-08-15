-- kn24_tableshape.lua -- what SHAPE of data does the KN2400 expect at 0x48000000?
-- rig-machine: kn2400
--
-- kn24_fontsrc.lua confirmed the firmware reads the undumped "table" region (164,300 reads
-- from t=0.84 s, region declared ROMREGION_ERASEFF because no such chip is dumped for this
-- family). That answered WHETHER. This answers WHAT, which is the part that survives:
-- nobody can dump this ROM today, but a description of the access pattern is a TEST a
-- candidate dump can be checked against when one appears.
--
-- It reports four things kn24_fontsrc.lua buckets away:
--   1. per-address counts in the hot first 256 bytes -- a header POLL and a linear SCAN look
--      identical once bucketed to 256 B, and they mean completely different things
--   2. for every 256 B block that is swept, whether it is swept ONCE or repeatedly
--   3. a reads-per-second timeline -- steady traffic is streaming, a burst that stops is a
--      one-shot table copy, and traffic that never stops is a retry loop
--   4. read WIDTH (8/16/32-bit), which constrains what the data structure can be
--
-- ⚠ THE CAVEAT THAT MATTERS, and it is not small: this region reads back as all-0xFF.
--    A firmware that validates a header and retries on failure will produce a COMPLETELY
--    different access pattern once the header is valid. So this measures "how the KN2400
--    behaves against a missing ROM", which is only the same as "how it reads a real ROM" if
--    the traffic looks like unconditional streaming rather than a failing retry.
--    Distinguishing those two is the whole point of items 1 and 3 -- the rig is built to be
--    able to say "this tells us nothing about the real chip", and that is a real outcome.
--
--   ./tools/rig.sh kn24_tableshape kn2400 -s 32
--   TAP_UNTIL=30 ...        (default 30)
--
-- Prints SHAPE lines to stderr, then a verdict naming which of the two readings the data
-- supports.

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local UNTIL = tonumber(os.getenv("TAP_UNTIL")) or 30
local BASE  = 0x48000000

-- Globals: a local handle is collected by the Lua GC and the tap silently stops firing.
_G.TS = _G.TS or {
    n = 0, addr = {}, blocks = {}, timeline = {}, widths = {}, order = {}, norder = 0,
}

_G.TS.tap = prog:install_read_tap(0x48000000, 0x483FFFFF, "shape", function(offset, data, mask)
    local s = _G.TS
    s.n = s.n + 1
    local t = mac.time.seconds

    -- 1. exact addresses, but only in the hot first 1 KB -- unbounded elsewhere would grow
    --    a table with millions of keys.
    if offset - BASE < 0x400 then
        s.addr[offset] = (s.addr[offset] or 0) + 1
    end

    -- 2. per-256 B block: count, and how many distinct SECONDS it was touched in. A block
    --    copied once is touched in one second; a block re-read forever is touched in many.
    local b = offset & 0xFFFFFF00
    local blk = s.blocks[b]
    if not blk then
        blk = { n = 0, secs = {}, nsecs = 0, first = t }
        s.blocks[b] = blk
        s.norder = s.norder + 1
        s.order[s.norder] = b          -- discovery order: the sequence blocks are first touched
    end
    blk.n = blk.n + 1
    if not blk.secs[t] then blk.secs[t] = true; blk.nsecs = blk.nsecs + 1 end
    blk.last = t

    -- 3. timeline, one bucket per second
    s.timeline[t] = (s.timeline[t] or 0) + 1

    -- 4. access width, from the byte-lane mask
    local w = 0
    local m = mask
    while m ~= 0 do
        if (m & 0xFF) ~= 0 then w = w + 1 end
        m = m >> 8
    end
    s.widths[w] = (s.widths[w] or 0) + 1
    return nil
end)

_G.TS.h = emu.add_machine_frame_notifier(function()
    if _G.TS.done or mac.time.seconds < UNTIL then return end
    _G.TS.done = true
    local s = _G.TS

    log(string.format("SHAPE total_reads=%d", s.n))
    if s.n == 0 then
        log("SHAPE no reads -- nothing to characterise.")
        mac:exit()
        return
    end

    -- ---- widths
    local wl = {}
    for w, c in pairs(s.widths) do wl[#wl + 1] = string.format("%d-byte:%d", w, c) end
    table.sort(wl)
    log("SHAPE widths " .. table.concat(wl, " "))

    -- ---- hot addresses
    log("SHAPE hottest individual addresses in the first 1 KB:")
    local al = {}
    for a, c in pairs(s.addr) do al[#al + 1] = { a, c } end
    table.sort(al, function(x, y) return x[2] > y[2] end)
    for i = 1, math.min(12, #al) do
        log(string.format("   +0x%03X  %d reads", al[i][1] - BASE, al[i][2]))
    end
    local distinct_lowaddrs = #al

    -- ---- blocks: swept once vs repeatedly
    local once, repeated, nblocks = 0, 0, 0
    local bl = {}
    for b, blk in pairs(s.blocks) do
        nblocks = nblocks + 1
        bl[#bl + 1] = { b, blk }
        if blk.nsecs <= 1 then once = once + 1 else repeated = repeated + 1 end
    end
    table.sort(bl, function(x, y) return x[2].n > y[2].n end)
    log(string.format("SHAPE blocks=%d swept_in_one_second=%d touched_in_many=%d",
        nblocks, once, repeated))
    log("SHAPE busiest blocks (reads, distinct seconds touched, first..last):")
    for i = 1, math.min(10, #bl) do
        local b, blk = bl[i][1], bl[i][2]
        log(string.format("   0x%08X  %6d reads  %3d s  t=%.0f..%.0f%s",
            b, blk.n, blk.nsecs, blk.first, blk.last,
            (blk.n == 256 and blk.nsecs <= 1) and "   <- exactly 256 reads in one second: a linear sweep" or ""))
    end

    -- ---- discovery order, which shows whether blocks are walked in address order
    local ord = {}
    for i = 1, math.min(12, s.norder) do
        ord[#ord + 1] = string.format("+0x%X", s.order[i] - BASE)
    end
    log("SHAPE blocks first touched in this order: " .. table.concat(ord, " "))

    -- ---- timeline
    local secs = {}
    for t, _ in pairs(s.timeline) do secs[#secs + 1] = t end
    table.sort(secs)
    local tl = {}
    for _, t in ipairs(secs) do tl[#tl + 1] = string.format("%d:%d", t, s.timeline[t]) end
    log("SHAPE reads per second -- " .. table.concat(tl, " "))

    -- ---- the verdict this rig exists to reach
    --
    -- The first draft classified on "was a block touched in more than one second", which put
    -- 112 of 113 blocks in the "repeated" bucket and reported a useless "mixed". Two seconds
    -- apart is not a poll. The questions that actually separate the readings are: does the
    -- traffic STOP, and is it concentrated in a small header?
    local last_sec = secs[#secs]
    local ceased = (last_sec < UNTIL - 5)
    -- how much of the traffic lands in the first 0x40 bytes -- the descriptor, if there is one
    local hdr = 0
    for a, c in pairs(s.addr) do if a - BASE < 0x40 then hdr = hdr + c end end
    local hdr_pct = 100.0 * hdr / s.n
    log("SHAPE ----")
    log(string.format("SHAPE header_share=%.1f%% of all reads land in the first 0x40 bytes; "
        .. "traffic %s at t=%d of %d", hdr_pct, ceased and "CEASED" or "was still running",
        last_sec, UNTIL))
    if not ceased then
        log("SHAPE VERDICT: traffic never stops -- consistent with a RETRY/POLL loop against the")
        log("  all-0xFF region. Says little about what a real ROM would see.")
    elseif hdr_pct >= 40 then
        log("SHAPE VERDICT: a BOUNDED, boot-time walk driven by a DESCRIPTOR in the first 0x40 B.")
        log("  It stops and does not resume, so whatever the firmware wanted it took once, early,")
        log("  and later drawing works from a RAM copy -- not from live fetches out of this ROM.")
        log("  ⚠ The addresses walked BEYOND the header are what an all-0xFF descriptor produces.")
        log("  They are NOT evidence of the real ROM's layout. The solid finding is the descriptor:")
        log("  its offset, its field width, and the fact that it is consulted constantly.")
    else
        log("SHAPE VERDICT: a bounded walk not dominated by a header -- read the block lines above.")
    end

    mac.video:snapshot()
    mac:exit()
end)
