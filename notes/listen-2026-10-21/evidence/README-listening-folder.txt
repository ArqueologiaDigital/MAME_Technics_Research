KN7000 emulator -- listening recordings, 2026-10-21
====================================================

All files are ordinary stereo, 16-bit, 48 kHz WAV. Each one starts 0.5 s before the first note and is normalized
so that the loudest file of its comparison group peaks at -1 dBFS. Within a group, every file gets the SAME gain,
so loudness differences between them are real. Each WAV has an MP3 twin (LAME VBR -q:a 2) for the phone.

Emulator: the published ~/compartilhado/kn7000-emulator/kn7000 (md5 7336efbe: effects DSP at 60 MHz, DRC on),
-bios v13 (program 893), -window. MAME's -wavwrite gives 3 channels: channels 0 and 1 (instrument left and right)
were kept, and channel 2 (the floppy drive) was dropped; it was digital silence in every kept span.
"Computed" means MAME's own output stream (-wavwrite), which doesn't depend on host speed. "Live" means what the
host actually played: the PipeWire sink monitor captured with pw-record while MAME ran at normal (throttled)
speed in a window.

Scripts, logs and the MIDI file: ~/compartilhado/kn7000_mame/notes/listen-2026-10-21/ (README.md there).
Raw recordings: work/ here. stats.txt here is the analysis table, as written by mklisten.py.


GROUP 1 -- a MIDI file on the instrument's own wave ROMs, REVERB on vs off   (gain +5.23 dB on both)
---------------------------------------------------------------------------------------------------
listen.mid: our own file, public domain, played into MIDI IN 1 (-midiin1). In order:
   0.5 s  C major chord on GM 80 square lead, held 3 s and released, then 5 s with nothing else
   8.5 s  J. S. Bach, Prelude in C major BWV 846, bars 1-4, piano
  22.5 s  the same four harmonies on strings, 2 s each, with a drum pattern (crash at the end)
  31.5 s  C major chord on a warm pad, held 4 s, released at 35.5 s
(times are in the files, which start 0.5 s before the first note)

midi-reverb-on.wav   38.50 s  peak -5.96 dBFS  RMS -24.85 dBFS  REVERB as at boot (the LED on, read from the firmware)
midi-reverb-off.wav  38.50 s  peak -1.00 dBFS  RMS -18.63 dBFS  REVERB pressed off at 27 s (the LED off at 28.5 s)

Listen for:
 - D2: with REVERB on, MAME plays only the reverb's return (the wet sound), with no dry sound. It sounds distant
   and about 6-6.5 dB quieter in every section, and it starts 30 ms late (the reverb's pre-delay). With REVERB off
   you hear the plain dry sound. The real instrument plays dry plus wet with REVERB on.
 - The reverb tail: after the square-lead chord is released (3.5 s into the file). REVERB off: it stops dead,
   digital silence within 0.25 s. REVERB on: a tail that dies away over about 2.4 s (-26 to -104 dBFS), then
   silence until the piano.
 - A known emulator fault, not part of the test: from the piano on, the notes never stop. The piano, strings and
   pad ring on after their note-offs and pile up, so the pad's release at 35.5 s changes nothing. The square-lead
   chord was put first for this reason. On the real instrument every note would end.

Not made: the third take with the effects DSP bypassed. It would sound like the REVERB-off take (with REVERB off
the DSP isn't heard at all in MAME; see notes/dsp-noise-2026-10-21), and the MIDI takes had already used the
run budget.


GROUP 2 -- Another World's intro, DSP mode (the game's own samples): computed vs live   (gain +21.22 dB on both)
------------------------------------------------------------------------------------------------------------------
Through the program menu card (technics-roms-disasm kn7000/tools/kn7menu/build/card, AW\KN7APP.BIN 94910f68),
with the owner's loader floppy. Both files come from ONE MAME session.

aw-intro-dsp-computed.wav   60.50 s  peak -1.56 dBFS  RMS -19.15 dBFS  MAME's computed stream, the first 60 s of the intro
aw-intro-dsp-live.wav      101.34 s  peak -1.00 dBFS  RMS -18.89 dBFS  what the host played, same session, same music

Listen for: the slowdown. The emulation ran at a mean 63% of real time during the intro in this window, so the
live file is the same 60 s of music stretched to 101 s, flat (about 8% at 60% speed), and rougher, with a noise floor between
the notes (notes/dsp-noise-2026-10-21: 13-21 dB higher at about 60% speed). The computed file is the clean
reference, which is what the emulation produces when it keeps up.
Raw level: the computed stream peaks at only -22.8 dBFS, hence the +21 dB gain.


GROUP 3 -- Another World's intro, tone-generator mode (the music as MIDI to the instrument's voices)   (gain +6.85 dB)
--------------------------------------------------------------------------------------------------------------------
aw-intro-tg-computed.wav   60.50 s  peak -1.00 dBFS  RMS -15.54 dBFS  computed stream, the first 60 s of the intro

PART SELECT RIGHT 2 was pressed once as the intro started (84.55 s). The game switched to mode 1 at 84.88 s,
before its first sound at about 85.2 s, so the whole file is the tone-generator mode. A press before the intro
is ignored (the game reads the button only once its loop runs).
Listen for: the game's own samples (aw-intro-dsp-computed) against the KN7000's voices playing the same score.
Before normalizing, this mode was 14.4 dB louder than the DSP mode. The two files have their own gains, so
compare timbre, not level. The emulator's hanging MIDI notes (GROUP 1) can affect this mode too.


Levels were checked by analysis before handing over (mklisten.py; stats.txt). Every file has its first note at
0.49-0.50 s and sound in 89-100% of its 1-second windows. None is silent or near silent.
