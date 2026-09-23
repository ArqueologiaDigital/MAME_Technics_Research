"""Last reviewer-facing pass over the PR: plan labels, stale text, crammed lines.

QUESTION IT ANSWERS
  "Is there anything left that only makes sense to the person who wrote it?"

    * internal plan-phase labels (F.1/F.2/F.3) -- meaningless outside our roadmap
    * comments describing code that no longer exists ("a bring-up sine synth")
    * comment blocks that lost their indentation in an earlier trimming pass
    * multiple assignments on one line -- measured null is 0 across four merged
      upstream CPU cores (sharcops.hxx, m68kmusashi.cpp, mn10200.cpp, sh4.cpp),
      so this is house style rather than a rule invented here

RUN   python3 final_polish.py            (from the PR worktree root)
PASS  prints "ok"; the PR-wide greps for "F.[0-9]" and notes/*.md come back empty.
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


edit('src/devices/cpu/sharc/sharc.cpp', [
("""// memory (0x80000+) is added in F.2/F.3 when the DSP actually runs.
""",
 """// memory (0x80000+) is not modelled yet.
"""),
("""	// F.3: the kernel programs the SPORT-DMA chain-pointer (CP) registers with a value CP; the
	// transfer-control block lives at internal address 0x8000 + (CP & 0x1FFFF), whose II
""",
 """	// A program sets the SPORT-DMA chain-pointer (CP) registers; the
	// transfer-control block lives at internal address 0x8000 + (CP & 0x1FFFF), whose II
"""),
])

edit('src/devices/cpu/sharc/sharc.h', [
("""	// F.3 SPORT audio: the base addresses of the kernel's serial-audio DMA autobuffers, derived
	// at runtime from its DMA transfer-control blocks (see iop65l_w). [sport 0/1][A=0 / B=1].
""",
 """	// Base addresses of the running program's serial-audio DMA autobuffers, derived
	// at runtime from its DMA transfer-control blocks (see iop65l_w). [sport 0/1][A=0 / B=1].
"""),
("""	// F.3 SPORT audio DMA autobuffer bases (see sport_tx_buffer/sport_rx_buffer).
""",
 """	// SPORT audio DMA autobuffer bases (see sport_tx_buffer/sport_rx_buffer).
"""),
])

edit('src/mame/matsushita/kn7000.cpp', [
("""#include "cpu/sharc/sharc.h"        // IC306 effects DSP (ADSP-21065L; F.1 uses the 21062 core)
""",
 """#include "cpu/sharc/sharc.h"        // IC306 effects DSP (ADSP-21065L)
"""),
("""// kn7000_dsp_bridge_device -- routes the tone-generator audio through the effects
// DSP (F.3). It sits between the TG and the speakers with 2 inputs and 2 outputs.
""",
 """// kn7000_dsp_bridge_device -- routes the tone-generator audio through the effects
// DSP. It sits between the TG and the speakers with 2 inputs and 2 outputs.
"""),
("""	required_device<kn7000_dsp_bridge_device> m_dspbridge;  // F.3: routes TG audio through the effects DSP
	required_device<adsp21065l_device> m_dsp;           // IC306 effects DSP (ADSP-21065L SHARC; host-boot idle until F.2)
""",
 """	required_device<kn7000_dsp_bridge_device> m_dspbridge;  // routes TG audio through the effects DSP
	required_device<adsp21065l_device> m_dsp;           // IC306 effects DSP (ADSP-21065L SHARC)
"""),
("""	// F.2 host-boot upload state (see dsp_data_w): the firmware sets a target address (reg
""",
 """	// Host-boot upload state (see dsp_data_w): the firmware sets a target address (reg
"""),
("""	// kernel's main loop one frame per edge. Stands in for the SPORT/codec frame sync until
	// F.3 models the real serial audio path; value is a plausible placeholder, not measured.
""",
 """	// kernel's main loop one frame per edge. Stands in for the SPORT/codec frame sync;
	// the value is a plausible placeholder, not measured.
"""),
("""				// Start the audio frame tick: the kernel's reset handler enables IRQ0 and then
// IDLEs (PM 0x8076) waiting for the first IRQ0, which drives its main loop one
// audio frame per edge. On real hardware IRQ0 comes from the SPORT/codec frame
// sync; here a periodic pulse stands in until F.3 models the serial audio path.
""",
 """				// Start the audio frame tick: the kernel's reset handler enables IRQ0 and
				// then IDLEs waiting for the first one, which drives its main loop one audio
				// frame per edge. On real hardware IRQ0 comes from the SPORT/codec frame
				// sync; a periodic pulse stands in for it here.
"""),
("""	// F.3 audio path -- REAL TOPOLOGY (SPORT DMA-chain RE, workflow wf_b58b1fda-df3):
""",
 """	// Audio path. None of the DSP's TX slots feeds a DAC directly:
"""),
("""		// Multi-unit routing per the LIVE-CAPTURED unit map (2026-07-20,
		// notes/dsp-unit-roles-live-capture.md -- DspEffectSelect + download-port taps):
""",
 """		// Multi-unit routing, from the effect-select and download-port traffic:
"""),
("""	// Effects DSP (F.2): hold the SHARC halted. The firmware host-boots it -- dsp_data_w
	m_dsp->set_input_line(INPUT_LINE_HALT, ASSERT_LINE);
	m_dsp_running = false;
	m_dsp_dl_words = 0; m_dsp_mode = 0; m_dsp_wcnt = 0; m_dsp_cur = 0; m_dsp_dl_addr = 0;
""",
 """	// Hold the SHARC halted; the firmware host-boots it through dsp_data_w.
	m_dsp->set_input_line(INPUT_LINE_HALT, ASSERT_LINE);
	m_dsp_running = false;
	m_dsp_dl_words = 0;
	m_dsp_mode = 0;
	m_dsp_wcnt = 0;
	m_dsp_cur = 0;
	m_dsp_dl_addr = 0;
"""),
("""	// --- Sound (first cut): a bring-up sine synth keyed by the PC key bed, so
//     notes are audible now. Real dual-TG PCM synthesis + effects DSP is future
//     work (see notes/audio-output-implementation-plan.md). Shared by all the
//     models that reuse this config; only kn7000 drops MACHINE_NO_SOUND for now.
""",
 """	// --- Sound. Shared by every model that reuses this config.
"""),
("""	KN7000_TONEGEN(config, m_tonegen, 0);
	// F.3: route the tone-generator audio through the effects-DSP bridge, then to the speakers.
""",
 """	KN7000_TONEGEN(config, m_tonegen, 0);
	// Route the tone-generator audio through the effects-DSP bridge, then to the speakers.
"""),
# remaining dangling note pointers and provenance
("""				// at its own makeup so it does NOT couple to the reverb TOTAL DEPTH. Live capture
""",
 """				// at its own makeup so it does NOT couple to the reverb TOTAL DEPTH.
"""),
("""	// ch0 = control panel, ch1 = MIDI port 1, ch2 = MIDI port 2 (adversarially
""",
 """	// ch0 = control panel, ch1 = MIDI port 1, ch2 = MIDI port 2.
"""),
("""	// The boot code writes to 0x90000000 and 0x8C000000 (copying from the top of
// the program ROM). Neither is in the static I/O map (notes/io-map.md); they
// are almost certainly the LCD V-RAM / video / wave-DMA windows. Mapped as RAM
// placeholders so bring-up can proceed past them.
""",
 """	// The boot code writes to 0x90000000 and 0x8C000000, copying from the top of
	// the program ROM. Neither appears in the static I/O map; they are most likely
	// the LCD V-RAM / video / wave-DMA windows. Mapped as RAM placeholders.
"""),
("""	// Tone-generator register-indirect write interface (write-only; see the
	// member declaration and notes/tone-generator.md). Modeling it here captures
	// the register file and keeps the constant TG traffic out of the io_w log.
""",
 """	// Tone-generator register-indirect write interface (write-only; see the member
	// declaration). Modeling it here captures the register file and keeps the
	// constant TG traffic out of the io_w log.
"""),
# crammed assignment lines (measured null upstream: 0)
("""			l = m_rx[m_rx_rd][0]; r = m_rx[m_rx_rd][1];
			rawl = m_rxraw[m_rx_rd][0]; rawr = m_rxraw[m_rx_rd][1];
""",
 """			l = m_rx[m_rx_rd][0];
			r = m_rx[m_rx_rd][1];
			rawl = m_rxraw[m_rx_rd][0];
			rawr = m_rxraw[m_rx_rd][1];
"""),
("""		m_tx[m_tx_wr][0] = l; m_tx[m_tx_wr][1] = r;
		m_tx[m_tx_wr][2] = cl; m_tx[m_tx_wr][3] = cr;   // chorus return (0 when chorus off -> no effect)
		m_tx[m_tx_wr][4] = dl; m_tx[m_tx_wr][5] = dr;   // sound-dsp return (0 when off -> no effect)
		m_tx[m_tx_wr][6] = ml; m_tx[m_tx_wr][7] = mr;   // multi return (0 when off -> no effect)
""",
 """		m_tx[m_tx_wr][0] = l;
		m_tx[m_tx_wr][1] = r;
		m_tx[m_tx_wr][2] = cl;   // chorus return (0 when chorus off -> no effect)
		m_tx[m_tx_wr][3] = cr;
		m_tx[m_tx_wr][4] = dl;   // sound-dsp return (0 when off -> no effect)
		m_tx[m_tx_wr][5] = dr;
		m_tx[m_tx_wr][6] = ml;   // multi return (0 when off -> no effect)
		m_tx[m_tx_wr][7] = mr;
"""),
("""		m_dsp_active = false; m_tx_primed = false;
""",
 """		m_dsp_active = false;
		m_tx_primed = false;
"""),
("""				ol = il; orr = ir;   // DSP not talking yet (early boot) -> dry TG passthrough
""",
 """				// DSP not talking yet (early boot) -> dry TG passthrough
				ol = il;
				orr = ir;
"""),
("""					ol = m_tx[m_tx_rd][0]; orr = m_tx[m_tx_rd][1];
					chl = m_tx[m_tx_rd][2]; chr = m_tx[m_tx_rd][3];
					ddl = m_tx[m_tx_rd][4]; ddr = m_tx[m_tx_rd][5];
					mml = m_tx[m_tx_rd][6]; mmr = m_tx[m_tx_rd][7];
""",
 """					ol = m_tx[m_tx_rd][0];
					orr = m_tx[m_tx_rd][1];
					chl = m_tx[m_tx_rd][2];
					chr = m_tx[m_tx_rd][3];
					ddl = m_tx[m_tx_rd][4];
					ddr = m_tx[m_tx_rd][5];
					mml = m_tx[m_tx_rd][6];
					mmr = m_tx[m_tx_rd][7];
"""),
("""					m_tx_last[0] = ol; m_tx_last[1] = orr; m_tx_last[2] = chl; m_tx_last[3] = chr;
					m_tx_last[4] = ddl; m_tx_last[5] = ddr; m_tx_last[6] = mml; m_tx_last[7] = mmr;
""",
 """					m_tx_last[0] = ol;
					m_tx_last[1] = orr;
					m_tx_last[2] = chl;
					m_tx_last[3] = chr;
					m_tx_last[4] = ddl;
					m_tx_last[5] = ddr;
					m_tx_last[6] = mml;
					m_tx_last[7] = mmr;
"""),
])

edit('src/mame/matsushita/kn_tonegen.cpp', [
("""				w.bank = p[e]; w.zlo = p[e+1]; w.zhi = p[e+2];
""",
 """				w.bank = p[e];
				w.zlo = p[e+1];
				w.zhi = p[e+2];
"""),
("""				w.len = rd32(e+8); w.lstart = rd32(e+12); w.llen = rd32(e+16);
""",
 """				w.len = rd32(e+8);
				w.lstart = rd32(e+12);
				w.llen = rd32(e+16);
"""),
("""		w.bank = 0xFF; w.zlo = 0; w.zhi = 0;
""",
 """		w.bank = 0xFF;
		w.zlo = 0;
		w.zhi = 0;
"""),
("""		w.len = SINE_LEN; w.lstart = 0; w.llen = SINE_LEN;
""",
 """		w.len = SINE_LEN;
		w.lstart = 0;
		w.llen = SINE_LEN;
"""),
])

edit('src/devices/cpu/mn10300/mn10300.cpp', [
("""		m_lar = pop32(); m_lir = pop32(); m_mdr = pop32();
		m_a[1] = pop32(); m_a[0] = pop32(); m_d[1] = pop32(); m_d[0] = pop32();
""",
 """		m_lar = pop32();
		m_lir = pop32();
		m_mdr = pop32();
		m_a[1] = pop32();
		m_a[0] = pop32();
		m_d[1] = pop32();
		m_d[0] = pop32();
"""),
])
print('ok')
