## Index: what each `rt_` probe answers

Recovered 2026-09-23 from session scratch. The eleven scripts were committed here
on 2026-09-20; this per-script table was not, and it is the part that says what
each one reads and what a pass means. Filenames below carry the `rt_` prefix the
committed copies use.

Measured with BOTH binaries, read-only, no rebuild:

    WORKING   ~/compartilhado/kn7000_mame_build/kn7000 wsa1r -rompath ~/compartilhado/kn7000-emulator/roms
    STALLING  <the upstream-extraction build> wsa1 wsa1r -rompath <its own rompath>

Common flags: `-skip_gameinfo -window -autoboot_delay 0 -autoboot_script <script>`
plus private `-nvram_directory`/`-cfg_directory` (RULE 20). Env: `STOP_AT`, `BUCKET_S`.
The stalling build wants `qsigcwsa1dx.bin` / `am29f400t.bin`, the overlay `*.ic21` /
`*.ic22` — symlink, never copy a ROM.

| script | question it answers | signal read | pass/fail meaning |
|---|---|---|---|
| `rt_timeline.lua` (copy of `notes/wsa1-probes/wsa1_cpu2_timeline.lua`) | where are the two CPUs? | CURPC per frame | overlay CPU1 leaves 0xF8E671 by t=3; extraction sits there to t=80 |
| `rt_stallwatch.lua` | why does CPU1 spin at 0xF8E671-81? | CPU1 RAM (0x80) 16-bit tick, (0x8a) bit 7, (0x6007e1) | tick advances 485/s (overlay) vs 30/s (extraction); the loop exits on tick delta > 0x1F4 |
| `rt_tickwriter.lua` | what drives that tick, and how fast? | write tap on CPU1 0x80-0x81 | one writer, prom_a 0xF82D0B (vector 0xFFFF44 = INTT1): 487.4/s vs 30.8/s |
| `rt_sfrtap.lua` | is Timer 1 programmed the same? | write tap on CPU1 SFR 0x00-0x2F | first 32 writes byte-identical: T01MOD=0x0D, TREG0/1=0x0F/0x00, TRUN=0xB7 |
| `rt_ivec.lua` | which interrupts actually dispatch on CPU1? | read tap on 0xFFFF00-0xFFFF83 (every dispatch does RDMEML there) | overlay 6 s vs extraction 96 s (16x scale): INTT1 2928 vs 2929 (ratio 1.00), INTTR4 1211 vs 0, INTTC2 1034 vs 15, SWI7 97 vs 2, INT0 20 vs 0 |
| `rt_kill_inttr4.lua` | is the dead 16-bit timer what blanks the panel? | holds CPU1 SFR 0x75 (INTET54) at 0 on the WORKING build | panel still renders in full => **NO**. Control = the same run without the script |
| `rt_link.lua` | which direction of the inter-CPU link is alive? | r/w taps on CPU1 0x7C0000 and CPU2 0x100000 | overlay: cpu2 reads == cpu1 writes exactly (5391/5391). extraction: 10 read of 88 written, 3 sent back, 0 read |
| `rt_vram.lua` | does the firmware ever write UI content to display RAM? | write tap on the lcdc's videoram + link counts | extraction DOES: 5382 non-zero bytes at t=112-128 (= overlay's 6114 at t=4-6) |
| `rt_pix.lua` | is the content in RAM reaching the screen? | videoram non-zero count + screen bytes differing from uniform | extraction t=120: vram 5070 non-zero, screen UNIFORM (230400) => a display-control problem, not a draw problem |
| `rt_lcdcmd.lua` | what display-control commands are sent? | write tap on 0x790000/1; mask 0xFF00 = command lane, 0x00FF = data lane | overlay ends with `DISP ON` param **0x54** (m_fp=0x15, all three layers on); extraction never sends it in 340 s |
| `rt_dispon.lua` | who issues it? | CPU1 CURPC at each DISP command | prom_a 0xF8F7B8, parameter written at 0xF8F7EE; called with C=1 (0x04), C=0 (0x00), C=7 (0x54) |

**Gotcha**: a write tap on a 16-bit space reports the WORD base as `offset` for
both byte lanes; use `mask` (0xFF00 = odd byte) to tell the ports apart. A tap
range must be word-aligned — `install_write_tap(0x75, 0x75, ...)` throws.
