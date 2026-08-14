# ⚠ CORRECTION 2026-08-14 — read this first

This note states that the KN2400 boot reads nothing from the table region
`0x48000000-0x483fffff`. **That is false.** A read tap held to t=30 s
(`tools/rigs/kn24_fontsrc.lua`) counts **164,300 reads, the first at t=0.84 s**, concentrated
at `0x48000000` (124,933 reads) and spread over `0x480000xx`-`0x48004Cxx`. The count is
identical across two runs, so it is deterministic, not a sampling artefact.

Consequences:
* The KN2400/KN2600/PR54 family **does** have a separate table/font ROM, and it is **undumped**
  — a device that was missing from the project's undumped inventory.
* The driver declares that region `ROMREGION_ERASEFF`, so every glyph fetch returns `0xFF` and
  text draws as solid filled cells. That is precisely the visible symptom: on the KN2400 the
  **icons render correctly** (the grand-piano glyphs in the part cells) while every run of text
  is a black bar. The blitter and compositor are fine; the font source is empty.
* This also explains the gate's liveness baseline for these two models — `distinct=4` with an
  identical screen hash, the lowest of any model.

The original text follows, retained for its other content.

---

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

  > **CORRECTION 2026-07-20 (CONVERT tick) — this is not a CODE overlay.** The copy is real and the
  > numbers are right, but the routine is `MemStyleAreaLoadFactory` **0x4843B15B** (the entry the callers
  > use is 0x4843B160; 0x4843b1a0 is a `bra` in the middle of it), and both ends are style data:
  > `0x50180000` is **MEM_STYLE_AREA**, the 0x25800-byte RAM "TCMP" style container whose extent is
  > hard-coded in `MemStyleAllocFits`, and the source is not a program-ROM code image but **table-ROM
  > segment 2** — `TableRomSeg02PtrSize` returns `0x48000000 + dir[2] = 0x48035D08` with length
  > `dir[3] - dir[2] = 0x40674 - 0x35D08 = 0xA96C`. That chunk starts with the ASCII bytes `TCMP`, carries
  > allocator top `0x00A969` (hence the write span ending at `0x5018A964`), N = 3, and the three factory
  > style names " Easy 8 Beat ", "Easy 16 Beat ", " Easy Swing  ". Nothing calls into `0x50180000`.
  > The full writer contract is in kn7000_disassembly/kn7000_manual.sym.
  >
  > **Consequence for the KN2400 investigation:** "the KN2400 never populates its code overlay" is not a
  > boot blocker — the missing copy is the factory *style* container, which a keyboard can boot without.
  > The `0x50180000` write-tap is a red herring here; the derail has to be looked for elsewhere. (The
  > **library self-load** finding above is unaffected and still real.)

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

## Correction 2026-07-09 — the table ROM is NOT read at boot; no table-data disk exists
A read-tap over the ENTIRE table region (`0x48000000-0x483fffff`) shows the KN2400 reads **nothing** from it
in 3 emulated seconds of boot. So:
- The "empty table ROM" lead above is **refuted** — it is not the derail cause. The ~1951 static references
  to that range are later-feature resources (sound/graphics banks, `0x48080000`/`0x48100000`/…) never
  reached before the derail, or non-pointer data — not boot-critical.
- The derail remains a **program-ROM boot-flow** issue: the missing library self-load + overlay-copy before
  the object-init (`0x48728165`, reached by the main boot at t≈0 with a fresh stack).

### Answer to "table-data disk vs KN7000 ROM reuse" (user question, 2026-07-09)
- **No initial-data / table-data disk ships** for the KN2400/KN2600. `kn24-11.zip` = `kn24_11a.exe` +
  `kn24_11b.exe` (the two program halves → `KN24PRG.DAT`) + install.pdf; `kn26-11.zip` = `KN24PRG.DAT` +
  install.pdf; `KN2600_CD-Rom.zip` is just **PC MIDI drivers** (`mamidi.sys`, `.inf`, installers), not data.
- **The KN2400 boot does not read any table ROM** (its own or the KN7000's), so the boot does not depend on
  cross-model ROM reuse. The derail is entirely within the program ROM.

### Cross-model ROM reuse — INTEGRITY POLICY (per the user, 2026-07-09)
If, for *later* features (sound/graphics), we ever fill the KN2400's undumped WAVE / table mask ROMs by
reusing another model's ROM (e.g. the KN7000's), that must be **documented explicitly as an unverified
emulation hack UNTIL proven a technical fact** — verified from the **service manual / physical chip part
numbers** showing the KN2400 and KN7000 use the same mask ROM part. We must NOT silently present a
cross-model substitution as if it were the device's real ROM, to avoid misrepresenting these keyboards'
technical history. (Known real sharing: KN2400/KN2600/PR54 share ONE program firmware — that IS a fact.
KN2400↔KN7000 chip sharing is currently UNVERIFIED and would need the service manual.)

## ✅ RESOLVED 2026-07-20 — KN2400/KN2600 BOOT TO THEIR PLAY SCREEN

The whole "skipped library self-load / overlay copy" mystery had a one-line root cause in the
DRIVER's memory map, found by searching for the copy BY CONTENT (as planned) instead of by address:

**Mechanism (static RE).** The block-loader is a byte-for-byte relocated twin of the KN7000's
`InitializeBlock27` copy engine, at KN2400 **`0x4870587E`** (right next to the crt0 at `0x48705bdf`).
It walks a 12-byte-record descriptor list whose base is hardcoded as byte-pointers in the loader
prologue — KN2400 **`0x487965BB`** (found via LE-u32 references to the descriptor's byte addresses).
Record layout `{u16 flags, u16 len16, u32 src, u32 dest}`, stride 0xC; when flags bit15 is clear the
copy length = next record's src − this src; flags bit15 marks the final record, whose 3-byte payload
`de 00 00` (= `retf`) is planted at the window end as a sentinel. The loader's dest adjust
(`cmp 0x80000000 / add 0x40000000`) sends every dest below 0x80000000 through the **+0x40000000
alias**. Descriptor tables live at the very END of each program image:
- KN7000 (`D=0x487F6EE9`): 1 record — ROM `0x487B8FD1` (len 0x3DF15) → `0x4C000000` (phys 0x8C000000,
  the libram) + sentinel at `0x4C03FFF0`.
- KN2400 (`D=0x487965BB`): 1 record — ROM `0x487285BE` (len 0x23DFA) → **`0x50120000`** (phys
  **`0x90120000`**) + sentinel at `0x5018FFF0`. The payload disassembles as clean MN10300 code linked
  at 0x50120000 (starts with the same soft-float libm as the KN7000's library at 0x4C000005). So the
  KN2400 self-loads its library INTO WORK RAM — it never touches 0x4C/0x8C (matching every earlier
  zero-libram trace), and 0x90000000..0x903fffff must be the +0x40000000 write/execute alias of the
  0x50000000 work RAM.

**Driver root cause.** `maincpu_mem` mapped `0x90000000-0x97ffffff` as a SEPARATE `vram` share. The
self-load DID run every time — its 147 KB landed in the vram share at 0x90120000, while execution
read zeros from workram 0x50120000 → `call 0x5018ccf4` into cleared RAM → the free-running derail.
(All the old write-taps watched 0x50180000/0x8C — nobody watched 0x90120000.)

**Fix.** New `kn2400` machine config (`m_ram90_workram`): `map(0x90000000, 0x903fffff).ram()
.share("workram")` + maskable vectors → trampoline slot 0x90000000 (KN6000-style). With the alias in
place the boot self-loads, populates the whole 0x5012xxxx-0x5018xxxx region (later stages fill past
the initial copy), the RTOS comes up multitasking, and the firmware paints its play screen.

**Display.** The KN2400/KN2600 panel is a **320x240 FOUR-LEVEL GRAYSCALE LCD**: the firmware
composites a 2bpp framebuffer at **`0x9C800000`** (stride 80 bytes, MSB-first pixel pairs,
0 = lightest). Found empirically by scanning the 0x9C bank for content and decoding candidates.
`screen_update` gained an `m_lcd_kn24` path (320x240, 2bpp decode); the play screen (title bar,
menu bars, 8 sound-group tiles with instrument icons) renders for BOTH kn2400 and kn2600
(snapshot-verified). Like the KN6000/KN6500, TEXT does not render yet (same class of problem —
see notes/kn6000-kn6500-boot.md); icons and screen structure are real firmware output.

Regression: kn7000 reverb oracle **bit-identical c3b67ea711ce3c00f8ae2af1e07651cb**, kn6000 play
screen unaffected, `-validate` clean. ROMs: the split even/odd images (CRCs already in the driver)
are generated from `kn7000_scratchpad_snapshot/kn2400_full.bin` (LKG1+LKG2 concatenation).
