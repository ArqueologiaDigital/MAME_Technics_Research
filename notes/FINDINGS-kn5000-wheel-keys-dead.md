# The tempo/program wheel could not be turned from the keyboard

Date: 2026-08-18. Reported by Felipe against the published overlay binary; diagnosed here.

## Symptom

Pressing the wheel's keys did nothing: no change to the port value, no change to the on-screen
tempo. Dragging the knob with the mouse worked. Rebinding the keys in the Input menu changed
nothing.

## Cause

The overlay declared the wheel as

```cpp
PORT_ADJUSTER(50, "Tempo / Program data wheel")
```

**An `IPT_ADJUSTER` cannot carry an input sequence.** Adjusters are driven from the *Slider
Controls* menu, not *Input (this machine)*, so there is no key to rebind and no default to fall
back on. MAME's saved cfg shows the same thing from the other side -- a bare value, no sequences:

```xml
<port tag=":cpanel:ENCODER" type="ADJUSTER" mask="255" defvalue="50" value="73" />
```

The mouse drag worked because the layout script wrote the field directly with `set_value()`,
which bypasses MAME's input pipeline entirely. **The two paths are independent, and only one of
them was ever exercised.**

## Measurement

`tools/rigs/input_seq_probe.lua`, run against the published binary with `--user-cfg`:

```
SEQ field "Tempo / Program data wheel" (type 167)
SEQ   standard   = (none)
SEQ   increment  = (none)
SEQ   decrement  = (none)
```

All three empty. For comparison, a bound control reports actual codes in those slots.

## Fix

`PORT_ADJUSTER` -> a wrapping 24-position `IPT_POSITIONAL` carrying `PORT_CODE_DEC`/`PORT_CODE_INC`,
matching the upstream PR implementation. The device's wrap arithmetic moves from the adjuster's
0..100 range to `ENCODER_POSITIONS`, and the layout keeps its own logical position and writes it
with `set_value()` (an adjuster's `user_value` does not exist on a positional field).

## Three traps worth keeping

1. **`rig.sh` defaults to a throwaway cfg directory.** Every probe run that way reports MAME's
   *default* bindings and is blind to the user's environment. That is RULE 20, and it is the second
   time it has cost a day. Chasing a user-reported binding problem means `--user-cfg`.

2. **A working mouse drag is not evidence of a working control.** The layout writes the field
   directly. `tools/rigs/kn5000_wheel_pr_test.lua` does the same, so it PASSES on a control with no
   bindings at all -- it proves the wire path and says nothing about input.

3. **Check which implementation is in the binary before trusting a test of it.** The binary under
   test contained only the overlay's adjuster; the PR tree had never been built. `strings -a
   <binary> | grep 'Tempo / Program'` distinguishes them in one command.

---

# Second bug: dragging the knob killed the keys (same day)

With the wheel changed to `IPT_POSITIONAL` the keys worked -- until the knob was dragged once with
the mouse, after which they were dead again, permanently. The knob graphic also never moved when
the keys were used.

## Cause

`ioport_field::set_value()` on an analog field sets a **sticky programmatic override**:

```cpp
void analog_field::set_value(s32 value)     // ioport.cpp:3820
{
    m_use_adjoverride = true;
    m_adjoverride = std::clamp(value, m_adjmin, m_adjmax);
}
```

`m_use_adjoverride` is set only there and cleared only by `clear_value()` -- nothing in
`frame_update()` resets it -- and `analog_field::read()` (ioport.cpp:4002) returns the override
instead of the accumulator whenever it is set. So the first layout drag detaches the field from
the input system for the rest of the session.

## The constraint behind it

The two write paths are mutually exclusive **by type**:

```cpp
// ioport.cpp:1048, in ioport_field::set_user_settings
if (!m_settinglist.empty() || m_type == IPT_ADJUSTER)
    m_live->value = settings.value;
```

| control | layout drag via `user_value` | key bindings |
|---|---|---|
| `IPT_ADJUSTER`   | works, and does NOT latch | impossible (no sequences) |
| `IPT_POSITIONAL` | silent no-op; only `set_value()` works, which latches | works |

That is why the adjuster version dragged happily for months while being unturnable from the
keyboard, and why swapping it for a positional traded one bug for the other. Neither type supports
both routes on its own.
