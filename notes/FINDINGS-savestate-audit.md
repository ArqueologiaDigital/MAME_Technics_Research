# Save-state coverage across the Technics devices

*2026-08-15. Tool: `tools/audit_savestate.py` (run it; do not trust this table's age).*

## Why this exists

MAME requires working save states, and an unregistered mutable member is invisible until
someone loads a state and the machine is quietly wrong. That already happened here: nine
effect-send gains in `kn_tonegen` were omitted because they are `std::atomic<float>` and
`save_item()` cannot register an atomic. A state saved with reverb engaged restored with the
boot-default mix — nothing looked wrong until you listened. Fixed in `ac0a8bb` by shadowing them
through `device_pre_save()` / `device_post_load()`.

## Current state

```
device header                           decl  saved  unregistered
kn5000_cpanel.h                           39     24             1  <-- look
kn5000_tonegen.h                          41      5            30  <-- look
kn6000_cpanel.h                            3      0             0
kn7000_cpanel.h                            6      2             0
kn_cpanel.h                               19     13             0
kn_tonegen.h                              42     28            13  [hooks: some may be shadowed]
```

`kn_tonegen`'s 13 are the nine now-shadowed gains plus four legitimately exempt (the
MAME-managed stream, construction-time `m_num_voices`, and the immutable ROM-derived
`m_wentries` / `m_sine_pcm` / `m_wdefault`). That row is **done**; the tool cannot follow the
shadow indirection, which is why it still lists them.

## What is actually left, read by hand

**`kn5000_cpanel` — `m_tx_queue` (`std::queue<uint8_t>`).** The control-panel serial transmit
queue. A state saved mid-frame loses whatever was queued, which on this device means a dropped
panel byte — and the KN5000 panel link is already known to wedge in ways that are hard to
reproduce. Real, but it needs the shadow treatment and the CP-serial work is on hold at Felipe's
request, so it is **not** something to change unasked.

**`kn5000_tonegen` — 30 members, but most are not emulation state.** Read individually they fall
into three groups:

| group | members | verdict |
|---|---|---|
| instrumentation | `m_anchor_census`, `m_census_*`, `m_glitch_*`, `m_insta_*`, `m_dsp1_*`, `m_notelog`, `m_nl*`, `m_undumped_muted` | measurement counters, not machine state — saving them would be wrong, not merely unnecessary |
| derived / immutable | `m_sine_tab`, `m_dir`, `m_waveform_size` | built once from ROM |
| **genuine runtime state** | **`m_keybed_queue`** (`std::queue`), **`m_pending_notes`** (`std::deque`), `m_eg_gain`, `m_eg_gate_latch`, `m_handoff_ctrl`, `m_mute_undumped`, `m_use_level080` | the two containers hold queued note events; the flags are live gates |

The two containers are the ones that matter, and they need the same shadow pattern as the gains.
The flags are cheap. **This is the KN5000 — the one driver that is upstream — so its save-state
correctness matters more than the fork-only models'.**

## Honest limits of the tool

It is a lead generator, not a proof. It cannot distinguish a mutable member from a constant, it
exempts by *type* (a `std::vector` can be live state), and it cannot see shadowing. Every line it
prints is a question. The three groups above were decided by reading the code, not by the script.
