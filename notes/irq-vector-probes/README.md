# How a maskable interrupt reaches its handler on the MN10300 Technics machines

**The question:** the MAME driver used to carry a `namespace fw` block of firmware
addresses, including two KN7000 interrupt handlers, on the belief that the KN7000
"installs two handlers in its self-loaded library and splits the levels between
them" while its siblings use a trampoline. A driver that knows one firmware
revision's internals will not be accepted upstream, so: what does the hardware
actually do?

**The answer.** The MN103002 vectors a maskable interrupt of level L through
`IVR[L]`, a 16-bit register at `0x20000000 + L*4`. Every one of the five firmwares
writes `IVR0..IVR6 = 0` once at boot and never touches them again, then builds a
six-byte `nop ; jmp <handler>` thunk at the base of the vector window
(`0x90000000`), computing the jump displacement against the thunk's own execution
address. So **one vector serves all seven levels on every machine**, and the
handler address is the firmware's business, not the driver's.

The KN7000 was never special. `0x4C03DDA0` — the "quick dispatcher" the driver
named — is referenced by nothing in the whole 4 MB image: no literal, no branch.
It is a dead alternate build of the same handler.

## Run it

```sh
python3 notes/irq-vector-probes/irq_vector_mechanism.py ~/compartilhado/technics_romsets
```

It de-interleaves each romset the way `ROM_LOAD32_WORD` does (even half supplies
bytes 0,1 of each 32-bit word, odd half bytes 2,3; the image loads at
`0x48400000`) and checks two things per image: exactly two thunk builders, and
each of the seven IVRs written exactly once. **PASS on all five, 2026-09-23:**

| romset | thunk 0 handler | thunk 1 handler | builder | IVR writes |
|---|---|---|---|---|
| kn7000 | `0x4C03DE26` | `0x484D77CF` | `0x48410070` | `0x484100A4`-`0x484100C8` |
| kn6000 | `0x4C3F7942` | `0x4C07B19D` | `0x484003AB` | `0x484003DF`-`0x48400403` |
| kn6500 | `0x4C3815A2` | `0x4C07B331` | `0x484003AB` | `0x484003DF`-`0x48400403` |
| kn2400 | `0x5018DF0B` | `0x48705624` | `0x48705CCF` | `0x48705D03`-`0x48705D27` |
| kn2600 | `0x5018DF0B` | `0x48705624` | `0x48705CCF` | `0x48705D03`-`0x48705D27` |

The KN6000 and KN6500 handlers differ (`0x4C3F7942` vs `0x4C3815A2`) on otherwise
near-identical firmware — which is exactly why a driver must not hardcode them.

The pass criterion is deliberately across **all five** images rather than one: a
machine that grew a third thunk, or wrote a non-zero IVR, would invalidate the
single-vector model the driver now relies on.

## Runtime control

Asserting the mechanism is not the same as showing MAME uses it. With the vector
pointed at the thunk, the KN7000 reaches its play screen: **60,903 of 169,600 LCD
pixels non-black**. Moved 0x100 bytes off the thunk — same build, one constant
changed — it is **0 of 169,600**. So the vector is load-bearing and the machine
really does reach its handler through memory the firmware wrote.

## The reset stack pointer, same block

`find_reset_sp_idiom.py` answers the neighbouring question: does each firmware set
SP itself, so the CPU needs no `set_reset_sp()`?

```sh
python3 notes/irq-vector-probes/find_reset_sp_idiom.py <prog.bin> [<prog.bin> ...]
```

It finds the `mov imm32,a0 / mov a0,sp / add -0xc,sp` idiom in the reset path.
Measured 2026-09-23:

| image | reset vector | sets SP at | to |
|---|---|---|---|
| kn7000 | `0x4840FF7E` | `0x4840FFF9` | `0x50021CF8` |
| kn6000 | `0x484002E3` | `0x48400350` | `0x5000778C` |
| kn2400 | `0x48705BDF` | `0x48705C5A` | `0x5006908C` |

All three set it before their first push or call, so the driver's
`set_reset_sp()` was unnecessary — and note the three values DIFFER, so the single
constant the driver carried was the KN7000's applied to all five machines.

## What this does NOT settle

The **board decode of the vector base**. The GPL GDB simulator for this part
(`dv-mn103cpu.c:250`) applies `0x40000000 + IVR[level]`, but `0x40000000` there is
only where that simulator's board loads its image, and the Technics thunk is built
for execution at `0x50000000` (`mov 0x50000001, d1` — the jmp's own address). The
driver uses `0x90000000`, the window the firmware writes through. Related and also
open: the sim puts NMI at base+8 while thunk 1 sits at +6, and the ROM padding is
`nop`-filled either way, so it arbitrates nothing.

Neither gap affects the driver, because only thunk 0 — offset 0 — is the maskable
vector, and offset 0 is invariant under any base. Parked for hardware in
`notes/HARDWARE-QUESTIONS-PENDING-FELIPE.md`.
