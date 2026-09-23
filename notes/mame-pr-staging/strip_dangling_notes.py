"""Remove pointers and provenance that only resolve inside the private overlay.

QUESTION IT ANSWERS
  "Can a MAME reviewer follow every reference in this PR?"

  Three classes, all invisible to the compiler:
    * `see notes/<x>.md` -- those files exist only in the kn7000_mame overlay
    * session provenance: dates, run IDs, queue-item numbers, "supersedes the
      earlier guess", star markers
    * firmware addresses cited purely as provenance for a decoded fact

  The FACT each one carries is kept (e.g. "the schematic mislabels this
  designator" is real, useful information); the ceremony around it is dropped.

  Also fixes one duplicated, orphaned, mid-sentence comment block in
  kn_tonegen.cpp that an earlier mechanical trimming pass left behind.

RUN   python3 strip_dangling_notes.py      (from the PR worktree root)
PASS  prints "ok", then the grep for notes/*.md over the PR's files is empty.
"""


def shift(text, n):
    out = []
    for line in text.split('\n'):
        if n < 0:
            out.append(line[min(-n, len(line) - len(line.lstrip('\t'))):])
        else:
            out.append(('\t' * n + line) if line.strip() else line)
    return '\n'.join(out)


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        for d in (0, -1, 1, -2, 2):
            cand = shift(old, d)
            if cand in s:
                s = s.replace(cand, shift(new, d), 1)
                break
        else:
            raise AssertionError('%s MISSING: %r' % (path, old[:80]))
    open(path, 'w').write(s)
    print('rewrote', path)


edit('src/mame/matsushita/kn6000_cpanel.cpp', [
("""    BYTE-IDENTICAL (compared descriptor-for-descriptor across all 30 segments
    and 164 button-bits -- zero differences). See notes/kn6000-panel-matrix.md.
""",
 """    BYTE-IDENTICAL (compared descriptor-for-descriptor across all 30 segments
    and 164 button-bits -- zero differences).
"""),
("""// LCDL D101-D134, LCDC D106, LCDR D301-D320, CPC D323-D345, CPR D351-D377) -- that table is
// reproduced in notes/kn6000-panel-matrix.md. What it does NOT give without further wire
// tracing is the anode-group x SEG coordinate for most of them, i.e. which register/bit the
""",
 """// LCDL D101-D134, LCDC D106, LCDR D301-D320, CPC D323-D345, CPR D351-D377). What it does NOT
// give without further wire tracing is the anode-group x SEG coordinate for most of them,
// i.e. which register/bit the
"""),
])

edit('src/mame/matsushita/kn6000_cpanel.h', [
("""    matrices are BYTE-IDENTICAL (30 descriptor segments, 164 button-bits, zero
    differing entries -- see notes/kn6000-panel-matrix.md), so a single class
    serves both models.
""",
 """    matrices are BYTE-IDENTICAL (30 descriptor segments, 164 button-bits, zero
    differing entries), so a single class serves both models.
"""),
("""
    Matrix: notes/kn6000-panel-matrix.md

***************************************************************************/
""",
 """
***************************************************************************/
"""),
])

edit('src/mame/matsushita/kn7000_cpanel.cpp', [
("""
    Protocol: notes/panel-serial-protocol.md

***************************************************************************/
""",
 """
***************************************************************************/
"""),
("""// pure identity. Button-to-column assignments come from each button's firmware event code + arg
// (notes/panel-button-map.md). LEDs are driven independently on the same normSeg keys (tools/gen_lay.py).
""",
 """// pure identity. Button-to-column assignments come from each button's firmware event code + arg.
// LEDs are driven independently on the same normSeg keys.
"""),
("""// Reverse-normalization (the inverse of firmware table 0x486135A0):
""",
 """// Reverse-normalization (the inverse of the firmware's normalization table):
"""),
])

edit('src/mame/matsushita/kn7000_cpanel.h', [
("""
    Protocol: notes/panel-serial-protocol.md
    Matrix:   notes/panel-descriptor-map.md

***************************************************************************/
""",
 """
***************************************************************************/
"""),
])

edit('src/mame/matsushita/kn_cpanel.cpp', [
("""    See kn_cpanel.h for the rationale of the split, and
    notes/panel-serial-protocol.md for the protocol itself.
""",
 """    See kn_cpanel.h for the rationale of the split.
"""),
("""//   pos 0 sync, 1 sync, 2 PAYLOAD1, 3 sync, 4 PAYLOAD2, 5 sync, 6 sync
// (KN7000 TX sites: sender 0x484AC5E9; states 1..6 at 0x484AC7FA / 0x484AC8D3 /
// 0x484AC977 / 0x484AC9FF / 0x484ACA96 / 0x484ACAEA). Parse by position.
""",
 """//   pos 0 sync, 1 sync, 2 PAYLOAD1, 3 sync, 4 PAYLOAD2, 5 sync, 6 sync
// Parse by position.
"""),
])

edit('src/mame/matsushita/kn_cpanel.h', [
("""
    Protocol: notes/panel-serial-protocol.md
    Per-model matrices: notes/panel-descriptor-map.md (KN7000),
                        notes/kn6000-panel-matrix.md (KN6000/KN6500)

***************************************************************************/
""",
 """
***************************************************************************/
"""),
("""	// The shared front-panel analog controls the panel sub-CPUs also scan stay in the
""",
 """	// The analog controls the panel sub-CPUs scan live in the driver's ioports;
	// the device reads them through these tags.
"""),
])

edit('src/mame/matsushita/kn_tonegen.cpp', [
("""    See kn_tonegen.h for the firmware evidence behind this split, and
    notes/kn6000-tonegen-spec.md for the KN7000-vs-KN6000 comparison.
""",
 """    See kn_tonegen.h for the firmware evidence behind this split.
"""),
# the duplicated, orphaned, mid-sentence block an earlier trimming pass left
("""	save_item(NAME(m_gain_save));
}

	// Per-voice amplitude envelope DRIVEN BY THE FIRMWARE'S 7-param EG (r0/r1/r2 rate|level
	// pairs, resolved at note-on -- see tg_write and notes/tg-envelope-sweep-results.md).
	// Full stage chain: linear ATTACK to PEAK (r0), exponential DCY1 toward SUS1 (r1),
	// exponential DCY2 toward SUS2 (r2, the long-tail second stage), then exponential
	// RELEASE to silence when the gate drops (r3=0x8000 / managed r0 burst / steal mute).
	// A piano (SUS1=SUS2=0) genuinely decays to silence in two stages; an organ


	// Per-voice amplitude envelope DRIVEN BY THE FIRMWARE'S 7-param EG (r0/r1/r2 rate|level
	// pairs, resolved at note-on -- see tg_write and notes/tg-envelope-sweep-results.md).
	// Full stage chain: linear ATTACK to PEAK (r0), exponential DCY1 toward SUS1 (r1),
	// exponential DCY2 toward SUS2 (r2, the long-tail second stage), then exponential
	// RELEASE to silence when the gate drops (r3=0x8000 / managed r0 burst / steal mute).
	// A piano (SUS1=SUS2=0) genuinely decays to silence in two stages; an organ

""",
 """	save_item(NAME(m_gain_save));
}

"""),
])

edit('src/mame/matsushita/kn_tonegen.h', [
("""    THE DECISIVE EVIDENCE (static RE, 2026-07-20; see
    notes/kn6000-tonegen-spec.md for the full comparison table):
""",
 """    THE DECISIVE EVIDENCE:
"""),
("""	// Envelope stages (see notes/tg-envelope-sweep-results.md). The firmware's 7-param
	// amplitude EG: ATTACK to PEAK (r0), DCY1 toward SUS1 (r1), DCY2 toward SUS2 (r2),
""",
 """	// The firmware's 7-param amplitude EG:
	// ATTACK to PEAK (r0), DCY1 toward SUS1 (r1), DCY2 toward SUS2 (r2),
"""),
("""	// Per-voice amplitude envelope DRIVEN BY THE FIRMWARE'S 7-param EG (r0/r1/r2 rate|level
	// pairs, resolved at note-on -- see tg_write and notes/tg-envelope-sweep-results.md).
	virtual void sound_stream_update(sound_stream &stream) override;
""",
 """	// Per-voice amplitude envelope driven by the firmware's 7-param EG (r0/r1/r2
	// rate|level pairs, resolved at note-on -- see tg_write).
	virtual void sound_stream_update(sound_stream &stream) override;
"""),
("""	// Per-voice AMPLITUDE ENVELOPE, driven by the firmware's own 7-param EG. Decoded via
	// the AMPLITUDE EDIT -> ENVELOPE screen sweep (notes/tg-envelope-sweep-results.md):
""",
 """	// Per-voice AMPLITUDE ENVELOPE, driven by the firmware's own 7-param EG:
"""),
])

edit('src/mame/matsushita/kn7000_tonegen.cpp', [
("""			// Voice life-cycle class (workflow RE + 11-family sweep, 2026-07-11):
			//  - GATE_FOLLOW: aux bit15 (brass/sax/organ) -- no firmware key-up write; the
//    TG (which hosts the key-bed FIFO) gates them off itself on key release.
""",
 """			// Voice life-cycle class:
			//  - GATE_FOLLOW: aux bit15 (brass/sax/organ) -- no firmware key-up write; the
			//    TG, which hosts the key-bed FIFO, gates them off itself on key release.
"""),
("""			// Resolve this voice's amplitude envelope from the firmware's 7-param EG.
			// DECODED 2026-07-20 via the AMPLITUDE EDIT -> ENVELOPE screen sweep
""",
 """			// Resolve this voice's amplitude envelope from the firmware's 7-param EG.
"""),
("""		// ★ DECODED 2026-07-20 (queue item B2; static RE of the lib setter family
		// 0x4C037D0F..0x4C037F10 + live setter/arg traps -- see notes/per-part-depth-bank.md):
""",
 """		// Decoded from the library's setter family and its live argument traffic:
"""),
("""			m_gain_depth = float(data & 0x7F) / 127.0f;   // TOTAL DEPTH (live-verified: 0x8500|depth)
""",
 """			m_gain_depth = float(data & 0x7F) / 127.0f;   // TOTAL DEPTH (0x8500|depth)
"""),
("""			m_gain_chorus = float(data & 0x7F) / 127.0f;  // CHORUS send (0x8198 low7 = per-part depth;
			                                              // 0x0B00 off -> 0; routes to CHORUS unit 9 --
			                                              // live-captured unit map, dsp-unit-roles-live-capture.md)
""",
 """			m_gain_chorus = float(data & 0x7F) / 127.0f;  // CHORUS send (0x8198 low7 = per-part depth;
			                                              // 0x0B00 off -> 0; routes to CHORUS unit 9)
"""),
("""			m_gain_dsp = float(data & 0x7F) / 127.0f;     // SOUND DSP send (0x8098 low7 = per-part depth;
			                                              // routes to the per-part insert pool u2..u6;
			                                              // RIGHT1 = unit 2 -- live-captured unit map)
""",
 """			m_gain_dsp = float(data & 0x7F) / 127.0f;     // SOUND DSP send (0x8098 low7 = per-part depth;
			                                              // routes to the per-part insert pool u2..u6,
			                                              // RIGHT1 being unit 2)
"""),
("""		// bus). Live-captured per-effect toggle map (2026-07-12, notes/effect-return-routing.md):
""",
 """		// bus), from the per-effect toggle map:
"""),
])

edit('src/devices/cpu/sharc/sharc.cpp', [
("""// 21065L IOP register bank -- stubbed for F.1. The base 2106x core fatalerrors on the
// 21065L-specific SPORT/SDRAM/DMA offsets the effect programs touch (0x28-0x3C, 0x53-0x7B,
// 0xE0-0xFC per notes/sharc-lle-assessment.md); returning 0 / accepting writes lets the
// program run without crashing. Real SPORT/SDRAM/DMA modelling is F.3.
""",
 """// 21065L IOP register bank -- stubbed. The base 2106x core fatalerrors on the
// 21065L-specific SPORT/SDRAM/DMA offsets (0x28-0x3C, 0x53-0x7B, 0xE0-0xFC);
// returning 0 and accepting writes lets a program run without crashing. Real
// SPORT/SDRAM/DMA modelling is still to do.
"""),
])

edit('src/devices/cpu/sharc/sharc.h', [
("""// on-chip SRAM and a different I/O-register personality. That personality is derived from
// the recovered firmware program (see the KN7000 driver / notes/sharc-lle-assessment.md):
// program code at PM 0x8000-0x8Dxx, data at DM 0x9800/0x9C40/0xC000/0xC302, external SDRAM
""",
 """// on-chip SRAM and a different I/O-register personality. That personality is derived from
// the program the KN7000 uploads to it: code at PM 0x8000-0x8Dxx, data at DM
// 0x9800/0x9C40/0xC000/0xC302, external SDRAM
"""),
])

edit('src/devices/cpu/sharc/sharcdrc.cpp', [
("""				// KN7000 effects kernel's HOT PATH: ~66M interpreter fallbacks per reverb-run before
				// this (measured 2026-07-12; the prior native MAC covered the MULTI-function forms,
				// but the kernel actually uses the SINGLE-function multiplier). Mirrors the
				// interpreter's general fixed multiplier (sharcops.hxx). Unsigned/mixed-sign and the
				// RND (0x18-0x1F) forms still fall back (rare / unused by the kernel); the SAT
				// family (0x00-0x0F) is native below (rec12 GATE REVERB uses Rn = SAT MRF (SF)
				// at PM 0x8438). Op byte:
""",
 """				// Technics KN7000 effects kernel's hot path: without these it took ~66M
				// interpreter fallbacks per reverb run, since the existing native MAC covered
				// only the MULTI-function forms. Mirrors the interpreter's general fixed
				// multiplier (sharcops.hxx). Unsigned/mixed-sign and the RND (0x18-0x1F) forms
				// still fall back; the SAT family (0x00-0x0F) is native below. Op byte:
"""),
])
print('ok')
