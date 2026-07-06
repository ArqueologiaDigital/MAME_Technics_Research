# KN7000 service / factory diagnostic mode

The firmware contains a full factory **test menu** (the service manual's
adjustment/diagnostic section). Enabling it in the emulator would give a
*reliable, complete* PANEL-SWITCH ↔ LED map — the cleanest way to bind every
control-panel button in the MAME layout (far better than the empirical
"press a segment, watch the screen" probes used so far for the sound/rhythm
grids). This note records the structure found by static RE so a later tick can
finish enabling it.

## Test-suite functions (from the firmware's own reflection symbols → kn7000.sym)

| Addr | Symbol | Service-manual test |
|------|--------|---------------------|
| 0x4849FDCF / 0x4849FDF8 | RomTestRunFunc / MainRomTestFunc | program-ROM checksum |
| 0x484A0165 / 0x484A018E | RamTestRunFunc / MainRamTestFunc | work-RAM |
| 0x484A0626 / 0x484A062A | DspTestFunc / MainDspCheck | DSP |
| 0x484A062E / 0x484A0657 | OthDeviceTestRunFunc / MainDeviceTestFunc | device |
| 0x484A09E0 / 0x484A0A32 | FdTestRunFunc / TestDiskFunc | floppy / disk |
| 0x484A11F7 / 0x484A13E1 | CpRamEditCheck / MainCpCheck | control-panel RAM |
| 0x484A148D / 0x484A14B6 | TestRgbwbRunFunc / TestRgbwbFunc | RGB white-balance (video) |
| 0x484A16DD / 0x484A170D | TestCrosstarlRunFunc / TestCrosstalkFunc | audio crosstalk |
| 0x484A173D / 0x484A1766 | TestSampleRunFunc / TestSampleFunc | sample play |
| 0x484A1805 / 0x484A1835 | TestContrastRunFunc / TestContrastFunc | LCD contrast |
| 0x484A1865 / 0x484A1895 | TestVideoOutRunFunc / TestVideoOutFunc | video-out |
| **0x484A1AAD / 0x484A1AFE** | **InOutTestFilter / InOutTestWindowProc** | **PANEL SW & LED test** ← the one we want |
| 0x484A2E11 / 0x484A2E3A | WaveRomTestRunFunc / MainWaveRomTestFunc | wave-ROM (the undumped ICs) |
| 0x484A3C5F | MainSDTestFunc | SD/disk |
| 0x484A40F8 | BoardTestFunc | board |
| 0x484A497B | **TestModeFunc** | test-mode menu **dispatcher** (switch on selection in d1) |
| 0x484A4BFC | AcTestMenuPageProc | AC-test menu page proc |

## Menu tables
Function-pointer / menu-item records live at **0x4874AD34 – 0x4874AFF0**
(consecutive u32 handler pointers; e.g. MainRomTestFunc@0x4874AF90,
MainRamTestFunc@0x4874AF94, MainDeviceTestFunc@0x4874AF98, TestModeFunc@0x4874AFE0,
MainSDTestFunc@0x4874AFF0, BoardTestFunc@0x4874AFE8, InOutTestWindowProc@0x4874AD34
and @0x4874AE58). The menu-page handlers that read these tables are at
0x4849F8F0 (→0x4874AE58) and 0x4849F974 (→0x4874AF90).

## Panel SW & LED test data
`PanelSwitchClassTable` @ **0x4860C9F4** — service panel-test mode: `switch# ->
[LED reg, value]`. Referenced once, at 0x484A0D23 (inside the panel-test code).
In the panel test each physical switch press lights a specific LED and shows the
switch identity, so driving a normalized `SEGnn.bit` port in this mode reveals
`SEGnn.bit -> switch# -> LED -> (service-manual matrix) -> button name`, i.e. the
exact `.lay` binding for every button.

## Entry (STILL TO CRACK)
Service manual: *hold C#3 + D#3 + C#4, then power on*. Attempt this tick:
injected note-ons 0x31/0x33/0x3D (C#3/D#3/C#4 at C4=60) into the modeled voice
FIFO (0x98050004) early in boot (t=10..900 ticks, held / no note-off) → still
booted to the normal home screen. So either (a) the note numbering differs
(Technics keyboard internal index vs MIDI), (b) the boot service-check reads the
held keys via a path *other* than the voice FIFO (likely the panel sub-CPU serial
scan or a direct key-matrix register, since the FIFO feeds the tone generator,
not the boot key-check), or (c) timing (the check ran before the injection).

### Next-tick plan
1. Find the early-boot key-combo check: locate the reset/init path and the read
   it uses for the 3 held keys (search the boot path for a 3-way note compare or
   a panel/key-matrix read gated on power-on). PanelTransaction/PanelRxState8
   (panel serial) are candidates for how the held keys arrive at boot.
2. Once the read + expected values are known, inject correctly **or** temporarily
   force the branch in the driver (research hack) to reach TestModeFunc → InOut
   test.
3. In the InOut test, sweep every `SEGnn.bit`, record switch#/LED, and combine
   with the CPR/CPC/CPL matrices (notes/panel-matrix-service-manual.md) to bind
   all remaining `.lay` buttons — closing out "make all buttons work".

## Related
- Normal-mode dispatch: `PanelButtonDispatch` 0x484ADB59 uses descriptor tables
  0x48614978/0x486149FC; `PanelWireNormTable` 0x486135A0 maps wire→normSeg.
- Matrices + verified bindings: notes/panel-matrix-service-manual.md.

## UPDATE: the panel-test mode flag 0x5006BFB2 (found + runtime-tested)
The panel-test button path is gated by RAM flag **0x5006BFB2** (checked in
PanelButtonDispatch 0x484ADB59 at 0x484ADB22/0x484ADB74; also 0x484AE292). When
`==1`, a button press routes to the panel-test handler (0x484A0CB0 → switch-class
LED lookup) instead of the normal descriptor dispatch. **Runtime-confirmed:**
writing `0x5006BFB2=1` via Lua then pressing GUITAR (SEG0C.b1) no longer opens the
GUITAR sound screen — the dispatch is re-routed. (The full test *screen* still
needs the proper service-menu entry; the flag alone only re-routes buttons.)

## KEY CAVEAT — the emulator panel-test is CIRCULAR for .lay mapping
Enabling the panel-test in the emulator does **not** help assign the remaining
`.lay` buttons (LCD soft-keys, CPC screen buttons) to normSeg.bit. Reason: on real
hardware the test maps *physical button → switch# → normSeg*. But in the emulator
the `.lay` buttons already **drive normSeg ports directly** — there is no physical
panel to press, so pressing a `.lay` button in the test just echoes the normSeg we
assigned. The missing *physical → normSeg* half lives in the undumped panel
sub-CPU and can only be recovered by:
  1. the **real hardware** panel-test (hold C#3+D#3+C#4 at power-on → press each
     physical button → read its switch#), or
  2. a panel sub-CPU firmware dump, or
  3. **empirical screen-probing in the emulator** — press each reachable
     normSeg.bit, observe the on-screen effect, match to the expected button
     function (the method that mapped the sound categories / genres / mutes). This
     is the only fully-autonomous emulator path, and it works for buttons with a
     visible effect (e.g. the RIGHT soft-keys show as part-select RIGHT1/RIGHT2).
So the ~70 buttons wired by descriptor-function-matching are the confidently
mappable set from static RE alone; the rest need (1) or (3).
