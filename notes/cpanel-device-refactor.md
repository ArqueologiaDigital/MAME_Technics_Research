# KN7000 control-panel extracted to a device (2026-07-13)

The control-panel HLE was split out of the monolithic driver into a dedicated device
`kn7000_cpanel_device`, mirroring the KN5000's `kn5000_cpanel_device` shape/style.

## Files
- `src/mame/matsushita/kn7000_cpanel.h` / `.cpp` (new device, ~90 + 308 lines).
- `src/mame/matsushita/kn7000.cpp` shrank 3232 -> 3011 lines.
- `build.sh`: symlinks the two new files into the build tree + adds `kn7000_cpanel.cpp`
  to the `SOURCES=` list (it also auto-compiles via the `#include "kn7000_cpanel.h"`, like kn5000).

## What moved vs stayed (the seam)
The KN7000 panel link is BYTE-level (unlike the KN5000's bit-level): the main CPU's SIO
delivers whole bytes. So the device is simpler than the KN5000's bit-bang serial.

MOVED to `kn7000_cpanel_device`:
- 7-byte TX frame parse (was in `sio_tx_byte` SIO_PANEL) -> `tx_byte()`.
- `panel_led_frame` (LED decode reg*8+bit), `panel_queue` (reply queue + ATN kick).
- reply-delivery event timer `panel_event` (param 1 = ATN edge, param 2 = next RX byte).
- 250 Hz `panel_scan` (buttons + APC/SEQ pot 0xD2 + DATA dial 0x10 + TEMPO knob 0x17),
  MINUS the MAIN-VOLUME->DSP block.
- all panel state (m_panel_pos/p1/p2, m_panel_resp/len/pos, m_btn_prev, the pot/dial/knob
  prev/synced/pos), the SEG/DIAL/VOLAPCSEQ/TEMPO ioports (by tag), the cpl/cpc/cpr LED finders.

STAYED in the driver (main-CPU SIO peripheral concerns):
- `sio_r`/`sio_w`, the 3-channel RX FIFOs, MIDI.
- the SIO byte-transfer completion **group 0x11** (`m_panel_txdone` -> new `panel_txdone_cb`,
  `m_c11_unserviced`, the intc_w re-deliver + irq_ack clear). This is per-byte SIO completion,
  NOT panel-HLE, so it stays.
- the INTC, and the MAIN-VOLUME->DSP master-gain poll (its own `volume_scan` timer, 250 Hz).

BRIDGE:
- driver -> device: `tx_byte(data)` (sio_tx_byte SIO_PANEL), `rx_enable()` (sio_w config bit14),
  `atn_rearm()` (intc_w EXTMD 11b->10b edge).
- device -> driver callbacks: `atn()` write_line -> `intc_assert(0x1a)`;
  `rxd()` write8 -> `{ sio_rx_push(SIO_PANEL, data); intc_assert(0x10); }`.
- machine_config: `KN7000_CPANEL(config, m_cpanel)` + the two callbacks + `set_seg_port`/
  `set_dial_port`/`set_volapcseq_port`/`set_tempoknob_port` (driver keeps the ioport finders
  as pass-through, exactly like kn5000 keeps m_CPL_SEG).

## Verified
Builds clean (only a pre-existing ROM_OPTIONAL deprecation warning). Runtime smoke test:
boots, CUSTOMIZE LED cpr_led0 goes 0->1 on menu open (through the device tx_byte->panel_led_frame),
held DEMO button still enters demo mode (button-scan -> panel_queue -> atn -> RX handshake).
Backup of the pre-refactor driver: /tmp/kn7000.cpp.backup. Transform script: /tmp/refactor.py.
Adversarial review: workflow cpanel-refactor-review (wf_a954d3fb-487).
