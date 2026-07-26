# KN5000 IC303 HLE — the HONEST VOICE LIFECYCLE (design for GAP LIFE-1 + LIFE-2)

Author: autonomous design pass, 2026-07-26. Requested by Felipe Sanches.
Scope: (a) when a voice must report SILENT in the 0x100000 active-voice bitmap; (b) whether a
deterministic note-off signal exists at the chip boundary; (c) what the HLE owes the firmware's
voice allocator/stealer. Plus the safety argument that a held note cannot be reclaimed.

Status: **DESIGN ONLY — no code changed in this pass.** Rules are stated so they can be
implemented and measured independently of GAP CAL-1, with the one CAL-1 dependency isolated and
named (§7).

Evidence labels: **MEASURED** (read from the disassembly bytes, the ROM, or a live capture),
**INFERRED** (deduction from measured facts), **SPECULATIVE** (unproven).

Sources
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`.
  `LABEL_02XXXX` = runtime address in decompressed sub RAM; that address *is* the citable
  anchor (the program does not execute in place), so citations are `asm L<line> / LABEL_02XXXX`.
* HLE `kn7000_mame/src/mame/matsushita/kn5000_tonegen.{cpp,h}`.
* Live captures from the voicelife audit, re-analysed here:
  `notes/audit/data-voicelife/voicelife_trace.txt` (bus trace around one held C4),
  `notes/audit/data-voicelife/voicelife_alloc.txt` (power-on → 5 notes + a chord).

---

## 0. The one architectural fact everything follows from

**IC303 has no note-off input.** Its voice-control register (+0x000) accepts exactly two
lifecycle commands — `0x81xx` = GATE ON and `0x7E00` = VOICE FREE — and everything between them
is envelope programming. A key release is delivered to the chip *only* as "here is a new
(target, rate) for the amplitude EG". The chip cannot tell a release from any other envelope
stage change, and **it is not supposed to**.

Consequently the firmware learns that a note has ended by **asking the chip**, and the reply is
the 0x100000 bitmap. That closes a loop the HLE currently breaks:

```
  firmware GATE (0x8100)  ──►  chip runs the EG  ──►  EG reaches zero
        ▲                                                    │
        │                                          chip drops its bitmap bit
        │                                                    │
        │              LABEL_02219F sees the 1→0 edge  ◄──────┘
        │                          │
        └── channel returns to the free list ◄── LABEL_02B4A1 writes 0x7E00
                                        LABEL_021E31 retires the node
```

**MEASURED, `voicelife_alloc.txt`:**
```
12.481481  R 0000 0000     <-- status_r finally returns 0 for bank 0
12.481537  W 0000 7E00     <-- 56 us later: teardown of ch0
12.481599  W 0001 7E00     <-- and ch1
```
The 0x7E00 is emitted immediately after, and only after, the bitmap read returns 0. The HLE's
`status_r()` return value is the *sole* thing that decides when the firmware reclaims a voice.

The existing code comment at `kn5000_tonegen.cpp:349` states the opposite — that a handed-off
voice "can never" get a 0x7E00 — and that comment is **wrong**: the 0x7E00 comes back, but only
if we report the silence that earns it. **That single misconception is GAP LIFE-1.**

---

## 1. The firmware's teardown decision, exactly (MEASURED)

`LABEL_02219F` (asm L13273) runs one bank of 16 channels per audio tick:

```
b    = ++(0x1128) & 3
HL   = DAC_Write_Sample(b)                     ; L13280  write 0x100000 = b, read 0x100000
new  = cmd_bitmap[0x2936 + 2b] | HL            ; L13284-13288
tmp  = (new ^ prev[0x292E + 2b]) & prev        ; L13291-13302  = prev & ~new
prev[0x292E + 2b] = new                        ; L13304-13308
for i in 0..15:  ch = 16b + i
    if tmp bit i and !(node[+0x22] bit0):      ; L13327
        LABEL_021E31(node)                     ; L13324  retire the node -> free list
        LABEL_02B4A1(ch)                       ; L13327  +0x0C0+ch = 0x0000 ; +0x000+ch = 0x7E00
        LABEL_02150D(ch)                       ; L13330
    else if !(node[+0x22] & 0x81):
        node[+0x25] = (READ(0x0180+ch) & 0x3FFF) >> 5      ; L13337-13344
        if node[+0x25] < 0x80 and node[+0x22] bit2:
            LABEL_021E83(node)                 ; L13350  demote to the steal-me-first list
```

Three properties of that code are load-bearing:

**P1 — the teardown is EDGE triggered.** `tmp = prev & ~new`: the bit must have read 1 on the
previous poll of that bank and 0 now. A bit that is 0 and stays 0 never tears anything down.
(asm L13291-13302.)

**P2 — `new` is `cmd_bitmap | chip`, and for ORDINARY voices `cmd_bitmap` is ZERO.**
`LABEL_022340` (the allocator, asm L13451) takes two branches at allocation:

| branch | asm | `node[+0x22]` | `cmd_bitmap[0x2936]` | `prev[0x292E]` |
|---|---|---|---|---|
| request byte `req[6+i]` bit7 SET | L13534-L13549 | `0x88` | **bit SET** (keep-alive) | untouched |
| bit7 CLEAR | L13551-L13584 (`LABEL_022444`) | `0x08` | **bit CLEARED** | **bit PRE-SET** |

The second branch *pre-arms the edge detector at allocation*: `LDA XBC, 292Eh / OR (XBC+WA), DE`
(asm L13582-L13584). So for a chip-managed voice, **from the instant it is allocated, the very
first poll of its bank that reads 0 tears it down.** There is no grace period and no firmware
keep-alive.

**P3 — the keep-alive, where it exists, is dropped early.** `LABEL_022587` (asm L13694-L13724) is
"hand this voice over to the chip": `RES 7,(0x14AF + ch*0x27)` (asm L13700) (= `node[+0x22]` bit7, so
0x88 → 0x08), then `cmd_bitmap &= ~bit` (asm L13717), then tail-jump to `LABEL_021EA1` (asm L13724). It is called from
**ten** sites, and MEASURED on the bus the hand-off happens ~0.6 ms after the gate for a key-bed
note (`+0x000 = 0xF0FF` at 12.006603 vs the gate at 12.006012, `voicelife_alloc.txt`).

> **Design consequence, and it is the whole reason this design is conservative:**
> a held key-bed note has, for essentially its entire life, **no firmware protection at all**.
> The safety of held notes therefore MUST NOT be built on the firmware's keep-alive. It must be
> a property of what the HLE reports. §4 builds it that way.

**MEASURED poll cadence** (`voicelife_trace.txt`, e.g. 11.523011 / 11.547589 / 11.572173 /
11.596730): one bank read every **24.58 ms**, so each bank is polled every **98.33 ms**. That is
the worst-case teardown latency after a voice truly goes silent, and it is also the natural time
constant for the R2s interlock below. (Consistent with `Audio_Process_Init`, asm L38150-L38160, which
alternates `LABEL_027A46` and `LABEL_02219F` on successive calls, toggled by `(0x041342) ^= 0xFF`.)

---

## 2. LIFE-1, MEASURED in one line pair

`voicelife_alloc.txt`, every write to channel 0's control register in a 17-second session:

```
4.066129   W 0000 8100      <-- boot self-test gate
4.066628   W 0000 1200
4.066771   W 0000 7E00      <-- self-test frees it
5.859349   W 0000 8100      <-- a real voice is gated on ch0
5.859385   W 0000 F000      <-- ...and handed off to the chip (bare command, no magnitude)
                            <<< NO 0x7E00 — for 6.15 seconds >>>
12.006012  W 0000 8100      <-- ch0 RE-GATED for the C4 key press
12.006603  W 0000 F0FF
12.481537  W 0000 7E00
```

Between 5.859385 and 12.006012 the firmware never freed channel 0, because our `status_r`
(`kn5000_tonegen.cpp:352-360`) reports `key_on`, and a handed-off voice's `key_on` is never
cleared (no release burst ever arrives for it — nothing arrives for it at all). The node stayed
allocated, the free list did not refill, and the allocator eventually **re-gated a channel the
firmware still believed was sounding**. That is GAP LIFE-1, MEASURED, with no inference.

The brief's framing ("allocation runs 0..63 then wraps") is **partly a miss** — see the
predict-then-check log, §8 — but the mechanism is exactly as described and the population it
affects is the accompaniment/rhythm/handed-off voices, which is the majority of a playing
instrument's channel demand.

---

## 3. (a) THE RULES — when a voice reports SILENT

### R0 — decode the latch; do not mask it to 2 bits
`status_r` currently does `int bank = m_addr_latch & 0x03;` (`kn5000_tonegen.cpp:352`). The
firmware issues **two different reads** through the same port (asm L13280 and L13341):

| latch | meaning | HLE must return |
|---|---|---|
| `0x0000..0x0003` | active-voice bitmap of bank *n* | bit *i* = `sounding(n*16 + i)`, i.e. **R1** |
| `0x0180 + ch` (ch 0..63) | that voice's current envelope level | `(level8(ch) & 0xFF) << 5` |
| anything else | not issued by v142 | `0` |

`level8` = the voice's current amplitude-EG magnitude scaled 0..0xFF, **0 when not sounding**.
The firmware keeps `(V & 0x3FFF) >> 5` truncated to 8 bits and only ever compares it against
`0x80` (asm L13341-13346), so the map must be **monotone**, not exact. MEASURED today: latch
0x0180 returns 0x0003 and latch 0x018C returns 0xFC00 — bank bitmaps answering a level query.

### R1 — what "active" means: `eg_running`, a LATCH, not a level test
Bit *i* of the bank bitmap is 1 **iff** the voice's `eg_running` latch is set. The latch is:

* **SET** by `+0x000 = 0x81xx` (the gate). Only by that. (asm L29757, L30213, L30294, L30667,
  L30891, L31071, L31086.)
* **CLEARED** by `+0x000 = 0x7E00` (the free command, `LABEL_02B4A1` asm L26793).
* **CLEARED** when the amplitude EG TERMINATES — rule **R2**.
* changed by **nothing else**. In particular no write to groups 8/9/10 may set or clear it.

Why a latch and not "is the output nonzero right now": by **P2** the edge detector is pre-armed
at allocation, and by the pre-mute (§6) the EG level at gate time is at the floor. A rule that
answered "is it loud yet" would report 0 on the poll immediately after the gate and the firmware
would tear the brand-new note down within one bank period. The latch makes the bit **1 from the
gate**, which is what a hardware EG's run/idle flag does.

### R2 — EG termination
`eg_terminated` (and hence `eg_running := false`) at the first sample where **all** of:

1. the amplitude EG's **current level has reached the floor**, and
2. the amplitude EG's **current target is at or below the floor** — i.e. it has *converged*, not
   passed through zero on the way up, and
3. **[R2s, the calibration-independent interlock]** the voice's rendered contribution to the
   output has rounded to **zero in the 16-bit output** (|contribution| < 0.5 LSB) continuously
   for one full bank-poll period, **98.33 ms** (MEASURED, §1).

Condition 3 is not a tuning knob: 0.5 LSB is the output quantum and 98.33 ms is the measured
poll period. Its only job is to make the rule safe *before* GAP CAL-1 is settled (§7).

Conditions 1+2 are stated on the *rendered gain*, not on a register byte, precisely so that the
rule survives whatever CAL-1 concludes: **"floor" means the level code at which the HLE's own
level→gain law returns gain 0.**

### R3 — an EG write NEVER re-arms and NEVER resets
Writes to groups 8/9/10 (+0x800/+0x840/+0x880/+0x8C0/+0x900/+0x940/+0x980/+0x9C0/+0xA00/+0xA40)
load a new (target, rate) and nothing else. They must not touch `eg_running`, must not reset the
wave pointer, and **must not reset the EG's current level** — the ramp continues from where it
is toward the new target.

*Predict-then-check:* this rule makes commit d3457eb's hand-coded "release starts from the HELD
level" an **emergent** property rather than a special case, and it removes the double-release
bug (audit GAP 1) without a `key_on` guard, because there is no `process_key_off` left to call
twice. Predicted before writing this section; confirmed by re-reading `process_key_off`
(`kn5000_tonegen.cpp:1495-1519`), whose entire body — the `!v.key_on` idempotence guard, the
2400-sample release counter, the 4800-sample hold counter — is subsumed.

### R4 — the gate is an unconditional FULL re-initialisation
`+0x000 = 0x81xx` resets, regardless of the channel's previous state: wave pointer to 0, EG to
segment 0 with its current level wherever the preceding writes left it, filter state cleared,
`eg_terminated = false`, `eg_running = true`. **No per-voice state may survive a gate.** This is
what makes voice stealing clean (§6) — a stolen channel is re-initialised, never left ringing.

### R5 — `0x7E00` is a hard stop, not a release
Output goes to zero on the same sample; `eg_running = false`, `active = false`, wave pointer
cleared. It is the firmware's *reply to our own silence report*, so by construction the voice is
already silent when it arrives and the stop is inaudible (§4). It must not start or restart a
fade — today it calls `process_key_off` (`kn5000_tonegen.cpp:236-240`), which is what produces
the +10 dB re-onset the amplitude audit measured.

### R6 — the "silencing" register pairs are ordinary EG programs
`+0x840 = 0xFF00 / +0x800 = 0xFF80` (channel pre-reuse), `0xA200 / 0xA280` (panic), and the
release burst are **not** special commands; they are (target, rate) loads and R3 handles them.
What must NOT happen is the current behaviour, where `update_voice_params`
(`kn5000_tonegen.cpp:507`) reads `0xFF80`'s high byte as "maximum volume" and slams the channel
to full scale 386 µs before it is re-gated. Resolving which byte is the target is CAL-1's job
(§7); the lifecycle only requires that the pre-reuse pair end up rendering as *silence*.

### R7 / R8 / R9 — deletions
* **R7.** Delete the release heuristic (`kn5000_tonegen.cpp:275-279`) and `process_key_off`
  entirely. See §5 — there is nothing to replace it with, and nothing needs replacing.
* **R8.** Delete `hold_counter` and `release_counter` (`kn5000_tonegen.h:102-103`). Both are
  superseded by the EG; `hold_counter`'s stated rationale ("ensures a few poll cycles see the
  voice as active") is already false — `status_r` never reads it.
* **R9.** Leave `data_r()` returning what it returns. **MEASURED: the firmware never reads
  0x100002** — 263 reads in `voicelife_trace.txt`, 100 % at 0x100000. Do not invent semantics
  for a port that is never read.

---

## 4. THE SAFETY ARGUMENT — a held note cannot be reclaimed

The claim to defend is the MUST-NOT-REGRESS invariant: *a held key must sustain for as long as
the key is down, and an honest `status_r` must not let the firmware take it away.*

**Lemma 1 (edge).** A teardown of channel *ch* requires the OR-bitmap bit for *ch* to have read
1 on one poll of its bank and 0 on the next. (asm L13291-13302, property P1.)

**Lemma 2 (no firmware shelter).** For a chip-managed voice the firmware contributes 0 to the
OR and has pre-armed `prev` (asm L13551-L13584, property P2); for a keep-alive voice the shelter
is dropped ~0.6 ms after the gate (asm L13694-L13724 `LABEL_022587`, MEASURED at 12.006603). **The
design may not rely on firmware protection, and it does not.**

**Lemma 3 (Silence-Honesty).** Under R1+R2, if the bitmap bit for *ch* reads 0 then the HLE's
contribution of *ch* to the output is exactly 0 at that instant, and remains exactly 0 until the
next register write to *ch*.
*Proof.* The bit reads 0 only when `eg_running` is false. `eg_running` is false only (i) before
any gate — no wave, no output; (ii) after `0x7E00` — R5 zeroes the output; or (iii) after R2
fired. In case (iii), R2(1) puts the EG level at the floor, R2(2) puts the target at or below
the floor so the ramp cannot climb without a new register write, and R2s(3) independently
certifies that the rendered samples have been rounding to zero for 98.33 ms. In all three cases
the contribution is 0 and stays 0 absent a new write. ∎

**Theorem.** *A firmware teardown can never remove audible sound.*
*Proof.* By Lemma 1 a teardown happens only on a poll where the bit reads 0. By Lemma 3 the
channel's contribution is then exactly 0. The teardown's own bus effects are `+0x0C0 = 0x0000`
and `+0x000 = 0x7E00` (asm L26780/L26793), both of which set a channel that is already emitting
zero to emit zero. No sample changes. ∎

**Corollary A — a sustaining voice is unreclaimable.** While a key is down, the amplitude EG sits
in the segment whose target is the patch's sustain level. If that target is above the floor,
R2(2) is false forever, `eg_running` stays set forever, the bit never drops, and by Lemma 1 no
teardown can ever fire — for any hold duration. The sustain is **structurally** safe: it does
not depend on a timer, a threshold, or the poll rate.

**Corollary B — a decaying voice is freed at the right time, and inaudibly.** A Piano note held
for 20 s decays to silence and is then freed. That is what the real instrument does (the
firmware has no other way to recover the channel), and by the Theorem the free itself is
inaudible.

**The honest limit of the argument, stated plainly.** The one way this design could shorten a
held note is if GAP CAL-1's calibration makes the amplitude EG converge to the floor *too
early*. But that is a **calibration** defect, not a lifecycle defect: a too-fast decay is
audible **as a decay, before any teardown can occur**, because R2s requires the output to have
already been at zero for 98.33 ms. The lifecycle rule cannot create such a regression; it can
only expose one that the calibration already contains. This is the precise sense in which
LIFE-1 is "coupled to CAL-1", and the coupling is one-directional.

**Regression gate (measure this, do not assert it).** Render a 30-second held C4 on Piano
before and after the change and compare sample-by-sample. Pass = the two renders are
bit-identical up to the first teardown, and the residual after the teardown is < 1 LSB.
A criterion that cannot fail is not a pass: this one fails loudly if R2 fires while the voice is
still audible, which is exactly the risk being guarded.

---

## 5. (b) THE DETERMINISTIC NOTE-OFF SIGNAL — verdict: **THERE IS NONE, AND NONE IS NEEDED**

### 5.1 The heuristic is not equivalent — disproof
The current detector (`kn5000_tonegen.cpp:275-279`) fires `process_key_off` on any `+0x900`
write to a keyed-on voice more than 1 ms after its gate. `+0x900` in that position is written
only by `LABEL_02D436` (asm L29936; its six writes are `+0x840, +0x940, +0x0A00, +0x800,
+0x900, +0x9C0` from the shared scratch block at 0x0451CC, offsets +0x2e/+0x32/+0x36/+0x2c/
+0x30/+0x34). So the question reduces to: *is `LABEL_02D436` reached only on note-off?*

**No. MEASURED counter-example, from the disassembly:**

```
Voice_CC_Portamento      asm L25150      ; a CONTROL CHANGE, keys still down
  └─ LABEL_02CCD3        asm L29116      ; query {mode 0x80, key (part<<8)|0x80, mask 0x007F}
  │                                      ; = "every channel of this part"
  └─ Voice_ParamInit     asm L25175 / L29344
       for each channel in the list, dispatch on chan[+0x01] & 0x3C   (asm L29361-29372):
         0x20 -> LABEL_02CD71  (asm L29405)  ──┐
         0x10 -> LABEL_02CED5  -> LABEL_02D436 │
         0x08 -> LABEL_02CE4C  -> LABEL_02D436 │  all reach the SAME six writes
         0x04 -> poke chan[+0x2f]/[+0x31],     │
                 or LABEL_02CD71 (asm L29387) ─┘
```
A portamento controller move on a part whose keys are held therefore re-emits the six-write
burst on **every sounding channel of that part**, with the keys down. Under the present
heuristic every one of those notes is force-released. (**MEASURED** for the call chain; the
audible consequence is **INFERRED** — no capture exercises portamento yet, and that is the
obvious confirming experiment.)

The same routine `Voice_ParamInit` is the *note-off* service too (asm L29469, inside
`Voice_NoteOn`'s velocity-0 branch `LABEL_02CFE7` at asm L29463-29477). One routine, both
duties. There is nothing in the register stream that distinguishes them.

### 5.2 The `+0x840 → +0x940` adjacency signature is also not a note-off
Audit GAP 5 proposed treating "a `+0x940` write whose predecessor on the same channel was
`+0x840`" as the deterministic release. That signature does correctly and uniquely identify
`LABEL_02D436` (verified against all nine register writers, audit §1.1) — but §5.1 shows
`LABEL_02D436` itself is not note-off-specific. **The signature is exact for the wrong thing.**
It identifies "the EG program was replaced", which is precisely what the chip sees and precisely
what carries no note-off information. **This is a reported miss** (§8).

### 5.3 Note-off does not even reliably *produce* a register write
`Voice_ParamInit`'s `0x04` branch (asm L29372-29386) responds to a note-off by setting
`chan[+0x2f] |= 0x0080` — arming a **countdown**, not writing a register. `LABEL_026E5B`
(asm L21467) then decrements it once per `LABEL_027A46` tick (24.58 ms) and only calls
`LABEL_02CD71` when the low 7 bits reach zero (asm L21491-21503). So for those voices the key
release produces **no bus activity at all** for up to 127 ticks (~3.1 s). Any detector keyed on
"a write happened" is structurally unable to see those note-offs.

### 5.4 And a note-off can arrive as a *hard mute* instead
For tone records whose class byte satisfies `p[+0x10] & 0xC0 == 0x40`, `Voice_NoteOff`
(asm L28606, guard at L28618-L28621) responds to a key release with `+0x840 = 0xFF00`,
`+0x800 = 0xFF80`, then `+0x000 = chan[+0x2d]` (asm L28663-L28700) — the *same* pair that
`Voice_SetPitch` (asm L28560/L28578) writes at note-**on**. So the identical two-word sequence
means "release this note" in one context and "mute the channel I am about to re-gate" in the
other. Three different note-off deliveries, none distinguishable, one of them silent.

### 5.5 Verdict
**DELETE, do not replace.** There is no deterministic note-off signal at the chip boundary
because IC303 has no note-off concept; the firmware's note-off is entirely an internal state
change (`LABEL_022587` clearing `node[+0x22]` bit7 and the `cmd_bitmap` bit, asm L13694-L13724),
and reading it would be a chip-boundary violation. The HLE must model the chip: gate, EG,
terminate, free (R1-R5). Once it does, "note-off" is not a thing the HLE needs to know, and
the heuristic's failure modes (§5.1-§5.4) all disappear because there is no detector left to
fail.

This is a **stronger** result than fixing the heuristic: the heuristic is not merely imprecise,
it is answering a question the interface does not pose.

---

## 6. (c) VOICE ALLOCATION AND STEALING

### 6.1 The firmware's allocator (MEASURED, for the record — the HLE must not model it)
`LABEL_022340` (asm L13451) allocates by taking the **head of the first non-empty list** in a
per-class search order (`LABEL_02229A` asm L13367, class table at 0x0F633 + class*6; a nonzero
override at 0x1345 pins a specific node). Nodes are 0x27-byte records at `0x148D + ch*0x27` on
doubly-linked lists (`LABEL_021C83` / `021D59` / `021E02` / `021E15`, asm L12850-12915); the
node index is the channel, and `node[+0x24]` holds the channel number.

`node[+0x22]` is the state machine:

| value | meaning | set by |
|---|---|---|
| `0x88` | active, firmware keep-alive (`cmd_bitmap` bit set) | alloc, asm L13534 |
| `0x08` | active, chip-managed (`cmd_bitmap` clear, `prev` pre-armed) | alloc, asm L13551-L13584 |
| `0x04` | active, demoted | `LABEL_021EA1` asm L12960-12971 |
| `0x02` | spent — moved to list 6, the **steal-me-first** list | `LABEL_021E83` asm L12946 |
| `0x01` | retired / free | `LABEL_021E31` asm L12932-L12933 |

Two transitions matter to us:

* `LABEL_021EA1` (asm L12960): `if node[+0x22] bit7: return` (never demote a keep-alive voice);
  `if node[+0x25] < 0x80: goto LABEL_021E83` (**demote on the chip-reported level**);
  else `0x08 → 0x04` and move to list `node[+0x26]`.
* `LABEL_021E31` (asm L12908-L12945) is the **only** route back to the free list, and in steady state
  its only caller is the teardown at asm L13324 — which requires the chip to report silence.

`node[+0x25]` is seeded `0xFF` at allocation (asm L13523) and thereafter is **the chip's own
per-voice envelope level**, read at latch `0x0180 + ch` (asm L13337-13344) and zeroed on retire
(asm L12933).

### 6.2 What the HLE owes, and what it must not do
**The HLE must not allocate or steal.** That is firmware list surgery over its own RAM; the
audit's §4.5 finding "voice allocation and stealing are not the HLE's job" is **correct as-is**
and this design does not change it. But the HLE supplies **both inputs** the policy consumes,
and today both are wrong:

| policy question | firmware reads | HLE today | fix |
|---|---|---|---|
| "is this channel finished?" | bank bitmap, latch 0..3 | `key_on` — never true for handed-off voices → **the free list never refills** | **R1 + R2** |
| "which channel is expendable?" | level at latch `0x0180+ch` | a bank bitmap answering a level query (latch masked to 2 bits, `cpp:352`) | **R0** |

The first defect causes stealing to *happen*; the second causes it to pick the *wrong victim*
(a still-ringing voice reads level 0 → demoted to list 6 → stolen first; a finished voice
whose channel index aliases a busy bank reads 0xE0 → protected). Both are MEASURED (§2 and
audit GAP 3 respectively).

### 6.3 Making a steal clean
At the chip boundary a steal is *nothing but a fresh note-on burst on a channel that is still
sounding*. Two obligations, in priority order:

1. **R4 is the whole answer.** The `0x8100` gate must unconditionally re-initialise the voice.
   `process_key_on` (`kn5000_tonegen.cpp:1456-1490`) already resets `wave_offset`, `env_level`,
   `lp_z` and `pitch_offset`; under the new EG it must additionally reset the EG level, the EG
   segment index and `eg_terminated`. If **any** per-voice state survived a gate, a stolen voice
   would keep ringing under the new note. Nothing else is required for correctness.

2. **Honour the pre-mute, but never depend on it.** The firmware writes `+0x840 = 0xFF00` /
   `+0x800 = 0xFF80` **386 µs** before the burst (MEASURED: 12.005590 / 12.005593 vs the
   `+0x040` write at 12.005976, `voicelife_trace.txt`; emitters `Voice_SetPitch` asm
   L28560/L28578 and `Voice_NoteOff` asm L28663/L28677). Under R3+R6 that is an ordinary EG
   program to silence at maximum rate, so the previous occupant ramps out instead of being
   slammed to full scale (today) or cut dead.
   **But it is guarded**: `CP QIZH, 040h / JR NC` (asm L28556-L28558) skips it unless the
   *key query* found a channel — so a channel stolen from a **different key** receives **no**
   pre-mute. (MEASURED guard; INFERRED consequence.) R4 must therefore stand alone.

3. Not our business, noted for completeness: `LABEL_021ECB` → `LABEL_021F08` (asm L12979-L13070)
   is the all-notes-off/reset path — `+0x840 = 0xA200`, `+0x800 = 0xA280` on all 64 channels,
   then `+0x0C0 = 0x0000`, `+0x000 = 0x7E00` on all 64. R5 and R6 already cover it; no extra
   rule needed.

### 6.4 Predicted effect on the observed allocation march
`voicelife_alloc.txt` shows C4→ch0,1 D4→ch2,3 E4→ch4,5 F4→ch6,7 G4→ch8,9 chord→ch10..15 — a
monotone march. That is **normal FIFO free-list behaviour and not a defect**; `LABEL_021E31`
appends retired nodes to the tail (asm L12925-L12931). R1/R2 will not change it for key-bed
notes (they are already freed, if at the wrong moment). What R1/R2 changes is that
**handed-off voices start being freed at all**, which is what stops the free list from draining
during accompaniment.

---

## 7. The single dependency on GAP CAL-1 — stated as a contract

The lifecycle needs exactly **one** thing from the envelope calibration, and it is a structural
requirement, not a number:

> **CAL-1 CONTRACT.** The level→gain law `g(L)` must return **exactly 0** for the level code(s)
> the firmware uses to silence a channel. A gain law with a nonzero floor is unusable for the
> voice lifecycle and must be corrected, not worked around.

The justification is not aesthetic: a chip that could never render a voice silent could never
drop its bitmap bit, so the firmware could never free a channel, so a 64-voice instrument would
lock up after 64 notes. The firmware's entire voice manager presupposes that `g` reaches zero.

**A contradiction CAL-1 must resolve (reported, deliberately NOT resolved here).** The four
MEASURED `+0x800` values are:

| context | `+0x840` | `+0x800` | asm |
|---|---|---|---|
| channel pre-reuse | `0xFF00` | `0xFF80` | L28560 / L28578, L28663 / L28677 |
| all-notes-off / panic | `0xA200` | `0xA280` | L13013 / L13027 |
| key release (captured) | `0x8B00` | `0x8B80` | `LABEL_02D436`, trace 14.013433/14.013443 |
| note-on (captured) | `0x484C` | `0xE57F` | trace 12.006xxx |

`LABEL_025636` (asm L18944; the word is built at L19078-L19087) builds the `+0x800` word as
`(level << 8) | RATETAB_0x011963[desc[+0x28]]`, storing it to scratch `[+0x3c]`, which
`LABEL_02D68F` ships to `+0x800` (asm L30187, write at L30194-L30201). Under that reading the three silencing
contexts share **rate `0x80`** but carry **three different levels** (0xFF / 0xA2 / 0x8B) — so
they cannot all be "jump to silence", yet all three must silence the channel. Meanwhile the
validated velocity direction ("`+0x800` high byte higher = LOUDER", MUST-NOT-REGRESS) makes the
pre-reuse value `0xFF` the *loudest* possible, which is what produces the full-scale blip 386 µs
before every re-gate (audit GAP 7).

I am **not** inventing a resolution. What the lifecycle needs is only that CAL-1 pick a decode
under which the pre-reuse pair renders as silence, and R2's floor then follows from `g` by
definition.

**Shipping order.** R0, R3, R4, R5, R7, R8, R9 and R2s are all calibration-independent and can
ship now. R1 can ship now with R2 reduced to its interlock clause R2s alone — that already fixes
LIFE-1 for every voice whose rendered output actually reaches zero. R2(1)+(2) should land with
CAL-1, because until `g` reaches zero, a voice that renders at (say) −81 dB never terminates and
the free list still does not refill for those voices. Saying so is more useful than shipping a
threshold that would make it look fixed.

---

## 8. Predict-then-check log, including the misses

| # | prediction (source) | outcome |
|---|---|---|
| 1 | "allocation runs 0,1,…,63 then WRAPS and steals" (task brief) | **PARTIAL MISS.** In the capture every key-bed voice *was* freed (0x7E00 within ~60 ms of release) and the march 0,1→…→10..15 is ordinary FIFO. The never-freed population is specifically the **handed-off** voices. Mechanism confirmed, scope narrower and sharper: MEASURED at ch0, gated 5.859349, handed off 5.859385, re-gated 12.006012 with no intervening free (§2). |
| 2 | "`+0x840` followed by `+0x940` is the deterministic release signature" (audit GAP 5) | **MISS.** The signature is exact for `LABEL_02D436` but `LABEL_02D436` is not note-off-specific — `Voice_CC_Portamento` → `Voice_ParamInit` reaches it with keys down (§5.1). Reported rather than shipped. |
| 3 | "a handed-off voice can never receive a 0x7E00" (`kn5000_tonegen.cpp:349`) | **MISS / now falsified.** The 0x7E00 is generated *by* the silence report; the loop is closed through `status_r`, MEASURED at 12.481481 → 12.481537 (§0). This is the misconception at the root of LIFE-1. |
| 4 | "honest silence reporting risks reclaiming held notes" (task brief) | **HELD, but relocated.** The risk is real and it is *entirely* CAL-1's; R2s makes the lifecycle rule itself incapable of cutting audible sound (§4 Theorem). |
| 5 | "R3 will make d3457eb's 'release from the held level' emergent" (this pass) | **CONFIRMED** by re-reading `process_key_off` (`cpp:1495-1519`): its whole body is subsumed by carrying the EG level across a reprogram. |

## 9. Open, and deliberately not answered

* `node[+0x22]` bit0 ("never tear down", asm L13327) — set by `LABEL_021E31` (asm L12936) on
  retired nodes; whether anything else sets it is not traced. Not needed by this design.
* The identity of the note-on request byte `req[6+i]` bit7 that chooses `0x88` vs `0x08`
  (asm L13529-13533) — i.e. which voices get the firmware keep-alive. **Not needed**: the design
  assumes the worst case (no keep-alive) throughout, which is the safe direction.
* The low bits of the hand-off word `0xF0xx`/`0xFExx` (`slot[+0x2d]`, built by `LABEL_025589`
  asm L18856-18906). Audit GAP 8 shows the HLE's `data & 0x1FF` is one bit too wide; the
  correct field is `data & 0xFF` with bit 8 an independent flag whose meaning is **not decoded**.
  Out of scope here, flagged.
* Whether the release delay `chan[+0x2f]` initialised at note-on (asm L27197-L27200, from
  `LABEL_03421E` asm L37174 via the table at 0x011E16) is ever armed *at note-on* rather than at
  note-off. Not load-bearing: R1-R5 are indifferent to when the EG is reprogrammed.

---

## 10. Reproduction

Register/bitmap traces used above are `notes/audit/data-voicelife/voicelife_trace.txt` and
`voicelife_alloc.txt`; the probes that produced them are alongside them
(`voicelife_probe.lua`, `voicelife_probe2.lua`). Re-running them:

```
S=<scratchpad>
cd ~/compartilhado/kn7000-emulator
timeout 420 ./kn7000 kn5000 -rompath roms -window -nomaximize -skip_gameinfo \
  -nvram_directory $S/nvvl -autoboot_script $S/voicelife_probe.lua -autoboot_delay 0 \
  -video opengl -sound none
```
The returned passthrough handler from `install_write_tap`/`install_read_tap` **must** be stored
in a global or Lua garbage-collects it and the tap silently never fires.

Disassembly anchors:
```
grep -n 'LABEL_02219F\|LABEL_02B4A1\|LABEL_022340\|LABEL_022587\|LABEL_021E31\|LABEL_021E83\|\
LABEL_021EA1\|LABEL_02CD71\|LABEL_02D436\|Voice_ParamInit\|Voice_NoteOff\|Voice_SetPitch\|\
LABEL_026E5B\|LABEL_027A46\|LABEL_02CCD3\|LABEL_025636' kn5000_subprogram_v142.asm
```
