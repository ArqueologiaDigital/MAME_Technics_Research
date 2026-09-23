"""Rewrite the comments that trimming left mid-sentence, as short complete ones."""
FIX = {
    'src/mame/matsushita/kn7000.cpp': [
        ('\t// note events from the key bed (KN5000-shared "keyboard input"; 16-bit word,\n',
         '\t// Note events from the key bed: low byte = key code, high byte = velocity,\n'
         '\t// 0xFFFF = empty. Make/break is bit 7 of the key byte, not the velocity.\n'),
        ("\t// firmware's service-mode WAVE ROM test (checksum core 0x484839A1) reads the\n",
         "\t// The service-mode WAVE ROM test reads the wave ROMs through this port: bank\n"
         "\t// at base+6, word address at base+8, sample word back at base+A.\n"),
        ('\t// The CPU host-boots the SHARC through an index register at 0x98000000 and a\n',
         '\t// The CPU host-boots the SHARC through an index register at 0x98000000 and a\n'
         '\t// data register at 0x9C000000.\n'),
        ('\t\t// card-detect line (cover closed + card in = accessible; cover open => the\n',
         '\t\t// card-detect line: closed with a card in means accessible, open means absent.\n'),
        ('\t// The SD card is reached over SIO ch2. Delivery model (RE 2026-07-08): the\n',
         '\t// The SD card is reached over SIO channel 2.\n'),
        ('\t\t// 0x50000000 work RAM (the same one-bit window pair as 0x4C/0x8C and 0x44/0x84). The\n',
         '\t\t// 0x50000000 work RAM, the same one-bit window pair as 0x4C/0x8C and 0x44/0x84.\n'),
        ('\t// (TMnBC at 0x340010a4+, beyond the TM4/TM5 pair the core models) as\n',
         '\t// (TMnBC at 0x340010a4+, beyond the TM4/TM5 pair the core models) as plain RAM.\n'),
        ('\t\t// the KN5000 firmware calls "keyboard input" (KN5000 0x110000: read voice events,\n',
         '\t\t// what the KN5000 firmware calls "keyboard input".\n'),
        ('\t// F.2 host-boot: decode the upload protocol and write the streamed program/data into\n',
         '\t// Host boot: decode the upload protocol and stream the program into the DSP.\n'),
        ('// The INTC register model lives in the MN10300 core (mn10300.cpp intc_*). The\n',
         '// The INTC register model lives in the MN10300 core; only board policy is here.\n'),
        ('\t// Rear-panel MIDI IN / BASS PEDAL selector switch (SW701 on the JACK board). The\n',
         '\t// Rear-panel MIDI IN / BASS PEDAL selector switch, SW701 on the JACK board.\n'),
        ("\t// controller scans. The firmware's software compositor blends the UI plane and the\n",
         "\t// controller scans; the firmware composites the planes in software.\n"),
        ('\t\t// 1 = no card / 0 = card present (raw read 0x4854bce0: btst bit4). The\n',
         '\t\t// 1 = no card, 0 = card present.\n'),
        ('\t// On-chip SIO routing (the register model lives in the core, as does the\n',
         '\t// On-chip SIO routing; the register model itself lives in the CPU core.\n'),
        ('\t// programmed at the factory: the firmware inflates the CTMINI payload from an\n',
         '\t// programmed at the factory from the Initial Data Disk.\n'),
    ],
    'src/mame/matsushita/kn_tonegen.h': [
        ("\t// event FIFO (the firmware reads it at 0x98050004 = the TG's own +4 register), so the\n",
         "\t// event FIFO, which the firmware reads at the TG's own +4 register.\n"),
        ('\t// its DSP bridge while the sound thread writes them), and save_item() cannot take an\n',
         '\t// its bridge while the sound thread writes them, so they are saved by hand.\n'),
    ],
    'src/mame/matsushita/kn7000_tonegen.cpp': [
        ('\t\t// A REAL note-on always programs the 7-halfword amplitude EG (r4..rA) for the\n',
         '\t\t// A real note-on always programs the 7-halfword amplitude EG first, so require\n'
         '\t\t// a programmed EG before keying a voice on.\n'),
        ("\t\t\t// the firmware rewrites regs 0,1,4,5,8,9 of the note's ODD companion block with\n",
         "\t\t\t// the firmware rewrites regs 0,1,4,5,8,9 of the note's odd companion block.\n"),
    ],
    'src/mame/matsushita/kn7000_tonegen.h': [
        ('\t// TGs) is routed here from io_w. Once the TG-enable gate is open (see the\n',
         '\t// TGs) is routed here from io_w, once the TG-enable gate is open.\n'),
    ],
    'src/mame/matsushita/kn6000_tonegen.cpp': [
        ("\t\t// KN7000's class 0x1C02 gate-follow marker) is NOT yet identified, and the\n",
         "\t\t// KN7000's class 0x1C02 gate-follow marker) is not yet identified.\n"),
        ('\t\t\t// rewrites the first two registers of each envelope bank ({4,5,8,9,C,D}) with a\n',
         '\t\t\t// rewrites the first two registers of each envelope bank ({4,5,8,9,C,D}).\n'),
    ],
}

missed = 0
for path, pairs in FIX.items():
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        if old not in s:
            print('  MISS %s: %r' % (path, old.strip()[:66]))
            missed += 1
            continue
        s = s.replace(old, new, 1)
    open(path, 'w').write(s)
    print('fixed', path)
print('missed:', missed)
