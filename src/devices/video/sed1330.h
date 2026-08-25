// license:BSD-3-Clause
// copyright-holders:Curt Coder
/**********************************************************************

    Seiko-Epson SED1330 LCD Controller emulation

    ----------------------------------------------------------------
    OVERLAY COPY -- kn7000_mame development tree.

    Stock MAME's sed1330_device leaves update_graphics() an empty
    function body, so a host that puts the part in all-graphics mode
    (OVLAY DM1 = DM3 = 1) drives a correctly-programmed but
    permanently blank panel.  The Technics SX-WSA1R does exactly that,
    so this copy implements it.  Three changes against upstream:

      * update_graphics() is implemented (OR composition of pages 1,
        2 and optionally 3);
      * draw_graphics_scanline() gained a `blend` argument and a clamp
        against the bitmap width;
      * command_w() honours a bare DISP ON / DISP OFF with no
        parameter byte, which the WSA1's panel init ends with;
      * every scalar member has a default initialiser, so the frames
        rendered before the host programs the chip cannot read
        indeterminate geometry.

    Nothing here changes behaviour for a host that uses text mode and
    always sends the DISP parameter byte, which is every other
    consumer of this device in tree.  Upstreaming these is a separate
    job and would need pc8401a / pc8500 / textelcomp / psr2000
    regression runs; none of those drivers is in this focused build.
    ----------------------------------------------------------------

**********************************************************************/

#ifndef MAME_VIDEO_SED1330_H
#define MAME_VIDEO_SED1330_H

#pragma once




//**************************************************************************
//  TYPE DEFINITIONS
//**************************************************************************

// ======================> sed1330_device

class sed1330_device :  public device_t,
						public device_memory_interface,
						public device_video_interface
{
public:
	// construction/destruction
	sed1330_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

	uint8_t status_r();
	void command_w(uint8_t data);

	uint8_t data_r();
	void data_w(uint8_t data);

	uint32_t screen_update(screen_device &screen, bitmap_ind16 &bitmap, const rectangle &cliprect);

protected:
	// device-level overrides
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;

	// device_memory_interface overrides
	virtual space_config_vector memory_space_config() const override;

	// optional information overrides
	virtual const tiny_rom_entry *device_rom_region() const override ATTR_COLD;

private:
	// Every scalar below carries a default initialiser.  Upstream initialises
	// only m_bf, in the constructor, and device_reset() is empty, so on the
	// frames drawn before the host has programmed the chip the render path
	// reads indeterminate m_lf / m_cr / m_ap and can walk outside the bitmap.
	// The values chosen are the inert ones: display off, nothing to draw.
	int m_bf = 0;               // busy flag

	uint8_t m_ir = 0;             // instruction register
	uint8_t m_dor = 0;            // data output register
	int m_pbc = 0;              // parameter byte counter

	int m_d = 0;                // display enabled
	int m_sleep = 0;            // sleep mode

	uint16_t m_sag = 0;           // character generator RAM start address
	int m_m0 = 0;               // character generator ROM (0=internal, 1=external)
	int m_m1 = 0;               // character generator RAM D6 correction (0=no, 1=yes)
	int m_m2 = 0;               // height of character bitmaps (0=8, 1=16 pixels)
	int m_ws = 0;               // LCD drive method (0=single, 1=dual panel)
	int m_iv = 0;               // screen origin compensation for inverse display (0=yes, 1=no)
	int m_wf = 0;               // AC frame drive waveform period (0=16-line, 1=2-frame)

	int m_fx = 1;               // character width in pixels
	int m_fy = 1;               // character height in pixels
	int m_cr = 0;               // visible line width in characters
	int m_tcr = 0;              // total line width in characters (including horizontal blanking)
	int m_lf = 0;               // frame height in lines
	uint16_t m_ap = 0;            // virtual screen line width in characters

	uint16_t m_sad1 = 0;          // display page 1 start address
	uint16_t m_sad2 = 0;          // display page 2 start address
	uint16_t m_sad3 = 0;          // display page 3 start address
	uint16_t m_sad4 = 0;          // display page 4 start address
	int m_sl1 = 0;              // display block 1 height in lines
	int m_sl2 = 0;              // display block 2 height in lines
	int m_hdotscr = 0;          // horizontal dot scroll in pixels
	int m_fp = 0;               // display page flash control

	uint16_t m_csr = 0;           // cursor address register
	int m_cd = 0;               // cursor increment direction
	int m_crx = 1;              // cursor width
	int m_cry = 1;              // cursor height or location
	int m_cm = 0;               // cursor shape (0=underscore, 1=block)
	int m_fc = 0;               // cursor flash control

	int m_mx = 0;               // screen layer composition method
	int m_dm = 0;               // display mode for pages 1, 3
	int m_ov = 0;               // graphics mode layer composition

	// address space configurations
	const address_space_config      m_space_config;
	memory_access<16, 0, 0, ENDIANNESS_LITTLE>::cache m_cache;

	inline uint8_t readbyte(offs_t address);
	inline void writebyte(offs_t address, uint8_t m_data);
	inline void increment_csr();

	void draw_text_scanline(bitmap_ind16 &bitmap, const rectangle &cliprect, int y, int r, uint16_t va, bool cursor);
	void draw_graphics_scanline(bitmap_ind16 &bitmap, const rectangle &cliprect, int y, uint16_t va, bool blend = false);
	void update_graphics(bitmap_ind16 &bitmap, const rectangle &cliprect);
	void update_text(bitmap_ind16 &bitmap, const rectangle &cliprect);

	void sed1330(address_map &map) ATTR_COLD;
};


// device type definition
DECLARE_DEVICE_TYPE(SED1330, sed1330_device)

#endif // MAME_VIDEO_SED1330_H
