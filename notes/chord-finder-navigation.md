> Phase C / first-cut-audio recon (2026-07-09). Companion to sound-subsystem-plan.md.

## UPDATE 2026-07-10 (b) — PITCH INVESTIGATED: chord finder plays GARBAGE voicing (not a decode bug)

With the post-boot gate (CONFIG bit2) the chord finder is playable and the "ear" (MUTE
PART 15 ON = SEG07 0x10) fires a chord. Felipe: "fix the pitch." Full RE done; conclusion:
the tonegen decode is CORRECT and the wrong pitch is the FIRMWARE computing a bad voicing.

Evidence (temp TGCAP/PITCHPC instrumentation in tg_write/io_w, since reverted):
- **Keybed pitch decode VERIFIED exact** over an octave: C4=0xC838, E4=0xD838, G4=0xE438,
  C5=0xF838 -- all exactly `0xC838 + (note-60)*0x400`, integer notes. class 0x2401 is the
  pitch; 0x2801/0x2C04 are sample-zone/filter params (0x2801 shifts C4->E4 at a sample
  split, NOT octave), 0x3000 is a constant patch param on the keybed. So decode is right.
- **Keybed and chord finder write pitch from the SAME routine**: maincpu PC **0x4C036FBA**
  (in the self-loaded 0x4C lib ROM). The pitch VALUE is computed upstream and passed in.
- **Chord finder C-Maj ear** -> 0x2401 = 0x1374/0x3304/0x37B0 = notes 14.8/22.7/23.9
  (non-integer, sub-bass; pitch-classes ~D/A#/B, NOT C/E/G). Two voices per note (dual
  layer), same 0x2401.
- **Felipe's "already playing" hypothesis TESTED & RULED OUT**: 2nd ear press replays the
  SAME chord on fresh voices (not ignored). Note-offs ARE present: each voice does
  `0x0001=0xC000` (mute) then the `0x2401` pitch write -- proper note-off->note-on.
- **DECISIVE root-change test**: changed ROOT C->E (SEG04 0x40 = ROOT-up, auto-repeats;
  screenshot-confirmed). E-Maj played 0x0690/0x1290/0x37B0. Both are MAJOR triads so a sane
  voicing would give IDENTICAL intervals; instead C-Maj={7.9,1.2} vs E-Maj={3.0,9.3}
  semitones -- totally different, non-musical, and raising the root made notes go DOWN. One
  value (0x37B0) identical in both, like a stuck slot. => GARBAGE.

CONCLUSION: the APC chord-voicing computation reads bad/uninitialized data in this boot
state, so it emits non-musical 0x2401 values. NOT fixable in the tonegen (decode is right),
NOT "already playing", NOT a missing note-off. It's the accompaniment/voicing data+state
gap (same family as the "8 Beat 1" style-data issue, kn7000-ast-codec-zlib). NEXT to make
it correct: trace the pitch source above 0x4C036FBA (which RAM/table the voicing reads) and
fix that state/data -- do NOT fake a transpose (would misrepresent the device).

## UPDATE 2026-07-10 (c) — DEMO Overture: enters + intro note IN TUNE, but playback STALLS

Per Felipe: DEMO (SEG09 0x40, held; the code comment saying SEG06 is stale) -> DEMONSTRATION
menu -> LCD LEFT 1 (SEG03 0x08) = OVERTURE -> "Welcome to SX-KN7000" splash (screenshot).
With the gate open it plays ONE intro note = a clean, in-tune **F2 (88.6 Hz)** -- proving
the sound engine renders SEQUENCED note data at CORRECT pitch (keybed AND demo agree). BUT
playback then STALLS: over 90 s the splash LCD is byte-identical (t=20/50/85) and there is
NO audio after ~t=24. The maincpu keeps running VARIED code (no single spin-PC), so it's a
higher-level playback state machine waiting on a condition we don't satisfy (timer/DMA/
decode/sequencer tick), not a trivial missing-IRQ spin. **Pre-existing: the stall happens
WITHOUT the gate-poke too**, so it's independent of the gate and of the pitch issue. Open
thread: why the demo/sequencer doesn't advance past the first event.

## UPDATE 2026-07-10 — navigation CONFIRMED by screenshot; blocked by the same gate/SD-menu conflict

Attempted per Felipe's request. Findings (visible-video runs, screenshots):
- **The CHORD FINDER screen IS reachable and navigable, with the TG gate OFF**:
  HOME -> APC MODE (`SEG03 0x02`) -> **APC SELECT** screen -> CHORD FINDER soft-key
  (`SEG0F 0x40`, the LCD-RIGHT-5 position, labelled "CHORD FINDER" on APC SELECT) ->
  **CHORD FINDER** screen. Confirmed by screenshot: ROOT:C TYPE:Maj, a chord-type grid,
  ROOT/TYPE/INVERSION soft-keys, a mini-keyboard showing the chord, and an EAR icon at
  the bottom-right (LCD-RIGHT-5 = `SEG0F 0x40`). So step-2's SEG0F 0x40 guess was RIGHT;
  the "APC SELECT hash unchanged" earlier was the sparse LCD sample missing it.
- **The gate/SD-menu conflict blocks it, same as the keybed**: sound needs the TG gate ON
  (CONFIG bit1), but the gate ON lands boot on the SD MENU (screenshot), and APC MODE does
  NOT leave the SD menu (shot before==after). With the gate OFF you can navigate to the
  chord finder, but pressing the ear (`SEG0F 0x40` on the CF screen) produced NO TG voice
  writes and NO sound -- the voice path is gated off. So the chord finder does NOT bypass
  the gate issue.
- The old probe's "SEG10 0x02 fired" was a FALSE POSITIVE: it wrote a TG GROUP-1 register
  (reg 0x0400), not a note PITCH (group 9), and produced no audio. Ignore that candidate.
- Whether the ear fires the note EVENT (MainSoundAdd) under the gate is inconclusive here
  (debug-core printf output routing with -debugger none didn't surface). But it doesn't
  matter for audibility: the gate suppresses the voices either way.

CONCLUSION: the chord finder is a confirmed, navigable UI path, but it is subject to the
SAME recurring blocker as everything else -- the TG gate opens the SD menu (memory
kn7000-sd-strap-gate). Resolving that boot state is the real unlock (for the keybed, the
chord finder, AND effect selection / reverb). That is the recommended next target.

--- (original 2026-07-09 recon below) ---

# CHORD FINDER "ear" navigation + note-on detection plan

Scripts saved at:
- `/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/c6cf97f4-b4f1-4ba1-adc0-85474706b167/scratchpad/chord_finder_probe.lua`
- `/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/c6cf97f4-b4f1-4ba1-adc0-85474706b167/scratchpad/chord_finder_bpcount.lua`

All APIs/addresses verified against the driver source, `kn7000.sym`, and the MAME 0.288 Lua bindings in `/home/fsanches/compartilhado/kn7000_mame_build/`.

## 1. Exact ioport SEG / mask per step (kn7000.cpp INPUT_PORTS_START)

| Step | Button | ioport/mask | PORT_NAME (source) | Confidence |
|---|---|---|---|---|
| 1 HOME→APC SELECT | APC MODE | `SEG03` `0x02` | `"APC / CHORD FINDER"` (kn7000.cpp:1119) | High — dedicated single-bit button whose name references CHORD FINDER; matches manual p57 step1 (sound-gui-inventory.md:40) |
| 2 APC SELECT→CHORD FINDER | CHORD FINDER soft-key | `SEG0F` `0x40` | LCD RIGHT 5 soft-key (kn7000.cpp:1244; the source PORT_NAME's "ACCOMP2 part ON" is a **retracted** part reading — this is a context-dependent soft-key, not a part selector) | MEDIUM — see caveat |
| 3 CHORD FINDER | ear soft-key | UNKNOWN — sweep (primary guess `SEG11` `0x02`) | balance-button row | LOW — not established |

CAVEAT step2: soft-keys are screen-contextual (the LCD RIGHT 5 soft-key `SEG0F 0x40` is CHORD FINDER on APC SELECT, sound-gui-inventory.md:46; its HOME "ACCOMP2 part ON" label is a **retracted** part reading — not a part selector). The driver binds LCD-RIGHT 1–5 to `SEG0F 0x04..0x40`, but panel-button-map.md:87-105 records only the LCD-LEFT column (SEG03 b3–b7) as user-confirmed; the LCD-RIGHT column is an unverified best-guess (board-decode for that CPR group un-pinned, panel-dispatch-table.md). If SEG0F 0x40 does not open CHORD FINDER, sweep SEG0F 0x04/0x08/0x10/0x20/0x40; the LCD-hash checkpoint shows which one changes the screen.

CAVEAT step3 (honest gap): the ear button's exact ioport bit is NOT established. The bottom balance row maps to firmware events 0x2008/0x2009, but those bits are only in the INACTIVE dispatch table 0x48614978 (panel-descriptor-map.md:136-167) whereas the KN7000 runs the flag==1 variant 0x486149FC. On the CHORD FINDER screen these physical buttons are re-interpreted positionally by the screen's Iv*Proc as ROOT/TYPE/INVERSION/ear. Candidate bits to sweep (rightmost first): SEG11 0x02, SEG0E 0x01, SEG10 0x02, SEG0E 0x02, SEG0F 0x02, SEG0D 0x02. The sweep is self-validating — the TG write-tap fires only for the button that sounds the chord (~3 non-0xFC voice writes = C-E-G), so we identify the ear empirically rather than needing the bit in advance.

## 2. Navigation + detection script (NO -debug) — chord_finder_probe.lua
Run from /home/fsanches/compartilhado/kn7000_mame_build/:
`./kn7000 kn7000 -rompath roms -video none -seconds_to_run 32 -autoboot_delay 0 -autoboot_script /ABS/PATH/chord_finder_probe.lua`
Hygiene first: `pkill -9 -f 'kn7000 kn7000'; sudo -n /usr/local/sbin/drop-caches`. Output to stdout (emu.print_info; add -log for error.log) and /home/fsanches/compartilhado/kn7000_run/chord_finder_probe.log.

The script: (1) hashes the LCD framebuffer at 0x9CE00000 (RGB565 640x240, kn7000.cpp:1410) at HOME, after APC MODE, after CHORD FINDER to prove each press changed the screen; (2) saves a savestate 'cf' at the CHORD FINDER screen; (3) sweeps the 6 ear candidates, machine:load('cf') between each; (4) a TG write-tap on 0x98040000-3 (main IC201) and 0x98050000-3 (sub IC205) reports non-0xFC voice writes with CURPC. Verified facts used: emu.add_machine_frame_notifier (luaengine.cpp:884; machine:add_notifier does not exist); presses held 30 frames (>=14 needed for 250Hz panel scan, kn7000.cpp:944); setbtn matches fields by .mask; MN10300 program space is 32-bit LE byte-addressed (mn10300.cpp:60) so TG ADDRESS latch = low16 (base+0, mask&0x0000FFFF), DATA = high16 (base+2, mask&0xFFFF0000); idle refresh reg-addr 0xFC0x filtered (tone-generator.md:34); machine:save/load = schedule_save/load (luaengine.cpp:1423). The winning ear candidate prints "<<< NOTE-ON FIRED". Full script inline in the chat deliverable.

## 3. Fallback event-queue injection — assessment
MILK queue at 0x5000757C, 0x38-byte entries; post via MainPostEvent 0x48429808; START/STOP = event 0x2020 (gui-toolkit-event-system.md, panel-dispatch-table.md). A stable injectable code for the ear button is NOT known (not found): the ear is a soft-key whose meaning is assigned by the focused CHORD FINDER Iv*Proc, not a fixed panel event; the physical balance buttons post generic Balance/Ctrl 0x2008/0x2009 + an arg, and which arg is the ear is exactly the unverified mapping (from the inactive table). Raw queue injection is therefore no more reliable than pressing the ioport bit and additionally requires reproducing the queue-entry layout + MainPostEvent call. Recommendation: do NOT use queue injection for the ear; the ioport sweep in §2 is strictly better and TG-tap-validated. (Dedicated events like START/STOP=0x2020 CAN be injected; the ear cannot. No Lua-drivable event-post path exists today — driver-side mailbox gap, sound-probing-infrastructure.md §5.3.)

## 4. Instrumentation — did a note-on fire?
(a) TG write-tap (PRIMARY, no -debug): install_write_tap(start,end,name,cb) with cb(offset,data,mem_mask) verified at luaengine_mem.cpp:283,678. Reconstruct (reg-addr,data) from the 32-bit LE lanes, filter 0xFC0x idle, log non-0xFC writes with CURPC (cpu.state["CURPC"].value, mn10300.cpp:116). Any non-0xFC voice write during an ear press = yes. Included in the §2 script.

(b) Function-call counters (needs debug core, NO UI window): taps miss opcode fetches, so count entries via MAME breakpoints — the core calls debugger_instruction_hook every instruction (mn10300.cpp:289). cpu.debug is non-nil only with the debug core (luaengine.cpp:1581); -debugger none keeps the core and auto-continues (none.cpp:48). Verified: device_debug:bpset(addr,cond,action) (luaengine_debug.cpp:415), debugger:command/execution_state/consolelog (372,378,373). chord_finder_bpcount.lua sets bpset on 0x4848C043 MainSoundAdd (sym:515)->temp0, 0x484948BC MainSeqRun (sym:580)->temp1, 0x4844812D note-handler->temp2, each with action "tempN=tempN+1; g" (auto-resume), zeroes temps before the ear press, and prints RESULT via debugger:command printf. Run: `./kn7000 kn7000 -rompath roms -video none -debug -debugger none -seconds_to_run 26 -autoboot_delay 0 -autoboot_script /ABS/PATH/chord_finder_bpcount.lua`. Note 0x4844812D is unnamed in kn7000.sym (cited sound-probing-infrastructure.md §1.3) and a zero there is expected if the ear uses the APC/sequencer path not the key-bed FIFO. Alternative if -debugger none is unavailable: -debug -debugscript with the same three bpset lines. Full script inline in the chat deliverable.

Interpretation: MSA>0 + voice writes = note-on fully fires (capture writes to identify the undocumented part/voice, sound-gui-inventory.md:56); MSA>0 no writes = allocator runs but synthesis gated downstream; MSA=0 SEQ>0 = routes through sequencer; all zero = wrong bit, redo the §2 sweep/LCD-hash check.