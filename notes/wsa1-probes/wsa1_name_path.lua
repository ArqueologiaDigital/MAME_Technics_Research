-- Where does the sound-name path stop?
--   A. does CPU 2 read prom_d at all, now that it is mapped?
--   B. does CPU 1 issue link command 0xE2 (remote block read) and get an answer?
--   C. is P7 bit 1 (CPU 1's receiver-busy line) stuck low, i.e. gap C?
local m = manager.machine
local cpu2 = m.devices[":cpu2"]
local cpu1 = m.devices[":cpu1"]
local sp2, sp1 = cpu2.spaces["program"], cpu1.spaces["program"]

local promd_reads, link_c1, link_c2, cmds = 0, 0, 0, {}
local taps = {}

taps[#taps+1] = sp2:install_read_tap(0xf00000, 0xf7ffff, "promd",
    function(off, data, mask) promd_reads = promd_reads + 1 return data end)
-- CPU 1's link port 0x7C0000, CPU 2's 0x100000
taps[#taps+1] = sp1:install_write_tap(0x7c0000, 0x7c0001, "l1",
    function(off, data, mask) link_c1 = link_c1 + 1
        local b = data & 0xff; cmds[b] = (cmds[b] or 0) + 1 return data end)
taps[#taps+1] = sp2:install_write_tap(0x100000, 0x100001, "l2",
    function(off, data, mask) link_c2 = link_c2 + 1 return data end)
_G.wsa1_taps = taps

local reported = false
local function report()
    if reported then return end
    reported = true
    local t = {}
    for b,n in pairs(cmds) do t[#t+1] = string.format("%02X:%d", b, n) end
    table.sort(t)
    emu.print_error(string.format(
        "RESULT promd_reads=%d  cpu1_link_writes=%d  cpu2_link_writes=%d",
        promd_reads, link_c1, link_c2))
    emu.print_error("CPU1 command bytes: " .. table.concat(t, " "))
end

-- report at t=90 s and again at exit, whichever the build supports
_G.wsa1_reporter = emu.add_machine_frame_notifier(function()
    if manager.machine.time.seconds >= 90 then report() end
end)
