-- kn24_fontsrc.lua -- where does the KN2400 text drawer fetch its glyphs?
-- rig-machine: kn2400
--
-- THE SYMPTOM (screenshot, 2026-08-14): the KN2400 draws ICONS correctly -- the grand-piano
-- glyphs in the part cells are clean -- but every run of TEXT renders as a solid black bar.
-- So the blitter and compositor work; each glyph is coming back fully set.
--
-- THE HYPOTHESIS: it reads glyph bitmaps from the "table" region 0x48000000-0x483FFFFF,
-- which the driver declares ROMREGION_ERASEFF because no such chip is dumped for this
-- family. All-0xFF glyph data draws as a filled cell -- exactly the symptom.
--
-- WHY THIS IS NOT ALREADY ANSWERED: notes/kn2400-boot.md records a read-tap showing the
-- firmware reads NOTHING from that range -- but that tap covered BOOT. Text is drawn later.
-- This rig therefore keeps the tap installed to t=TAP_UNTIL (default 30 s).
--
-- Reports, to stderr:
--   TABLE reads=<n> first=<addr> last=<addr> distinct_pages=<n>
-- plus a histogram of the top read addresses, and a snapshot for eyeballing.
--
-- A result of reads=0 REFUTES the hypothesis and sends the hunt to the program image
-- instead; a large count with addresses clustered in one sub-range CONFIRMS it and names
-- the font table's offset.
--
--   ./tools/rig.sh kn24_fontsrc kn2400 -s 32

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local UNTIL = tonumber(os.getenv("TAP_UNTIL")) or 30

-- Globals: a local handle is collected by the Lua GC and the tap silently stops firing.
_G.FS = _G.FS or { n = 0, first = nil, last = nil, hist = {}, pages = {} }

_G.FS.tap = prog:install_read_tap(0x48000000, 0x483FFFFF, "tablerd", function(offset, data, mask)
    local f = _G.FS
    f.n = f.n + 1
    if not f.first then
        f.first = offset
        f.t_first = mac.time.seconds + mac.time.attoseconds / 1e18
    end
    f.last = offset
    local page = offset & 0xFFFF0000
    f.pages[page] = (f.pages[page] or 0) + 1
    -- bucket to 256 B so the histogram stays small over millions of reads
    local b = offset & 0xFFFFFF00
    f.hist[b] = (f.hist[b] or 0) + 1
    return nil
end)

_G.FS.h = emu.add_machine_frame_notifier(function()
    if _G.FS.done or mac.time.seconds < UNTIL then return end
    _G.FS.done = true
    local f = _G.FS

    local npages = 0
    for _, _ in pairs(f.pages) do npages = npages + 1 end
    log(string.format("TABLE reads=%d t_first=%.2fs first=%s last=%s distinct_64k_pages=%d",
        f.n, f.t_first or -1,
        f.first and string.format("0x%08X", f.first) or "-",
        f.last  and string.format("0x%08X", f.last)  or "-",
        npages))

    if f.n == 0 then
        log("TABLE HYPOTHESIS REFUTED -- the text drawer never reads the empty table region.")
        log("  Look in the program image for the font instead.")
    else
        local top = {}
        for addr, c in pairs(f.hist) do top[#top + 1] = { addr, c } end
        table.sort(top, function(a, b) return a[2] > b[2] end)
        for i = 1, math.min(12, #top) do
            log(string.format("  0x%08X  %d reads", top[i][1], top[i][2]))
        end
    end
    mac.video:snapshot()
    mac:exit()
end)
