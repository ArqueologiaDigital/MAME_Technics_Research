# KN7000 panel LEDs — output path (preliminary)

Complements the panel *switch* mapping (notes/service-diagnostic-mode.md,
panel-matrix-service-manual.md). Needed to eventually light the `.lay` LEDs from
firmware state. Found by static RE; the final register/panel-command write still
needs one writer traced end-to-end.

## Two LED categories

**1. Button LEDs** (the small LED next to most panel buttons).
`PanelSwitchClassTable` @ 0x4860C9F4 gives, per switch#, a 2-byte record
`[LED_row_bit, LED_col_reg]` where `LED_col_reg` is one-hot (0x01/02/04/08/10/20 =
LED-matrix column) and `LED_row_bit` = 0..7. Records with high byte 0xFF are class
codes (0xF0–0xF5) for switches with **no** LED (e.g. keyboard keys). Decoded (my
independent dump, scratchpad/my_table_decode.txt): switches 6–40 and 53 carry LED
coords; e.g. sw08–15 = reg 0x02 bits 7..0, sw16–23 = reg 0x04, sw26–36 = reg 0x08,
sw35 = reg 0x10, sw40 = reg 0x20. This is what the service PANEL SW&LED test uses.

**2. Named indicator LEDs** (mode/hold/dial/other-part/…), driven by a small API:
- `SetOtherPartLed` 0x484164F4, `SetHoldLed` 0x48416512, `BlinkHoldLed` 0x48416536,
  `SetDialLed` 0x48416563, `SetModeLed` 0x48416590 (+ CheckHoldLED/CheckDialLED).
- These normalize an on/off arg then call the **LED dispatcher `0x484B1BCB`** with
  an LED index in `d0` (1..0x13 = 1..19; out-of-range → early return).
- Dispatcher: `(idx-1)*4` into **jump table `0x4861518C`** (19 u32 handlers).
- Each handler is `mov 1,d0; call 0x484B0Cxx; ret` — i.e. every one of the 19 LEDs
  has its **own dedicated set-function**:
  | idx | handler | writer |
  |-----|---------|--------|
  | 1 | 0x484B1BE7 | 0x484B0C3F |
  | 2 | 0x484B1BF1 | 0x484B0CA2 |
  | 3 | 0x484B1BFB | 0x484B1099 |
  | 4 | 0x484B1C05 | 0x484B0D05 |
  | 5 (OtherPart) | 0x484B1C0F | … |
  | …19 | 0x484B1C37/…/0x484B1C9B | … |

LED-related state RAM sits around 0x50021FD4–0x50022000 (SetModeLed reads
0x50021FD4; SetDialLed writes 0x50022000).

## TODO (for LED modeling in the driver + .lay)
1. Trace one writer (e.g. 0x484B0C3F) to the actual register or panel-serial
   command byte(s) it emits — determines whether button/indicator LEDs are a
   memory-mapped latch or a panel sub-CPU command (PanelTxKick 0x484AC523).
2. Expose those as MAME `output_finder` LEDs; bind `.lay` LED elements to them so
   they light from firmware state (the "LEDs" half of "buttons and LEDs").
3. Cross-map the 19 named-LED indices + the PanelSwitchClassTable button-LED coords
   to the physical LEDs in the layout.
