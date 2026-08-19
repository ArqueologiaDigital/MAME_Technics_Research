-- kn5000_tg_writes.lua -- is the firmware driving the tone generator at all?
-- rig-machine: kn5000
--
-- QUESTION ANSWERED: how many register writes reach IC303, and how many of them are
-- NOTE-ON GATES? This separates "the device makes no sound because it is broken" from
-- "the device makes no sound because nothing is telling it to play".
--
-- The tone generator sits on the SUB-CPU bus: 0x100000 = address latch, 0x100002 = data.
-- The latch selects both a register group and a voice, so this rig shadows the latch and
-- reports gates ((data & 0xFF00) == 0x8100) with the voice they were aimed at.
--
--   TG_REPORT_EVERY=10 ./tools/rig.sh kn5000_tg_writes kn5000 -s 130
--   (pair it with tools/rigs/kn5000_demo_capture.lua's DEMO press to have anything to see)
--
-- ⚠ STARTING THE DEMO TAKES TWO PRESSES, NOT ONE. The DEMO button only opens a menu
--   (DEMONSTRATION / PERFORMANCES / FEATURE PRESENTATION); the presentation itself starts when
--   the LCD soft key beside its row is pressed -- LEFT 4, CPL_SEG9 bit 0x02. Pressing DEMO alone
--   leaves the machine sitting in that menu forever, which is exactly as silent as a broken
--   sound device and looks identical in a wave capture. Nine scripted DEMO presses were spent
--   before a screenshot showed the menu.
--
-- PASS: thousands of gates spread over all four voice banks. Zero writes at all means the
-- firmware never got as far as playing, and no amount of work inside the device will help.

local mac = manager.machine
local function log(s) emu.print_error(s) end

local EVERY = tonumber(os.getenv("TG_REPORT_EVERY") or "") or 10
local PRESS_AT = tonumber(os.getenv("DEMO_PRESS_AT") or "") or 34.0
local HOLD = tonumber(os.getenv("DEMO_HOLD") or "") or 0.5

_G.TGW = _G.TGW or { latch = 0, addr_w = 0, data_w = 0, gates = 0, banks = {}, next_report = 0, pressed = false, released = false }

-- Press DEMO ourselves so this rig is self-contained.
local function demo_field()
    for _, tag in ipairs({ ":CPL_SEG3", ":cpanel:CPL_SEG3" }) do
        local p = mac.ioport.ports[tag]
        if p then
            for _, f in pairs(p.fields) do
                if f.mask == 0x01 then return f end
            end
        end
    end
    return nil
end

local sub = mac.devices[":subcpu"]
if sub == nil then
    log("TGW FATAL -- no :subcpu")
    mac:exit()
    return
end
local space = sub.spaces["program"]

_G.TGW.tap = space:install_write_tap(0x100000, 0x100003, "tg_watch", function (offset, data, mask)
    local S = _G.TGW
    if offset < 0x100002 then
        S.latch = data
        S.addr_w = S.addr_w + 1
    else
        S.data_w = S.data_w + 1
        if (S.latch & 0xFFC0) == 0x0000 and (data & 0xFF00) == 0x8100 then
            S.gates = S.gates + 1
            local bank = (S.latch & 0x3F) >> 4
            S.banks[bank] = (S.banks[bank] or 0) + 1
        end
    end
    return data
end)

local function field_by(tag, mask)
    local p = mac.ioport.ports[":" .. tag] or mac.ioport.ports[":cpanel:" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do if f.mask == mask then return f end end
    return nil
end

local demo = demo_field()
local left4 = field_by("CPL_SEG9", 0x02)    -- "LEFT 4": the FEATURE PRESENTATION row
local left2 = field_by("CPL_SEG10", 0x01)   -- "LEFT 2": "Start the internal DEMO"
log(string.format("TGW watching :subcpu 0x100000-0x100003 (DEMO %s, LEFT4 %s)",
    demo and "found" or "MISSING", left4 and "found" or "MISSING"))

_G.TGW.h = emu.add_machine_frame_notifier(function()
    local S = _G.TGW
    local t = mac.time.seconds

    -- The THREE-press sequence: DEMO opens the menu, LEFT 4 opens FEATURE PRESENTATION,
    -- LEFT 2 starts the internal demo. See tools/rigs/kn5000_demo_capture.lua.
    local function tap(f, name, at)
        if not f then return end
        if not S["down_" .. name] and t >= at then
            f:set_value(1); S["down_" .. name] = true
            log(string.format("TGW press %s at t=%.2f", name, t))
        elseif S["down_" .. name] and not S["up_" .. name] and t >= at + HOLD then
            f:set_value(0); S["up_" .. name] = true
        end
    end
    tap(demo, "DEMO", PRESS_AT)
    tap(left4, "LEFT4", PRESS_AT + 4.0)
    tap(left2, "LEFT2", PRESS_AT + 8.0)

    if os.getenv("TG_SNAP") and t >= PRESS_AT + 20.0 and not S.snapped then
        S.snapped = true
        mac.video:snapshot()
        log("TGW snapshot taken 20s after the start sequence")
    end

    if t >= S.next_report then
        S.next_report = t + EVERY
        local spread = {}
        for b = 0, 3 do table.insert(spread, string.format("b%d=%d", b, S.banks[b] or 0)) end
        log(string.format("TGW t=%6.1f  addr_w=%7d data_w=%7d gates=%6d  [%s]",
            t, S.addr_w, S.data_w, S.gates, table.concat(spread, " ")))
    end
end)
