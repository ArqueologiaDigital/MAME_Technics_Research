"""Put back the two blocks the PR deleted from already-merged upstream text.

QUESTION IT ANSWERS
  "Does this PR remove hardware documentation that upstream has already
   accepted?"

  It did, in two places, both casualties of a comment-density reduction pass:

    * the SX-KN7000 section header -- the part-number inventory for IC16..IC21,
      IC203/204/207/208 and IC414, with the three-reason argument for IC21 being
      16 Mbit against the service manual's "32M FLASH" caption, and the pin-level
      reading that settles IC207/IC208 against the block diagram. Deleting it
      left kn7000 as the only one of four ROM sets in the file with no header,
      and left the KN6000 set's "see the note in the KN7000 set above" pointing
      at nothing.

    * nine of the eleven lines of custom_data provenance -- including "The images
      below are therefore not chip dumps", which is the sentence that says what
      those nine CRC-bearing entries actually are, and the reason the region is
      16_BE rather than byte-wide.

  A driver PR that silently drops accepted hardware documentation is a bounce,
  and the second one removes exactly the statement that keeps constructed images
  honestly labelled. Both are restored verbatim from upstream/master.

RUN   python3 restore_upstream_docs.py     (from the PR worktree root)
PASS  prints "ok"; a diff against upstream then shows neither block deleted.
"""


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, '%s MISSING: %r' % (path, old[:90])
        s = s.replace(old, new, 1)
    open(path, 'w').write(s)
    print('rewrote', path)


HEADER = '/***************************************************************************\n\n    SX-KN7000\n\n    IC16, IC17   C3FBNG000016   32 Mbit flash, program + table (see note above)\n    IC18         C3CBND000046   64 Mbit mask ROM, rhythm  (later production)\n    IC20         C3FBMD000050   32 Mbit flash, rhythm      (earlier production,\n                                same site, and half the capacity; the manual\n                                states IC20 is not supplied as a spare part)\n    IC19         C3CBMD000098   64 Mbit picture ROM\n    IC21         C3FBMD000050   16 Mbit custom flash (user data).  The service\n                                manual captions this "32M FLASH", but that is\n                                copied from IC20: the firmware\'s flash device\n                                table (0x485CF9E0) accepts only 16 Mbit parts,\n                                so a 32 Mbit device would fail its autoselect\n                                check.  It also builds a 0x200000 sector map,\n                                and the board decodes a 2 MB window at\n                                0x96800000.  Three independent reasons for\n                                16 Mbit.\n    IC203        C3CBQD000002  128 Mbit mask ROM, wave, main TG bank Y (AWAY)\n    IC204        C3CBQD000001  128 Mbit mask ROM, wave, main TG bank X (AWAX)\n    IC207        C3CBQD000004  128 Mbit mask ROM, wave, sub TG bank Y (BWAY)\n    IC208        C3CBQD000003  128 Mbit mask ROM, wave, sub TG bank X (BWAX)\n\n    The wave devices sit on two independent buses per tone generator, so they\n    are declared as one region per bank rather than concatenated. The block\n    diagram shows IC207 and IC208 the other way round, but the schematic gives\n    BWAY on IC207 and BWAX on IC208 at pin level, the chip-enable groups agree\n    with it, and the part numbers pair as Y = 000002/000004 against\n    X = 000001/000003.\n    IC414        C3FBKD000162    4 Mbit flash, SD card sub-CPU program\n\n***************************************************************************/\n'

PROVENANCE = '\t// The custom flash holds user data, and is populated from a floppy rather than\n\t// programmed at the factory: the firmware inflates the CTMINI payload from an\n\t// "Initial Data Disk" and writes it verbatim to offset 0x20000, which is the top\n\t// 30 of the 64 KiB sectors.  Nothing is written below that, so the boot sectors\n\t// are left erased here.\n\t//\n\t// The images below are therefore not chip dumps.  Each is the exact content the\n\t// firmware places in the device for one published data set, so a part programmed\n\t// from that floppy reads back as declared.  They are offered as a BIOS choice\n\t// because a real instrument holds exactly one of them at a time.  Sectors 19..29\n\t// are byte-identical in all nine, so a little over a third of the region is an\n\t// invariant template rather than per-set data.\n\t// 16_BE: intelfsh preloads a 16-bit part with m_region->as_u16(), a host-native\n\t// read, so a byte-wide region would reach the device halfword-swapped.\n'

edit('src/mame/matsushita/kn7000.cpp', [
("""ROM_START(kn7000)
""", HEADER + """
ROM_START(kn7000)
"""),
("""\t// The custom flash holds user data, and is populated from a floppy rather than
\t// programmed at the factory from the Initial Data Disk.
""", PROVENANCE),
])
print('ok')
