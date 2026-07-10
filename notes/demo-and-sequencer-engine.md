# The demo + sequencer engine (reference RE, 2026-07-10)

Harvested from the 4-way root-cause investigation (adversarially verified) that led to
the tempo-timer fix (commit 60d5392). The demo NOW PLAYS; this documents how the
subsystem works, as reference for sequencer/style/SMF work. Companion:
sequenced-playback-and-style-data-rootcause.md.

## Demo data (all in the dumped program ROM -- nothing missing)

- **10 zlib song-SETUP blobs** @ 0x4879654C..0x48797E14 (file 0x39654C+): each
  inflates to a 0x8E0 "ZZZZ...JK" block (track table, KIT1, initial programs) into
  per-song RAM slots 0x501A5800 + n*0x8E0.
- **10 zlib song SEQUENCE blobs** @ 0x4879811C..0x487AC1E8: inflate (up to 0x9800
  bytes) into RAM 0x5003D36C; play pointer at 0x5003D34C. FORMAT: 256-byte-per-measure
  pages, byte0=0x80 flag, byte1=measure#, events = delta + running-status MIDI
  (90 nn vv dur..., B0/C0/E0), 0x81 = tick/rest marker.
- **10 zlib sound/registration blobs** @ 0x487AE1E8..0x487B0750 (" Soloist Sounds ",
  per-part configs).
- Per-song pointer tables: ROM 0x487B1788, boot .data copy (0x4841005C: ROM
  0x487B0B78 -> RAM 0x50000010, 0x7F34 bytes) lands them at RAM
  **0x50000C20/0x50000C50/0x50000C80** (setup/sequence/sounds x 12 entries).
- Slideshow: table of 10 **ACT scripts** @ 0x4867F75C (plain text "SSW-ACT-V01
  <ACTION><ACT NO=n><SHOW OBJ=\"fdemo_a1\">..."); OVERTURE=0x4867C618 shows
  fdemo_a1..a32 (JPEGs via the table-ROM directory @0x48000024+). Slideshow pacing =
  song position (hence the pre-fix frozen splash).
- DEMO menu: TtDemoMenu 10-entry widget records @ 0x4867BC28.

## Start chain

DEMO menu -> AcDemoSelectProc posts MT_DemoSongStart (0x01C30001, song index) ->
demo screen proc 0x4854DC8B -> 0x4854641B(song#) arms the state machine (bytes
0x5008198A-0x50081990, countdown 0x5008198C=0x14): at 7 the song loads (0x48457355
inflates the three blobs; slideshow starts); at 2 engine command **0x8002** is posted
(0x484582B9 -> kernel mailbox 0x4C014A56); at 1 a 5-tick fuse (0x5008198E=0x85) arms;
then 0x485465C4 calls the **transport start** (0x48445DA8 / 0x48445F59, lane-set 4).
Transport start REFUSES SILENTLY if clock-source byte **0x50149662 != 0** (external/
MIDI-clock mode) -- a gate to remember when sequenced playback "does nothing".

## The clock chain (two timers, two roles)

- **1 kHz engine feed** (TM4, GxICR 0x34000118 = the driver's sys_tick): library ISR
  0x4C02BB05 -> every 2nd IRQ calls divider 0x484D7936 (6-phase/8-subphase) -> sets
  engine service flags 0x50151C00 (bit 0x80 every 48 base ticks) -> the library
  engine-task loop (0x4C02BBE8..0x4C02BE2F) runs the demo state machine tick
  (0x484574AF -> 0x485464DB), pumps event queues (0x4C014E46+, dispatch 0x4C01B6DF).
- **96-PPQN event pacing** (TM5 = driver tmr7, GxICR 0x3400011C): ISR 0x48447084
  advances the FIVE clock-lane structs 0x50149666/0x5014967A/0x50149670/0x50149684/
  0x5014968E each tick, guarded by: stop flag 0x50149656==0; RUN bit15 of 0x5014966E
  (song lanes); count-in (0x50149698 bit14) additionally needs sync-status
  0x50149696 bits 15&7. PPQN phase (mod 96) at 0x50149664; master tick count
  0x50151BFC. Due events popped by 0x48447FD2/0x48453A99 -> 0x4C01B6DF -> TG.
- Tempo programming: reload = *(0x5003A540)=1,250,000 / BPM -> movhu (0x34001092);
  clamp 40..300 BPM (0x4844786E/0x48447888). Timer start 0x484477D3 is reached via
  0x4844785F, which has NO static caller (pointer-dispatched from the engine command
  interpreter -- e.g. the 0x8002 path).
- START/STOP panel family 0x2020/0x2023/0x2041 -> handler 0x484452EE (writes
  0x50149656, programs tempo, transport control). Demo medley auto-start posts
  0x00702020 from 0x4854657F.

## The pre-fix stall, resolved

The agent's open question "which gate holds" was answered empirically by the fix:
modeling TM5 alone made both the demo AND rhythm accompaniment play -- so the tempo
interrupt chain was the single root cause; the other gates (0x50149662 clock source,
RUN via the 0x8002 command, count-in sync) all pass normally. The single pre-fix F2
was the tick-0 event batch delivered synchronously at transport start.

Stall-PC classification (for future "is it alive?" triage): 0x4854D189 = GPIO
bit-bang settle loop (shadow 0x50005214 -> port 0x98060000); 0x484294C3 = MILK event
dispatch core (UI pump alive); 0x484B2873 = MIDI SIO delay helper; 0x4C03B707/
0x4C03B7E8 = RTOS context switch; 0x4C03D726 = kernel critical-section/semaphore
entry 0x4C03D6BC; 0x4C03DEF6 = interrupt epilogue. All idle/alive loops.

## Still-open threads (minor)

- Who exactly emits the demo's first F2 (first bass event 90 35/37.. vs count-in
  metronome) -- cosmetic curiosity now that playback works.
- 0x50149696 sync-status writers (0x48445959-0x484459A6): which subsystem feeds
  bits 15&7 (metronome lane? panel sync-start?) -- relevant only for count-in mode.
- The engine mailbox 0x8002 handler's exact dispatch inside 0x4C01B6DF/0x4C0216A8
  (sets RUN bit15) -- works, untraced.
- MIDI-clock slave mode (0x50149662 != 0): untested; when MIDI-in work resumes,
  external clock should pace the same lanes.
