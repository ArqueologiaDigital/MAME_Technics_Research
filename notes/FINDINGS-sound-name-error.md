# "Sound Name Error" — does it still happen, and what is it really?

2026-08-06. Binary: published `kn7000-emulator/kn7000`, md5 `f4f946e9d62a9886bf148a3856e6737c`,
byte-identical to the build tree at `kn7000_mame` HEAD `ba84bb3` — i.e. it CONTAINS `3fd44f3`.
Nothing was rebuilt.

## 1. Answer: it does NOT reproduce

Zero occurrences in ~514 s of emulated time across five conditions, including **both
deterministic bad cases** the side-quest brief names for the previous published build.

| run | schedule | emu time | `Sound Name Error` reads | control tap |
|---|---|---|---|---|
| boot | none | 30 s | **0** | 651,088 |
| ph033 | 33 presses, ends on RIGHT1 ORCHESTRAL PAD | 65.5 s | **0** | 1,247,093 |
| soak | **444 presses** | 223 s | **0** | 2,947,863 |
| demo | Feature Presentation, transport=04 for 100 s | 130 s | **0** | 2,716,450 |
| ph033 + shared cfg | TGMODE probe On | 65.5 s | **0** | 1,247,093 |
| **FORCED (§3)** | ph033 + corrupted reply tag | 65.5 s | **4,828** (568 copies) | 1,123,033 |

Detector: a Lua **read tap** on maincpu `0xEED290-0xEED2C7`. Exact, because the 2 MB ROM contains
exactly one reference to each string (`0xEED2A8` only from the copy loop at `0xFEE6A1`). A data
read of those bytes happens **iff** the firmware writes the fallback into a name buffer.
Positive control in every run: a counting tap over the same 64 KB ROM page, non-zero everywhere,
so a zero on the string tap is a real zero. NULL: the forced run gives 8.7 events/s; at that rate
514 s of clean runs would expect ~4,400. Measured 0. Detector floor is 1 event.

## 2. ★ The premise of the investigation (mine) was WRONG

I briefed this as "something asked for a SOUND NUMBER that is not in the name stream". That is
not what the code does.

`0xFEF252` returns a **7-bit rolling REQUEST TAG**, not a sound number:
```
fef252: lda XDE,0xe2b8
        (XDE+0)=0x2B                       ; SubCPU command 0x2B = the sound-name query
        inc 1,(0xe197) ; ld L,(0xe197) ; res 7,L ; (XDE+7)=L    ; 7-bit rolling TAG
        (XDE+8)=A  (XDE+9)=C               ; item index, group  <- the real "which sound"
        ld WA,3 ; ld BC,0x0a ; call 0xef32f4  ; SENDCOMM channel 3, 10 bytes
        ld L,(0xe2bf)                      ; returns the TAG
```
RUNTIME PROOF: `(0xE2BF)` is read twice per transaction — at `PC=0xEF3443` (the byte actually
transmitted) and `PC=0xFEF292` (the value returned) — same value both times, incrementing by 1
per transaction: `0x12..0x17, 0x19..0x1F, 0x20..0x24, 0x26..0x6B`. The gaps (`0x18 0x25 0x32
0x3F 0x4C 0x59`) are exactly the tags consumed by sibling queries `0xFEF293`/`0xFEF2D4`/`0xFEF315`
sharing the counter at `0xE197`. A reply-borne sound number could not produce that pattern.

And the "name stream" is a **RAM FIFO fed only by the SubCPU** — a 255-byte ring, header
`0x0201B7..0x0201C0`, data at `0x0201C1`, init at `0xEF2F69`. Consumer `0xEF2C22`→`0xEF2F83`
(returns `0xFFFF` when empty); its only three callers are inside `0xFEE55A`. Producer `0xEF2C2F`
← `0xEF31DB`, which appears exactly once in the image: entry **#3** of the pointer table at
`0xE00012`, referenced once at `0xEF3625` in the RECEIVE dispatcher, which splits the header as
`len=(h&0x1F)+1 / channel=h>>5` — the exact inverse of the encoder at `0xEF3345`.

**So `0xFEE55A` is: send query with tag T on channel 3; spin up to 3,584 times over the channel-3
receive FIFO looking for a record whose byte 7 == T; else return 0xFF.**
`DE = 0x0E00` is a **TIMEOUT, not a table size**. The `0xFFFF` from an empty FIFO does not end the
scan — it burns one iteration.

⇒ The string means **"the SubCPU's reply to my name query did not turn up"**, which is exactly
the fault class removed by `3fd44f3` (duplicate INT0 ⇒ wedged link) and `b1cf7db`/kn5000-29.

## 3. Positive control — the detector is not blind

Corrupting ONLY the value `0xFEF252` hands back (not the byte it transmits) makes the requester
hunt for a tag the reply cannot carry — a guaranteed timeout:
```lua
if BAD and pc == 0xFEF292 then
    local newv = (v + 0x40) % 0x80        -- half a tag-cycle away
    return (data % 0x100) + newv * 0x100
end
```
The `PC` guard is load-bearing: the other reader `PC=0xEF3443` is the TRANSMIT loop — forcing
that one changes the tag actually sent, the SubCPU echoes it back, and the lookup still succeeds.
(The first attempt did exactly that and produced a byte-identical run.)

Result: same binary, same schedule, one byte different → `Sound Name Error` ×10 on the ORCHESTRAL
PAD list with the group header still correct — **pixel-for-pixel the historical symptom**.
The instrument also captures the caller, so a real occurrence would report it directly:
```
!!! SOUND-NAME-ERROR t=13.372 addr=EED2A8 PC=FEE6A4 argC=00 argA=38 dest=0101BA
```

## 4. It does NOT point at the audible wrongness

The value that fails to match is a transaction tag; the instrument choice travels as
`(XDE+8)=index, (XDE+9)=group` in the OUTGOING packet and is unaffected by whether the name reply
returns. "Sound Name Error" means the name reply was lost or late, **not** that the wrong
instrument was selected. (INFERRED, not actionable: the link that lost the reply also carries
voice traffic, so a wedge bad enough to lose name replies could lose other messages — that is a
statement about the transport, not the name path.)

## 5. ★ Correction to our own notes

**The shared `kn7000-emulator/cfg/kn5000.cfg` carries NO `AREA` override.** Its only non-defaults
are TGMODE bit 1 (the EG-free probe) and `ENCODER=73`. The "cfg carries TGMODE=1 and AREA=2"
rule I recorded is out of date — that was the *build-tree* cfg at the time. Always check, and
always use a private `-cfg_directory`.

Housekeeping for the disasm owner: `0xEF2C22` is named `SeqAlt3_ReadByte` in
`symbols/maincpu_symbols_reference.txt`. On this evidence that is a **misnomer** — it is the
channel-3 inter-CPU receive FIFO's getc.

## 6. Caveats

* Reference-chain claims come from searching for 3-byte LE address encodings; a reference formed
  by arithmetic or reached through an unfollowed pointer would be missed. The chain is tight
  (`0xEF31DB`, `0xE00012`, `0xEED2A8` each have exactly one hit) but this is not proof of absence.
* Taps see DATA reads only; the tlcs900 core fetches opcodes separately. Hence the detector is on
  the string bytes, not on `PC=0xFEE694` — which is the stronger detector anyway, since the copy
  loop MUST read those bytes.
* Five conditions is not the whole input space. The historical sighting was session-state- and
  timing-dependent and flipped across builds differing only in serial timing. "Not seen in 514 s"
  is not "cannot happen".

## 7. Recommendation

Close task-queue **P7** and the side-quest
`KN7000/side-quests/pending/kn5000_sound_name_error_long_session.txt` as **not reproducible on
the current build**, with §2 recorded as the standing description of what the string means.
The detector + forced control (`scratchpad/sne/sne_detect.lua`, `forcefail.lua`) are the
acceptance test if it ever returns.
