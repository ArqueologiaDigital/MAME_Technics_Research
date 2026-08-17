-- kn5000_wheel_idle.lua -- what does the firmware do to the encoder SCAN LIST when NOBODY
-- touches the TEMPO/PROGRAM wheel?
-- rig-machine: kn5000
--
-- WHY THIS EXISTS. Our wheel emulation is a HLE poke: kn5000_cpanel.cpp:1201 writes
-- [0x19, delta, 0xFF, 0xFF] straight into main-CPU DRAM at 0x8E94, the encoder scan list the
-- firmware's main-loop poll Encoder_ValueScanAndSync (ROM 0xFC5761) consumes. We want to replace
-- that with the REAL producer -- but first we have to know whether a real producer is even running
-- when there is no hardware input. This rig runs the machine with the wheel UNTOUCHED and censuses
-- every access to the list:
--
--   1. WRITE tap on the WHOLE list, 0x8E94..0x8EA9 -- every writer PC, with a count and the value
--      written. Our HLE poke fires only on a detent, so with no input ANY writer here is the
--      FIRMWARE.
--   2. WRITE tap on the CANDIDATE RECORD buffer at 0x8EB2..0x8EB4 -- the 3 bytes the producer
--      fills in BEFORE the filter decides whether to queue them. This is strictly better evidence
--      than the list alone: it catches records that are proposed and then DROPPED.
--   3. WRITE tap on the ENTRY COUNT at 0x8EC4 -- a count going 0 -> 1 -> 0 is the cleanest
--      possible statement that something was queued and then consumed.
--   4. READ  tap on 0x8E94..0x8E95 -- the poll cadence and the polling PC.
--   5. A 0x8E55 sampler -- the boot-time settling-query result (panel command 20 0B), sampled
--      across the whole run, plus a write tap on 0x8E54..0x8E55 naming its writers.
--   6. Every record id it sees is resolved through the firmware's OWN descriptor pointer table at
--      ROM 0xED9C1E (or 0xED9C9E when DRAM 0x8D34 == 0x14), printing the descriptor bytes and
--      handler, so the log says WHICH input was staged rather than just a number.
--      Record 0x19 -> 0xED9B86 = A9 21 00 FF is THE DATA WHEEL and is flagged as such.
--
-- THE ANSWER IS THE SHAPE OF THE CENSUS. If the only writer is the clear (LD (0x8E94),0xFF at
-- ROM 0xFC6C54) and the only reader is the poll, the producer is DORMANT without real hardware
-- input. If other PCs stage records unprompted, the producer is ALIVE and the only thing missing
-- is the wheel's own input source.
--
-- THE FIRMWARE MAP THIS RIG PINNED (v10, measured PCs + disassembly, 2026-08-17):
--   0x8E94..0x8EA9  the scan list: 7 slots x 3 B [record id, value, changed mask] + 0xFF terminator
--   0x8EAC/0x8EAE   ...unused by the list
--   0x8EB2..0x8EB4  the CANDIDATE record the producer fills in
--   0x8EC4          the entry COUNT (0..7)
--   0x8E8C          poll index      0x8E90  record id just read      0x8E78  the copied entry
--   0xFC69EE  ScanAndQueue : lda XIZ,0x8EB2 ; while (count < 7) { produce; if L==0xFF break; append }
--   0xFC6A12  PRODUCE      : fills 0x8EB2..0x8EB4, returns L=0xFF when there is nothing to report
--   0xFC6B87  APPEND       : count*3 + 0x8E94 -> slot; ldi/ldiw copy; count++; 0xFF terminator
--   0xFC6C4F  helper returning the list base   0xFC6C54 clear (list=0xFF, count=0)
--   0xFC5761  Encoder_ValueScanAndSync : the consumer, reads 0x8E94+i*3, dispatches via 0xED9C1E
--   ⚠ 7 is a MEASURED bound (cp (0x8EC4),0x07 at 0xFC69F3 and 0xFC6A09), not a guess: the first
--     draft assumed 16 slots reaching 0x8EC3 and consequently mis-read unrelated variables at
--     0x8EBB / 0x8EC1 as staged record ids 0x00 and 0x01. They are not. Keep the range honest.
--
-- RUN:
--   ./tools/rig.sh kn5000_wheel_idle kn5000 -s 45
--   WI_LIST=0x8DD4 ./tools/rig.sh kn5000_wheel_idle kn5000 -s 45     # v5/v6 firmware
--
-- Environment knobs:
--   WI_LIST    scan-list address     (default 0x8E94; v5/v6 0x8DD4, v7 0x8DF8, v8/v9/v10 0x8E94)
--   WI_SLOTS   list capacity in 3-byte entries (default 7 -> 0x8E94..0x8EA9 incl. terminator)
--   WI_CAND    candidate record buffer (default 0x8EB2, 3 bytes)
--   WI_COUNT   entry-count byte      (default 0x8EC4)
--   WI_SETTLE  settling-result byte  (default 0x8E55)
--   WI_DUMP    seconds between interim censuses (default 10)
--   WI_STACKS  how many appends get a stack dump (default 6; ⚠ XNSP reads 0 on this core, so the
--              dump is empty -- kept only so the next person does not re-try it)
--   WI_SETTLED time the home screen is considered reached (default 24) -- the census is reported
--              SPLIT at this line, because boot traffic and steady-state traffic answer different
--              questions and mixing them is how a boot-only write gets read as a live producer.
--
-- TOUCHES NOTHING. No button is pressed, no adjuster is moved. That is the whole point: this rig
-- is the NULL. If it ever grows a stimulus it stops answering its own question.
--
-- ⚠ PC CAVEAT: the tlcs900 core prefetches, so a reported PC is the neighbourhood of the accessing
-- instruction, not guaranteed to BE it. Disassemble around it before naming a routine
-- (unidasm <rom> -arch tlcs900 -basepc <addr>, file offset = addr - 0xE00000).
--
-- ⚠ Two API hazards this rig encodes: notifier and tap handles are held in a GLOBAL or the Lua GC
-- collects them and the taps never fire; and a tap range on this 16-bit bus must start EVEN and end
-- ODD or MAME aborts with "end address has low bits unset".

local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local sp  = cpu.spaces["program"]

local LIST    = tonumber(os.getenv("WI_LIST")    or "0x8E94")
local SLOTS   = tonumber(os.getenv("WI_SLOTS")   or "7")
local CAND    = tonumber(os.getenv("WI_CAND")    or "0x8EB2")
local COUNT   = tonumber(os.getenv("WI_COUNT")   or "0x8EC4")
local SETTLE  = tonumber(os.getenv("WI_SETTLE")  or "0x8E55")
local DUMP    = tonumber(os.getenv("WI_DUMP")    or "10")
local STACKS  = tonumber(os.getenv("WI_STACKS")  or "6")
local SETTLED = tonumber(os.getenv("WI_SETTLED") or "24")

-- The firmware's own record-descriptor pointer table. Encoder dispatch (ROM 0xFC57CB) does
-- `ld XWA,0x00ED9C1E` and switches to 0x00ED9C9E when DRAM 0x8D34 == 0x14, then indexes by
-- record_id*4 to fetch a 32-bit descriptor pointer. Resolving it here turns a bare record id in
-- the log into the thing the firmware thinks it staged.
local DESC_A, DESC_B, DESC_SEL = 0x00ED9C1E, 0x00ED9C9E, 0x8D34

local function log(s) emu.print_error("[WIDLE] " .. s) end
local function now()
    local mt = mac.time
    return mt.seconds + mt.attoseconds / 1e18
end

-- One global holds every handle and every counter. `selfread` suppresses census entries for the
-- rig's OWN Lua reads of the list -- reading through the address space fires the read tap, and a
-- sampler that counts itself would report a cadence it invented.
_G.WI = {
    w = {},           -- writers  : key -> {n, t0, t1, pc, off, data, mask, phase}
    r = {},           -- readers  : key -> {n, t0, t1, pc, off, mask, phase}
    nw = 0, nr = 0,
    sw = {},          -- writers of the settling byte
    cw = {},          -- writers of the entry-count byte
    rec = {},         -- record ids seen STAGED IN THE LIST  : id -> {n, t0, t1, phase}
    cand = {},        -- record ids seen PROPOSED at 0x8EB2  : id -> {n, t0, t1, phase, pc}
    settle_seen = {}, -- distinct values observed at SETTLE, in order
    settle_last = nil,
    count_last = nil,
    count_max = 0,
    selfread = false,
    nextdump = 0,
    stacks = STACKS,
    log_budget = 60,  -- verbatim first-N write lines, then aggregate only
}

local function pc()
    local ok, v = pcall(function() return cpu.state["PC"].value end)
    return ok and v or -1
end

local function phase() return (now() >= SETTLED) and "steady" or "boot" end

-- Decode which byte lanes a 16-bit access actually touched, as a printable string.
local function lanes(off, data, mask)
    local out = {}
    if (mask & 0x00FF) ~= 0 then out[#out + 1] = string.format("[%04X]=%02X", off, data & 0xFF) end
    if (mask & 0xFF00) ~= 0 then out[#out + 1] = string.format("[%04X]=%02X", off + 1, (data >> 8) & 0xFF) end
    if #out == 0 then out[#out + 1] = string.format("[%04X] mask=%04X (no lane)", off, mask) end
    return table.concat(out, " ")
end

-- Every Lua read of the address space is bracketed by `selfread`, so the rig never counts itself.
local function peek(addr)
    _G.WI.selfread = true
    local ok, v = pcall(function() return sp:read_u8(addr) end)
    _G.WI.selfread = false
    return ok and v or nil
end
local function peek32(addr)
    _G.WI.selfread = true
    local ok, v = pcall(function() return sp:read_u32(addr) end)
    _G.WI.selfread = false
    return ok and v or nil
end

-- Resolve a record id the way the firmware does, and say what it is in words.
local function describe(id)
    local sel = peek(DESC_SEL)
    local tbl = (sel == 0x14) and DESC_B or DESC_A
    local p = peek32(tbl + id * 4)
    if not p or p < 0xE00000 or p > 0xFFFFFF then
        return string.format("id 0x%02X -> descriptor pointer 0x%08X (out of ROM)", id, p or -1)
    end
    local b = {}
    for i = 0, 3 do b[i + 1] = peek(p + i) or 0 end
    local h = peek32(p + 4) or 0
    local tag = ""
    if b[1] == 0xA9 and b[2] == 0x21 then tag = "   ★ THE DATA WHEEL" end
    return string.format("id 0x%02X -> desc 0x%06X = %02X %02X %02X %02X  handler 0x%06X%s",
        id, p, b[1], b[2], b[3], b[4], h, tag)
end

local function stackdump(p, why)
    local S = _G.WI
    if S.stacks <= 0 then return end
    S.stacks = S.stacks - 1
    log(string.format("    stack for %s (PC=0x%08X):", why, p))
    for _, nm in ipairs({ "XNSP", "XSSP" }) do
        local ok, spv = pcall(function() return cpu.state[nm].value end)
        if ok and spv then
            local out = {}
            for i = 0, 7 do
                local w = peek32(spv + i * 4)
                if w then
                    out[#out + 1] = string.format("%08X%s", w,
                        (w >= 0xE00000 and w <= 0xFFFFFF) and "*" or "")
                end
            end
            log(string.format("      %s=0x%08X : %s   (* = looks like a code address)",
                nm, spv, table.concat(out, " ")))
        end
    end
end

-- ---------------------------------------------------------------- write census on the scan list
-- The FULL list: SLOTS entries of 3 bytes. A range on this 16-bit bus must start EVEN and end ODD.
local WLO, WHI = LIST & ~1, (LIST + 3 * SLOTS - 1) | 1
_G.WI.tw = sp:install_write_tap(WLO, WHI, "wi_listw", function(offset, data, mask)
    if _G.WI.selfread then return nil end
    local S, t, p = _G.WI, now(), pc()
    S.nw = S.nw + 1
    local key = string.format("%08X/%04X/%04X/%04X", p, offset, data, mask)
    local e = S.w[key]
    if not e then
        S.w[key] = { n = 1, t0 = t, t1 = t, pc = p, off = offset, data = data, mask = mask, phase = phase() }
        if S.log_budget > 0 then
            S.log_budget = S.log_budget - 1
            log(string.format("W t=%7.3f %-6s PC=0x%08X  %s   (new signature)", t, phase(), p, lanes(offset, data, mask)))
        end
    else
        e.n = e.n + 1; e.t1 = t
        if e.phase ~= phase() then e.phase = "both" end
    end
    -- A write that lands on a SLOT BASE (LIST + 3k) and is not the 0xFF terminator/clear is a
    -- record id being STAGED. That is the producer's signature, so resolve and report it.
    for lane = 0, 1 do
        if (mask & (0xFF << (lane * 8))) ~= 0 then
            local a = offset + lane
            local v = (data >> (lane * 8)) & 0xFF
            if a >= LIST and ((a - LIST) % 3) == 0 and v ~= 0xFF then
                local slot = (a - LIST) // 3
                local r = S.rec[v]
                if not r then
                    r = { n = 0, t0 = t, t1 = t, phase = phase(), pcs = {} }
                    S.rec[v] = r
                    log(string.format("A t=%7.3f %-6s STAGED slot %d  %s   (from PC=0x%08X)",
                        t, phase(), slot, describe(v), p))
                    stackdump(p, string.format("append of record 0x%02X", v))
                end
                r.n = r.n + 1; r.t1 = t
                r.pcs[p] = (r.pcs[p] or 0) + 1
                if r.phase ~= phase() then r.phase = "both" end
            end
        end
    end
    return nil
end)

-- ------------------------------------------------- the CANDIDATE record the producer fills in
-- 0x8EB2..0x8EB4 = [record id, value, changed mask], written by the producer at ROM 0xFC6A12
-- BEFORE the filter at 0xFC6B87 decides whether it earns a list slot. A record that appears here
-- and never in the list was considered and dropped -- which the list tap alone cannot show.
local NLO, NHI = CAND & ~1, (CAND + 2) | 1
_G.WI.tn = sp:install_write_tap(NLO, NHI, "wi_candw", function(offset, data, mask)
    if _G.WI.selfread then return nil end
    local S, t, p = _G.WI, now(), pc()
    for lane = 0, 1 do
        if (mask & (0xFF << (lane * 8))) ~= 0 and (offset + lane) == CAND then
            local v = (data >> (lane * 8)) & 0xFF
            local c = S.cand[v]
            if not c then
                c = { n = 0, t0 = t, t1 = t, phase = phase(), pcs = {} }
                S.cand[v] = c
                log(string.format("P t=%7.3f %-6s PROPOSED  %s   (producer PC=0x%08X)",
                    t, phase(), describe(v), p))
            end
            c.n = c.n + 1; c.t1 = t
            c.pcs[p] = (c.pcs[p] or 0) + 1
            if c.phase ~= phase() then c.phase = "both" end
        end
    end
    return nil
end)

-- ---------------------------------------------------------------- the entry-count byte
local CLO, CHI = COUNT & ~1, (COUNT & ~1) + 1
_G.WI.tc = sp:install_write_tap(CLO, CHI, "wi_countw", function(offset, data, mask)
    if _G.WI.selfread then return nil end
    local S, t, p = _G.WI, now(), pc()
    local odd = (COUNT & 1) == 1
    if (mask & (odd and 0xFF00 or 0x00FF)) == 0 then return nil end
    local v = odd and ((data >> 8) & 0xFF) or (data & 0xFF)
    if v > S.count_max then S.count_max = v end
    local key = string.format("%08X/%02X", p, v)
    local e = S.cw[key]
    if not e then
        S.cw[key] = { n = 1, t0 = t, t1 = t, pc = p, v = v }
        log(string.format("C t=%7.3f %-6s 0x%04X (entry count) <- %d  from PC=0x%08X   (new signature)",
            t, phase(), COUNT, v, p))
    else
        e.n = e.n + 1; e.t1 = t
    end
    return nil
end)

-- ---------------------------------------------------------------- read census on the list head
local RLO, RHI = LIST & ~1, (LIST & ~1) + 1
_G.WI.tr = sp:install_read_tap(RLO, RHI, "wi_listr", function(offset, data, mask)
    if _G.WI.selfread then return nil end
    local S, t, p = _G.WI, now(), pc()
    S.nr = S.nr + 1
    local key = string.format("%08X/%04X/%04X", p, offset, mask)
    local e = S.r[key]
    if not e then
        S.r[key] = { n = 1, t0 = t, t1 = t, pc = p, off = offset, mask = mask, phase = phase() }
    else
        e.n = e.n + 1; e.t1 = t
        if e.phase ~= phase() then e.phase = "both" end
    end
    return nil
end)

-- ---------------------------------------------------------------- the settling-query result byte
local SLO, SHI = SETTLE & ~1, (SETTLE & ~1) + 1
_G.WI.ts = sp:install_write_tap(SLO, SHI, "wi_settlew", function(offset, data, mask)
    if _G.WI.selfread then return nil end
    local S, t, p = _G.WI, now(), pc()
    local odd = (SETTLE & 1) == 1
    local lane = odd and 0xFF00 or 0x00FF
    if (mask & lane) == 0 then return nil end     -- the OTHER byte of the word, not ours
    local v = odd and ((data >> 8) & 0xFF) or (data & 0xFF)
    local key = string.format("%08X/%02X", p, v)
    local e = S.sw[key]
    if not e then
        S.sw[key] = { n = 1, t0 = t, t1 = t, pc = p, v = v }
        log(string.format("S t=%7.3f 0x%04X <- 0x%02X  from PC=0x%08X   (new signature)", t, SETTLE, v, p))
    else
        e.n = e.n + 1; e.t1 = t
    end
    return nil
end)

-- ---------------------------------------------------------------- sampler + census reporting
local function sorted(tbl)
    local a = {}
    for _, e in pairs(tbl) do a[#a + 1] = e end
    table.sort(a, function(x, y) return x.n > y.n end)
    return a
end

local function census(tag)
    local S, t = _G.WI, now()
    local hexbytes = {}
    for i = 0, 3 * SLOTS do hexbytes[#hexbytes + 1] = string.format("%02X", peek(LIST + i) or 0xFF) end
    local b = peek(LIST) or -1
    log(string.format("=== CENSUS %s at t=%.2f =================================", tag, t))
    log(string.format("    scan list 0x%04X..0x%04X = %s", LIST, LIST + 3 * SLOTS,
        table.concat(hexbytes, " ")))
    log(string.format("      head byte 0x%02X -- %s ; entry count 0x%04X = %s (max seen %d of %d)", b,
        (b == 0xFF) and "0xFF = EMPTY, nothing staged" or "NON-EMPTY, an entry is staged",
        COUNT, tostring(peek(COUNT)), S.count_max, SLOTS))
    log(string.format("    candidate 0x%04X = %02X %02X %02X ; 0x%04X (settling result) = %s",
        CAND, peek(CAND) or 0xFF, peek(CAND + 1) or 0xFF, peek(CAND + 2) or 0xFF, SETTLE,
        S.settle_last and string.format("0x%02X", S.settle_last) or "unread"))
    local function idcensus(tbl, what)
        local k = {}
        for id in pairs(tbl) do k[#k + 1] = id end
        table.sort(k)
        log(string.format("    RECORD IDS %s: %d distinct", what, #k))
        local wheel = false
        for _, id in ipairs(k) do
            local r = tbl[id]
            local span = r.t1 - r.t0
            if id == 0x19 then wheel = true end
            local pl = {}
            for ppc, pn in pairs(r.pcs or {}) do pl[#pl + 1] = string.format("0x%08X x%d", ppc, pn) end
            table.sort(pl)
            log(string.format("      n=%-6d %s  t=%.2f..%.2f  %s%s  by %s", r.n, describe(id), r.t0, r.t1,
                r.phase, span > 1.0 and string.format("  ~%.2f/s", r.n / span) or "",
                table.concat(pl, ", ")))
        end
        log(string.format("      -> record 0x19 (the data wheel) %s in this set",
            wheel and "★ APPEARS" or "NEVER APPEARS"))
    end
    idcensus(S.cand, "PROPOSED by the producer at " .. string.format("0x%04X", CAND))
    idcensus(S.rec, "STAGED into the list by the firmware itself")
    log(string.format("    writes to 0x%04X..0x%04X : %d total, %d distinct signatures",
        WLO, WHI, S.nw, #sorted(S.w)))
    for _, e in ipairs(sorted(S.w)) do
        log(string.format("      W n=%-7d PC=0x%08X  %-26s  t=%.2f..%.2f  %s",
            e.n, e.pc, lanes(e.off, e.data, e.mask), e.t0, e.t1, e.phase))
    end
    log(string.format("    reads  of 0x%04X..0x%04X : %d total, %d distinct signatures",
        RLO, RHI, S.nr, #sorted(S.r)))
    for _, e in ipairs(sorted(S.r)) do
        local span = e.t1 - e.t0
        log(string.format("      R n=%-7d PC=0x%08X  off=0x%04X mask=%04X  t=%.2f..%.2f  %s  %s",
            e.n, e.pc, e.off, e.mask, e.t0, e.t1, e.phase,
            span > 0.5 and string.format("~%.0f reads/s", e.n / span) or ""))
    end
    log(string.format("    writes to 0x%04X (entry count) : %d distinct signatures", COUNT, #sorted(S.cw)))
    for _, e in ipairs(sorted(S.cw)) do
        log(string.format("      C n=%-7d PC=0x%08X  count<-%-3d t=%.2f..%.2f", e.n, e.pc, e.v, e.t0, e.t1))
    end
    log(string.format("    writes to 0x%04X : %d distinct signatures", SETTLE, #sorted(S.sw)))
    for _, e in ipairs(sorted(S.sw)) do
        log(string.format("      S n=%-7d PC=0x%08X  value=0x%02X  t=%.2f..%.2f", e.n, e.pc, e.v, e.t0, e.t1))
    end
    local hist = {}
    for _, v in ipairs(S.settle_seen) do hist[#hist + 1] = string.format("t=%.2f 0x%02X", v.t, v.v) end
    log(string.format("    0x%04X sample history (%d changes): %s", SETTLE, #S.settle_seen,
        (#hist > 0) and table.concat(hist, " -> ") or "never sampled"))
    log("=== END CENSUS " .. tag .. " ===")
end

log(string.format("armed: list 0x%04X..0x%04X (%d slots x 3 B + terminator), candidate 0x%04X, "
    .. "count 0x%04X, read tap 0x%04X..0x%04X, settle 0x%04X, settled-line t=%.0f. "
    .. "NOTHING is pressed or turned in this rig.",
    LIST, LIST + 3 * SLOTS, SLOTS, CAND, COUNT, RLO, RHI, SETTLE, SETTLED))

_G.WI.h = emu.add_machine_frame_notifier(function()
    local S, t = _G.WI, now()
    local v = peek(SETTLE)
    if v and v ~= S.settle_last then
        S.settle_last = v
        S.settle_seen[#S.settle_seen + 1] = { t = t, v = v }
        log(string.format("S t=%7.3f 0x%04X now reads 0x%02X   (CW bit7=%d CCW bit6=%d)",
            t, SETTLE, v, (v >> 7) & 1, (v >> 6) & 1))
    end
    if t >= S.nextdump then
        S.nextdump = S.nextdump + DUMP
        census(string.format("t%.0f", t))
    end
end)
