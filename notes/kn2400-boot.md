# KN2400 / KN2600 — boot derail analysis (in progress)

The KN2400/KN2600 drivers (they use the `kn7000` machine, so `m_lib_mirror = false`) **derail early at
boot**: the PC free-runs through zeroed RAM (`0x5018ccf4` → `0x51b2324e` → `0x539a7a4e` → …, incrementing).
The KN2400 is the *closest* KN7000 sibling (74 % string overlap, crt0 byte-identical to the KN7000's reset),
yet does **not** boot with the plain KN7000 machine.

## What was traced (fetch-ring + read/write taps, MAME lua)
- **Derail point.** Program code at `0x48728300` builds a **19-entry × 12-byte dispatch table** filled with
  **hardcoded RAM code pointers** (e.g. `mov 0x5018dfce, a1` at `0x48728301`), then at `0x4872833f` does
  `call 0x5018ccf4` — a hardcoded RAM address. SP is valid (`0x503813b0`); this is a clean call, not a
  stack smash.
- **That RAM is never loaded.** The only writes to `0x50180000–0x5018fffc` are the **BSS-clear loop**
  (`firstPC = 0x48705c98`, 16384 zero writes). No code is ever copied there, so `call 0x5018ccf4` executes
  zeros and the CPU runs off into garbage.
- **The library is NOT involved.** Before the derail the KN2400 reads **zero** bytes from `0x4C000000` and
  `0x8C000000`, and writes **zero** bytes to `0x8C`. So unlike the KN7000 (which self-loads its library into
  the `0x8C` libram) and the KN6000/KN6500 (which mirror the program ROM into `0x4C`/`0x8C`), the KN2400
  does not use the libram before this point. **The KN6000-style mirror does not fix it.**

## Working hypothesis — confirmed against the KN7000
A **~64 KB code overlay is meant to be resident in RAM at `0x50180000–0x5019xxxx`** (the hardcoded pointers
`0x5018ccf4` / `0x5018dfce` span that region). **The working KN7000 populates exactly this region**: a
write-tap over `0x50180000–0x5019ffff` on the booting KN7000 records **44036 non-zero writes spanning
`0x50180000–0x5018a964`, and the first one comes from PC `0x4c003046`** — a *library* copy routine (adjacent
to `LibMemCopy 0x4C003039` / `LibStrCopy 0x4C003051`). So the KN7000 order is: **(1) self-load the library
into `0x8C` → (2) call a library memcpy (`0x4c00304x`) to fill the `0x50180000` RAM overlay → (3) call into
that overlay.**

The KN2400 reaches step (3) (`call 0x5018ccf4` at `0x4872833f`) **without ever doing (1) or (2)**: zero
libram (`0x4C`/`0x8C`) reads *or* writes before the derail, and `0x50180000` only ever gets zeroed. So the
KN2400's **library self-load / overlay population is skipped or mis-ordered** — that is the real blocker, not
the dispatch table itself.

## NEXT
Find why the KN2400 skips the library self-load + overlay copy that the KN7000 does before `0x48728300`:
- The KN7000 self-loads its library via `InitializeBlock27 0x484D7BBD` (copies from program `0x487B8FD1`).
  For the KN2400 that source is **padding** (`0xFF`) — so if the KN2400 shares that loader, its library
  source must be **relocated** (find the KN2400's copy of that routine + its source/size).
- Trace the KN2400's crt0 up to `0x48728300` and see where its equivalent of steps (1)/(2) is — is it
  conditional on an unmodeled peripheral/flag (like the KN6000's tick-order derail), or does it copy to a
  different address? Compare the KN7000's caller of the `0x4c00304x` memcpy that first fills `0x50180000`.
Both drivers stay `MACHINE_NOT_WORKING` until the overlay is resident.
