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

## Update — the KN7000 mechanism is nailed down; the KN2400 is heavily relocated
Traced the KN7000's two prerequisite copies concretely (write-taps + caller rings):
- **Library self-load.** A copy loop at `~0x484d7b90` (the KN7000's `InitializeBlock27` region) copies
  program ROM **`0x487b8fd0`–`0x487f6ee6`** (~253 KB) → **`0x8c000000`** (the libram). This makes the
  library functions (e.g. `LibMemCopy 0x4c003039`) executable.
- **Overlay populate.** A block-copy helper at `~0x4843b1a0` calls `LibMemCopy(dest=0x50180000,
  src=program-ROM 0x48035d08, len=0xa96c)` — the ~43 KB RAM overlay's *content lives in the program ROM*;
  the copy just needs the library loaded first. So the KN7000 order is **self-load library → copy overlay →
  use overlay**.

**The KN2400 is heavily relocated**, so KN7000 addresses do NOT transfer: at file offset `0x484d7b60` the
KN2400 is only **7/112 bytes** identical to the KN7000 (it's INTC/GxICR init code there, not the block
loader). So the KN2400's self-loader and overlay-copy are at unknown, relocated addresses — this is why the
KN2400 dig is slower than the KN6000 (which reused `kn7000_state` at the same offsets).

Confirmed: by the derail the KN2400 has done **neither** copy — 0 non-zero writes to `0x50180000`, 0 libram
reads/writes — yet it reaches the overlay *use* (`call 0x5018ccf4` at `0x4872833f`). So either its boot
takes a wrong/early path into `0x48728300` (a derail, like the KN6000's SP=0), or the self-load/overlay copy
is gated on something unmodeled and skipped.

## NEXT (fresh dedicated tick)
1. Find the **caller** of the KN2400 function containing `0x48728300` — is it reached legitimately or via an
   early derail? (Trap its entry; the table-build loop swamped a 40-deep ring last time — trap earlier.)
2. Locate the KN2400's **relocated self-loader + overlay-copy** by *content*, not address: search for the
   copy that targets `0x8c000000` / `0x50180000`, or the block-descriptor holding the overlay's ROM source
   (the KN7000's is `src=0x48035d08,len=0xa96c` → the KN2400's src is relocated but the `dest=0x50180000`
   and structure should match). Then see why it doesn't run before `0x48728300`.

## Update — the object-init is reached LEGITIMATELY; overlay-load is a missing EARLIER step
Trapped the first entry into the `0x48728xxx` region: PC `0x48728167` (the function entry), reached via a
clean call chain **`0x485e4258` → `0x48728590` → `0x48728165`** with a valid SP (`0x503813e8`) — **not a
wild derail**. The entry (`0x48728167`) only builds RAM tables (`0x50380000`/`0x50380030`/`0x503807xx` set
to `-1`); it does **not** self-load the library or copy the overlay. So the library self-load + overlay copy
are **separate, earlier boot steps that the KN2400 skips** before it legitimately reaches this object-init
and calls the (unloaded) overlay method `0x5018ccf4`.

Ruled out: the **mirror won't help** — the overlay copy is never *called* (0 non-zero writes to
`0x50180000`, 0 libram reads), so providing the library via a mirror changes nothing pre-derail.

NEXT (fresh dedicated tick): trace the boot from the crt0 forward — where is the KN2400's self-load /
overlay-copy step, and why is it skipped/reordered? Start from the top of the caller chain (`0x485e4258` and
its callers) and find the KN7000-analogous "load blocks" pass. Slower than the KN6000 because every address
is relocated; budget it as its own investigation rather than interleaving.

## Update 2026-07-09 — ruled out interrupts; robust tooling; object-init is main-boot at t≈0
**Tooling fix** (last tick's traces hung): use `-seconds_to_run N` (MAME's clean built-in exit) and have
the lua **write findings to a file** instead of `manager.machine:exit()` + `timeout` (which failed to kill
MAME). Also avoid tapping the `0x90000000` LCD-window (expensive). This combination runs reliably.

**Ruled out — interrupt hypotheses:**
- The driver vectors KN2400 IRQs to the KN7000 library handlers `0x4C03DE26`/`0x4C03DDA0`, but a tap on
  `0x4C03DD00-0x4C03DEFF` shows the CPU **never fetches there** in 3 emulated seconds → no IRQ-into-empty-
  library.
- The object-init `0x48728165` (which calls the un-loaded overlay) is entered at **t≈0.0000 with a FRESH
  ZEROED STACK** (SP=`0x503813e8`, `*(SP..SP+0x44)`=all 0) → reached by the **main boot via jumps from the
  crt0**, NOT an interrupt preemption.

**So:** the library self-load + overlay-copy that the KN7000 performs *before* its object-init are simply
**absent/skipped from the KN2400's early boot path** — not preempted, not mis-timed.

**New lead — empty table ROM:** the KN2400 driver leaves the `table` region (`0x48000000`) `ROMREGION_ERASEFF`
(no dump), yet the firmware references `0x48000000-0x483fffff` ~**1951 times** with round bank addresses
(`0x48080000`, `0x48100000`, `0x481f0000`, …). The KN2400 may need a separate table/mask ROM that is
**undumped** (memory's "no separate table flash" may be wrong), or map resources differently. Its
`TCMP`/`Technics` resources ARE present in the *program* ROM (`0x484c6853`, `0x4852bc20`, …).

**NEXT:** trace the KN2400 crt0's jmp target (boot2) forward to `0x48728165` and find where the KN7000 does
its `InitializeBlock27` self-load + overlay-copy — the KN2400's relocated boot2 either omits or short-
circuits it. (The KN2400 crt0 jmp target differs from the KN7000's `0x487f7793`, which is padding for the
smaller KN2400 image.) Also decide the table-ROM question: is a mask/table ROM undumped, or unused?
