# How the KN5000 driver handles panel buttons+LEDs without the sub-CPU dump

The KN5000 **also lacks the control-panel MCU dumps**, yet its layout has every
button bound and LEDs modeled. It solves this the way the KN7000 should: a
behavioral **`kn5000_cpanel` device** that emulates the panel sub-CPUs' scan +
serial protocol (from the schematic, not a dump), plus a `.lay` that binds
**physical** ports. Reference: `mame_driver/src/mame/matsushita/kn5000_cpanel.{cpp,h}`
and `kn5000.cpp`. (Read-only reference; do not modify that tree.)

## Architecture
- `.lay` buttons bind **physical** ioports `CPL_SEG0..10` / `CPR_SEG0..10`
  (`required_ioport_array<11>`), inputmask = the SW-row bit. No "normalized
  segment" appears in the layout.
- The `kn5000_cpanel_device`:
  - **button_scan_callback** (~143 Hz timer): scans each `CPx_SEG` port; a change
    must be stable for 2 scans (debounce) before it's reported.
  - **send_button_packet(seg, is_left)**: emits a 2-byte frame
    `header = (seg & 0x0F) | (is_left ? 0xC0 : 0x00)` then `state` (the SW-row
    bitmask). The **main-CPU firmware normalizes** header→normSeg via its own wire
    table and dispatches. So the driver never needs physical→normSeg — it sends
    the physical (panel,seg) and the ROM does the scramble.
  - **process_led_command(row, data)** + `m_cpl_leds`/`m_cpr_leds`
    (`output_finder "cpl_led_%u"/"cpr_led_%u"`): decodes the main CPU's LED
    commands and drives layout LED outputs.
  - full self-clocked serial TX/RX state machine (SIN/SOUT/CLK/RST, INTA).

## Why this matters for the KN7000
- **The KN7000 driver already emits the identical frame format.** Its
  `panel_scan` sends `[addr][data]` with `addr = bank(0xC0=left/0x00=right) |
  seg`, `data = bitmask` — byte-for-byte the KN5000 `send_button_packet` header.
  Difference is only cosmetic: the KN7000 binds **normalized** `SEGnn` ports and
  reverse-normalizes to the addr; the KN5000 binds **physical** `CPx_SEG` and
  sends directly. Both require the same knowledge (which seg a button is on).
- **The bridge "problem" is thus already solved structurally** — the physical→
  normSeg scramble is done by the *firmware's* wire table (0x486135A0), not by us.
  For any button whose **function** we know from the descriptors
  (panel-button-normseg-map.md), we already have its normSeg.bit and can bind it.
- **LED modeling template:** adopt `process_led_command` + `output_finder` LEDs
  (our panel-leds.md traced the KN7000 LED writers 0x484B0Cxx / class table
  0x4860C9F4 → matrix cell); bind `.lay` LEDs to those outputs.
- **The KN5000 `.lay` is a cross-reference** for the KN7000's ambiguous buttons
  (LCD soft-keys, OTHER PART, CONTRAST, PAGE, DISPLAY HOLD, EXIT): the boards are
  the same design, so the KN5000's physical seg/SW assignment for a shared button
  is a strong **educated guess** for the KN7000 (per the user's "educated guess"
  guidance) until a sub-CPU dump confirms it.

## Takeaway / plan
The KN7000's normSeg approach is functionally equivalent to the KN5000's and is
fine to keep. Two concrete borrowings from the KN5000:
1. **LEDs**: port the `process_led_command` + output-finder LED modeling so the
   `.lay` LEDs light from firmware state.
2. **Ambiguous buttons**: use the KN5000 `.lay` assignments (+ descriptor
   functions) as educated guesses to finish wiring the soft-keys/CPC buttons.
