# Library ROM API (`0x4C000000`)

> **CORRECTION (superseded):** this ROM is **not undumped**. The boot **loads it
> at runtime from the program flash** into a RAM window aliased at `0x8C000000`
> (`0x4C000000 + 0x40000000`) — see [`library-rom-loading.md`](library-rom-loading.md).
> The used range is ~253 KB (298 entry points, max `0x4C03DE26`), all present in
> `kn7000_program.rom`. The API catalogue below is still useful, but the premise
> "separate undumped ROM, ≥ ~6 MiB, blocked on a hardware dump" is wrong.

The application firmware (`kn7000_program.rom`, mapped at `0x48400000`) is only
half of the code: it calls heavily into a **separate ROM at `0x4C000000`** that
is **not contained in the system-update floppies** and has not been dumped. This
note tabulates the firmware's dependency on it — i.e. the API surface that a
hardware dump would need to cover, and that MAME emulation is blocked on.

* **7923 calls / jumps** into the library ROM
* **298 distinct entry points**
* entry-point range `0x4C000005` .. `0x4C03DE26` → the ROM is at least **~1 MiB**

The call-site argument patterns show this ROM holds the **C runtime + MILK
kernel** — the standard-library primitives the application is built on. The
most-used entry points (inferred purpose from how their arguments are set up):

| entry point | calls | inferred purpose |
|-------------|-------|------------------|
| `0x4C001A48` | 1201 | printf/sprintf-family (multiple stack args + format-string pointer) |
| `0x4C0019D5` | 1107 | numeric formatter (value in d0, width/base in d1) |
| `0x4C003051` | 1034 | memory/string copy (a0=dest, a1=src pointers) |
| `0x4C0149FA` | 1008 | table/object accessor (d0=id/offset stepping by 0x10, d1=0) |
| `0x4C003039` | 488 | string/mem helper (near 0x4c003051) |
| `0x4C014A56` | 197 | — |
| `0x4C003024` | 185 | — |
| `0x4C0032F7` | 182 | — |
| `0x4C000B1C` | 142 | — |
| `0x4C000879` | 125 | — |
| `0x4C03DD74` | 115 | — |
| `0x4C014948` | 97 | — |
| `0x4C0039EB` | 97 | — |
| `0x4C000593` | 93 | — |
| `0x4C003987` | 92 | — |

**Implication for emulation:** with 7,900+ calls into it, the machine cannot
boot in MAME until this ROM is dumped (or the hottest entry points are HLE'd).
The `mn10300_sim` interpreter confirms this: the boot runs 3.06 M instructions
and then reaches a `call` into `0x4C0…`, which it cannot execute.

The full list of 298 entry points is in `library-rom-entrypoints.txt`.
