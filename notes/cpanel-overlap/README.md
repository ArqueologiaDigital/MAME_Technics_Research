# Do the Technics control-panel devices share enough to justify a generic base?

Asked 2026-09-20: could `wsa1_cpanel` become a specialization of a generic `technics_cpanel`, the
way `kn6000_cpanel` and `kn7000_cpanel` already specialize `kn_cpanel_base_device`?

**Measured answer: no — they share an architecture, not code.** Reproduce with
`measure_overlap.py src/mame/matsushita`.

## What already exists

| device | base class | in upstream MAME? |
|---|---|---|
| `kn_cpanel_base_device` | `device_t` | **no**, overlay only |
| `kn6000_cpanel_device` | `kn_cpanel_base_device` | no |
| `kn7000_cpanel_device` | `kn_cpanel_base_device` | no |
| `kn5000_cpanel_device` | `device_t` — **never migrated to the base** | **yes, merged** |
| `wsa1_cpanel_device` | `device_t` | no (in the PR branch) |

So a generic base already exists for *part* of the KN family, and the oldest member never moved to
it. That is the first piece of evidence: when this refactor was available, it was not worth doing
for the KN5000 either.

## 1. Text overlap, comments and string bodies stripped

|  | kn_cpanel | kn5000 | kn6000 | kn7000 | wsa1 |
|---|---|---|---|---|---|
| **kn_cpanel** | 100% | 1.5% | 2.0% | 1.5% | 5.6% |
| **kn5000** | 7.2% | 100% | 1.4% | 3.2% | 3.1% |
| **kn6000** | 6.9% | 1.4% | 100% | 7.6% | 2.0% |
| **kn7000** | 8.0% | 4.8% | 10.7% | 100% | 3.2% |
| **wsa1** | 15.4% | 3.5% | 2.0% | 2.5% | 100% |

⚠ Read this carefully, because the obvious reading is wrong. `wsa1` scores **15.4%** against
`kn_cpanel` — *higher* than `kn7000` scores against its own base (8.0%). That is not evidence that
wsa1 belongs under the base; it is an artifact of length (769 lines vs 278) and of the fact that a
derived class **should** share little with its base, because the base already holds the common
part. The table's real message is that every number is small.

## 2. Shared method surface

`wsa1_cpanel` defines 12 out-of-line methods:

    device_input_ports, device_reset, device_start, dial_delta, frame_complete, led_frame,
    queue_frame, rx_enable, segment_is_wired, start_request, tx_byte

Shared with `kn_cpanel`: **`device_start`, `device_reset`** (`device_t` boilerplate, not protocol)
and **`tx_byte`, `rx_enable`**. With `kn5000`/`kn6000`/`kn7000`: only `device_input_ports` and the
`device_t` pair.

So the entire common protocol surface is **two entry points plus the `atn()`/`rxd()` callbacks** —
an interface, not a body of code.

⚠ An earlier version of the script also matched in-class declarations with a loose
`type name(` pattern and reported 9-11 "shared methods", counting `if`, `switch`, `return`,
`LOGMASKED` and `PORT_START`. If a count here ever looks generous, check what it counted.

## 3. The protocol constants, which is what kills it

| | wsa1 | kn7000 / kn_cpanel |
|---|---|---|
| serial peripheral | TMP95C061 **SC1**, I/O-interface (synchronous) mode | MN10300 **SIO channel 0** |
| attention | **INT6** | INTC **group 0x1A**, with a two-edge re-arm dance |
| frame length | variable: 2, or `(n & 0x0F) + 3` | fixed **7-byte** TX frames |
| segment space | wire addresses `0xC0..0xD7` directly | **normSeg** normalization + `seg_wire_addr()` |

`kn_cpanel_base_device` is parameterized on exactly these. Hoisting a base above both would mean
virtualizing the frame parser, the attention sequence, the segment normalization and the LED
decode — everything the KN base currently *does* — leaving a base holding a reply queue and two
callbacks. That is not a refactor, it is a rename with extra indirection.

The one genuinely shared hardware fact is the panel MCU part: the WSA1R's IC1 is a Mitsubishi
M37471M2196S, the same part as the two panel MCUs in `kn5000_cpanel.cpp`. Same MCU, different
firmware, different host CPU, different link. Shared silicon does not imply shared driver code.

## Recommendation

1. **Do not hoist a `technics_cpanel` base**, and especially not inside the SX-WSA1R driver PR.
   `kn5000_cpanel` is already merged upstream; refactoring a merged device as part of a new-driver
   submission expands the review surface for no functional gain, and our own measurements of MAME
   review latency say breadth is what makes a PR slow.
2. **If the duplication ever does bite**, the cheap version is a ~20-line abstract interface
   (`tx_byte`, `rx_enable`, `atn`, `rxd`) that both families implement, not a shared base with
   behaviour in it.
3. **Renaming `wsa1_cpanel` to `wsa1r_cpanel` stands on its own merits** and does not depend on
   any of the above: the device models the rack's panel only, and the SX-WSA1 keyboard's panel is
   a different board that will need its own device.
