// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN6000 / KN6500 control panel HLE

    The SX-KN6000 and SX-KN6500 share ONE panel device: their firmware button
    matrices are BYTE-IDENTICAL (30 descriptor segments, 164 button-bits, zero
    differing entries -- see notes/kn6000-panel-matrix.md), so a single class
    serves both models.

    The panel is scanned by TWO Mitsubishi M37471M2196S 8-bit sub-CPUs (service
    manual pp.45-49): IC1 on the CPL board (10 SEG strobe columns) and IC10 on
    the CPR board (16 SEG columns, 10 of them wired). The CPC, LCDL, LCDC and
    LCDR boards have no CPU of their own -- they are matrix extensions hanging
    off those two. Buttons sit at (SEG column x SW0..SW7 return line); LEDs sit
    at (PNP anode group x SEG column).

    The CP wire protocol, the ATN/RX handshake and the analog controllers are
    shared with the KN7000 and live in the base class (kn_cpanel.h).

    Matrix: notes/kn6000-panel-matrix.md

***************************************************************************/

#ifndef MAME_MATSUSHITA_KN6000_CPANEL_H
#define MAME_MATSUSHITA_KN6000_CPANEL_H

#pragma once

#include "kn_cpanel.h"

class kn6000_cpanel_device : public kn_cpanel_base_device
{
public:
	kn6000_cpanel_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

protected:
	// device_t overrides
	virtual ioport_constructor device_input_ports() const override ATTR_COLD;

	// per-model geometry (see kn_cpanel.h)
	virtual int     num_scan_ports() const override { return 20; }
	virtual uint8_t scan_port_read(int port) override { return m_phys[port].read_safe(0); }
	virtual uint8_t port_seg(int port) const override { return uint8_t(port); }   // port index == normSeg
	virtual int     num_segs() const override { return 0x14; }
	virtual uint8_t seg_wire_addr(int seg) const override;
	virtual void    panel_led_frame(uint8_t addr, uint8_t data) override;

private:
	// Button scan-matrix ports -- OWNED by this device. One per sub-CPU scan column:
	// CPL_SEG0..9 = normSeg 0x00-0x09, CPR_SEG0..9 = normSeg 0x0A-0x13.
	optional_ioport_array<20> m_phys;

	// LED outputs (the two sub-CPU banks). No KN6000 .lay exists yet, so these are
	// currently unbound sinks; the D-number/legend inventory is in the notes.
	output_finder<512> m_cpl_leds;
	output_finder<512> m_cpr_leds;
};

DECLARE_DEVICE_TYPE(KN6000_CPANEL, kn6000_cpanel_device)

#endif // MAME_MATSUSHITA_KN6000_CPANEL_H
