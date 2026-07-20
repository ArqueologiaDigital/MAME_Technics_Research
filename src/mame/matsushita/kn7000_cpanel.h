// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN7000 control panel HLE

    High-level emulation of the KN7000 front-panel sub-CPUs (one per panel
    PCB) that scan the button matrices and analog controls and drive the panel
    LEDs, talking to the main MN10300 over a synchronous serial link (channel
    0 of the SIO ASIC).

    Only the KN7000-SPECIFIC half lives here: the button scan matrix (40
    normalized segments, 230 descriptor button-bits) and the three-board LED
    register decode. The CP wire protocol, the ATN/RX handshake and the analog
    controllers are shared with the other MN10300 models and live in the base
    class (kn_cpanel.h / kn_cpanel.cpp).

    Protocol: notes/panel-serial-protocol.md
    Matrix:   notes/panel-descriptor-map.md

***************************************************************************/

#ifndef MAME_MATSUSHITA_KN7000_CPANEL_H
#define MAME_MATSUSHITA_KN7000_CPANEL_H

#pragma once

#include "kn_cpanel.h"

class kn7000_cpanel_device : public kn_cpanel_base_device
{
public:
	kn7000_cpanel_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

	// Firmware-authoritative global-effect ON state, read from the LED frames the firmware
	// itself sends (CPR bank reg 0x03: MULTI = D1054 bit4, CHORUS = D1082 bit5). The driver's
	// DSP bridge uses these as the effect-enable gate for the cold-toggle case where the
	// firmware announces the state ONLY via the LED (see kn7000.cpp's group-0x20 notes).
	virtual bool chorus_led() const override { return m_chorus_led; }
	virtual bool multi_led() const override { return m_multi_led; }

protected:
	// device_t overrides
	virtual void device_start() override ATTR_COLD;
	virtual ioport_constructor device_input_ports() const override ATTR_COLD;   // the CP{board}_SEG{col} button matrix

	// per-model geometry (see kn_cpanel.h)
	virtual int     num_scan_ports() const override { return 22; }
	virtual uint8_t scan_port_read(int port) override { return m_phys[port].read_safe(0); }
	virtual uint8_t port_seg(int port) const override;
	virtual int     num_segs() const override { return 0x21; }
	virtual uint8_t seg_wire_addr(int seg) const override;
	virtual void    panel_led_frame(uint8_t addr, uint8_t data) override;

private:
	// Global-effect LED shadow (set in panel_led_frame; see chorus_led()/multi_led()).
	bool m_chorus_led = false;          // D1082 CHORUS (cpr_led29)
	bool m_multi_led  = false;          // D1054 MULTI (cpr_led28)

	// Button scan-matrix ports -- OWNED by this device (declared in device_input_ports(),
	// bound by tag in the constructor). One per physical board SEG column.
	optional_ioport_array<22> m_phys;      // CP{board}_SEG{col}

	// LED outputs (the three panel PCBs: left / center / right).
	output_finder<512> m_cpl_leds;
	output_finder<64>  m_cpc_leds;
	output_finder<512> m_cpr_leds;
};

DECLARE_DEVICE_TYPE(KN7000_CPANEL, kn7000_cpanel_device)

#endif // MAME_MATSUSHITA_KN7000_CPANEL_H
