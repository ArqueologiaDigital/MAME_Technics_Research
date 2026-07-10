# KN7000 DSP F.3 (SPORT audio) — implementation plan

Produced 2026-07-10 by an 11-agent research workflow (parallel deep-dives into the
ADSP-21065L Technical Reference + recovered kernel disassembly, each adversarially
verified, then synthesized). [VERIFIED] vs [HYPOTHESIS] tags are load-bearing:
do NOT commit/blog a [HYPOTHESIS] as established hardware fact — gate each on the
runtime evidence in Steps 4-5. Cross-check: notes/f3-iop-runtime-capture.md.

Based on reading the actual current source alongside the verified corpus, here is the concrete F.3 implementation plan. I confirmed against the live tree: `pgm_65l`/`data_65l` at sharc.cpp:163-184, the stubbed `iop65l_r/w` (returns 0 / ignores), `schedule_chained_dma_op`'s hardcoded `0x20000` base (sharcdma.hxx:13), and the driver's TG→speaker routing + 44.1 kHz `dsp_audio_tick` (kn7000.cpp:212, 739, 923, 1835-1851).

---

# KN7000 Effects-DSP F.3 — SPORT Audio Implementation Plan

Notation: **[VERIFIED]** = confirmed in firmware disasm + 21065L TR + MAME source (adversarially re-checked). **[HYPOTHESIS]** = plausible, not yet proven; must not be presented as fact in commits/blog.

Files:
- Core: `/home/fsanches/compartilhado/kn7000_mame_build/src/devices/cpu/sharc/sharc.cpp`, `sharc.h`, `sharcdma.hxx`
- Driver: `/home/fsanches/compartilhado/kn7000_mame/src/mame/matsushita/kn7000.cpp`

The steps are ordered so each is independently testable before the next is wired.

---

## Step 1 — PM/DM internal-SRAM aliasing (correctness prerequisite)

**The bug [VERIFIED].** `pgm_65l` maps `0x08000-0x1ffff` as one `.ram()` and `data_65l` maps `0x08000-0x1ffff` as a *separate* `.ram()`. Host-boot loads the coefficient/state tables via `space(AS_DATA).write_dword()` (kn7000.cpp:764) into the DM store, but the kernel's biquad reads them with `R3 = PM(I8,M8)`, `I8 = 0x9800` — from the PM store, which is a different backing array → reads zero. Only `0x9800` (I8) and `0x9C40` (I12) are actually PM-read [VERIFIED]; `0xC000`/`0xC302` are DM-only, but aliasing the whole data region is harmless and simpler.

**Why the obvious fixes are wrong:**
- The 21062 `m_blocks` 3-column interleave (sharc.cpp:356-390) is the *48-bit instruction* path (DTYPE=1 forces "48-bit 3-column transfer"); it deliberately maps PM-48 and DM-32 to *different* cells at one address, so it would **miss** the alias [VERIFIED].
- Overriding the C++ `pm_read32`/`pm_write32` methods fixes **only the interpreter** — F.3 runs on the **DRC**, and `sharcdrc.cpp:309-320` generates inline `UML_DREAD(QWORD, SPACE_PROGRAM) + DSHR 16`, never calling the C++ method [VERIFIED]. The fix must live in the **address map**.

**Design to use (map-level, DRC-safe):**
1. Add a device member to `adsp21065l_device`: `std::unique_ptr<uint32_t[]> m_data_sram;` sized `0x18000` (covers `0x08000-0x1FFFF`), `save_pointer()`-ed for savestates.
2. Split the maps at a code/data boundary of **`0x9000`** (all 48-bit code ≤ `0x8D92`, all data ≥ `0x9800`; nothing lives in `0x8D93-0x97FF` [VERIFIED], so `0x9000` is safe):
   - `pgm_65l`: keep `map(0x08000, 0x08fff).ram();` (64-bit slots for 48-bit instruction fetch via `pm_read48`). Add `map(0x09000, 0x1ffff).rw(FUNC(...pm_data_r), FUNC(...pm_data_w));`
   - `data_65l`: keep IOP `0x0-0xff`; add `map(0x08000, 0x08fff).ram();` (unused-as-data, harmless); add `map(0x09000, 0x1ffff).rw(FUNC(...dm_data_r), FUNC(...dm_data_w));`; keep external `0x20000-0xfffff .ram()`.
3. Handlers, all indexing the **same** `m_data_sram[offset - 0x9000]`:
   - `dm_data_r(offs)` → `return store[i];` ; `dm_data_w(offs,d)` → `store[i]=d;`
   - `pm_data_r(offs)` → `return uint64_t(store[i]) << 16;` (so the core's `pm_read32 = read_qword>>16` recovers `store[i]`, and the DRC's `DREAD QWORD + DSHR 16` does too)
   - `pm_data_w(offs,d)` → `store[i] = uint32_t(d >> 16);` (matches `pm_write32`'s `data<<16` convention)

   *Note:* the PM handlers must be declared to the map as 64-bit (`.rw()` on a 64-bit program space returns/takes `uint64_t`); the DM handlers are 32-bit.

**Independent test (before any SPORT work):** boot the kernel, then dump DM `0x9800` and PM `0x9800` from the debugger (or a one-shot log in the handler) — both must now return the same host-loaded non-zero table words. Confirm the biquad `R3 = PM(I8,M8)` at `0x8300` reads non-zero. This alone is a correctness win independent of audio.

---

## Step 2 — SPORT + DMA modeling on `adsp21065l_device`

**Key fact:** MAME's stock 2106x core has a DMA engine (`dma_op[]`, `schedule_chained_dma_op`) but **no SPORT peripheral at all** (grep confirms zero `sport` refs in the core). So F.3 adds SPORT behavior from scratch on the 65L device. Given the verified kernel structure, do **not** attempt cycle-accurate serial-bit DMA — model at the *buffer* granularity the kernel actually depends on.

**What the kernel set up [VERIFIED]:**
- `STCTL0/1 (0xE0/0xF0) = 0x013CB173`, `SRCTL0/1 (0xE1/0xF1) = 0x013C3173`: standard mode, 24-bit signed, MSB-first, external clock + external frame-sync (SHARC is a **slave**), DMA+chaining enabled on A and B halves. Divisors `0xE4/0xE6/0xF4/0xF6` are never written (rate is external).
- Eight chain-pointer writes: `CPT0A(0x73)=0x4309, CPT0B(0x53)=0x4311, CPT1A(0x7B)=0x4319, CPT1B(0x5B)=0x4321` (TX ch4-7); `CPR0A(0x63)=0x4329, CPR0B(0x33)=0x4331, CPR1A(0x6B)=0x4339, CPR1B(0x3B)=0x4341` (RX ch0-3).
- TCB address = `0x8000 + (CP & 0x1FFFF)` → TCBs at `0xC309…0xC341`. Each TCB (read downward: II, IM, C, CP) gives **II buffer bases** [VERIFIED]:
  - **Outputs (TX):** SPORT0 A=`0xC342`, B=`0xC34A`; SPORT1 A=`0xC352`, B=`0xC35A`
  - **Inputs (RX):** SPORT0 A=`0xC362`, B=`0xC36A`; SPORT1 A=`0xC372`, B=`0xC37A`
  - each buffer 8 words, modify +1, **self-chaining → free-running autobuffer, no completion IRQ** (SPORT ISR vectors are RTI stubs).
- **Direction proof [VERIFIED]:** the passthrough at `0x80FB` does `R0 = DM(I4+0x20)` with `I4=0xC342` → reads `0xC362` (**RX0A = input**) and writes `0xC342` (**TX0A = output**). So SPORT0-RX is the dry input, SPORT0-TX is the wet output.

**Implementation — recommended two-tier approach:**

**Tier F.3a (bring-up, recommended first — the "direct buffer" model).** Because the buffer addresses are fixed and verified, bypass serial-DMA emulation entirely:
1. In `iop65l_w`, capture and store the SPORT control words and CP writes (so nothing fatalerrors and so you can *validate* the addresses at runtime rather than hardcode blindly). Optionally, at the moment all 8 CPs are written, walk the TCBs (`op_ptr = 0x8000 + (cp & 0x1ffff)`, fields `dm_read32(op_ptr-0..-3)`) and cache `II/IM/C` per channel into device members. This makes the buffer addresses **runtime-derived, not assumed** — important for preservation integrity.
2. Expose two device methods used by the driver each frame:
   - `dsp_rx_write(int sport, int32_t l, int32_t r)` → writes 24-bit sign-extended samples into the cached RX-A/RX-B II addresses (`0xC362/0xC36A` for SPORT0).
   - `dsp_tx_read(int sport, int32_t &l, int32_t &r)` → reads the cached TX-A/TX-B II addresses (`0xC342/0xC34A`).
   - 24-bit format: on write, store `sample & 0xFFFFFF` sign-extended into 32-bit (DTYPE=01); on read, sign-extend bit 23.
3. **Fix `schedule_chained_dma_op` for the 65L regardless** (sharcdma.hxx:13): the hardcoded `op_ptr = 0x20000 + (cp & 0x1ffff)` lands in zeroed external SDRAM on the 65L. Make it `op_ptr = irq_vector_base() + (cp & 0x1ffff)` (= `0x8000` on the 65L). This is needed if/when the real DMA engine is exercised, and is correct-by-the-descriptor [VERIFIED].

Tier F.3a does not depend on resolving the frame-size or ping-pong unknowns — it writes the input buffer, lets the kernel run its fixed per-frame pass, and reads the output buffer.

**Tier F.3b (fidelity follow-up — real SPORT autobuffer DMA).** Model each SPORT-RX channel as "serial word arrives → `dm_write32(II)`, `II += IM`, reload `II` from TCB when `C` words done" and TX as the drain, self-chaining from the CP field. Gate this on first dumping the TCB `C`/`IM` fields at runtime (Step 5) to settle the 8-word/ping-pong semantics. Only pursue after F.3a validates the path.

---

## Step 3 — Audio routing in the driver

**Current state:** `tonegen` (2ch @ 44100) routes straight to `lspeaker`/`rspeaker` (kn7000.cpp:1837-1839); the DSP is inert w.r.t. audio. Goal: **TG → SPORT0-RX → [effects] → SPORT0-TX → speakers.**

**Sample rate [VERIFIED-as-plausible]:** keep **44100 Hz**. It is now hardware-justified (X201 = 16.9344 MHz = 384×44100; an 11.2896 MHz = 256×44100 net on the board; **no** 48k-family crystal exists). Update the "provisional placeholder" comment at kn7000.cpp:416-419 to cite X201 — but keep the **[HYPOTHESIS]** caveat that IRQ0 may be per-DMA-block (rate = 44100/N) rather than strictly per-sample (see Step 5).

**Routing mechanism (decoupled rings + existing frame tick):**
1. Introduce a tiny `device_sound_interface` bridge (either a new `kn7000_dsp_bridge` sound device, or fold into the driver's own `device_sound_interface`) with **2 inputs** (wired from `tonegen`) and **2 outputs** (wired to `lspeaker`/`rspeaker`), stream at 44100.
2. Re-route in machine config: `m_tonegen->add_route(0/1, "dspbridge", ...)`; `m_dspbridge->add_route(0,"lspeaker",1.0)`, `(1,"rspeaker",1.0)`. TG no longer feeds the speakers directly.
3. Two lock-free ring buffers between the sound thread and the CPU-timeline tick:
   - bridge `sound_stream_update`: for each sample, push the incoming TG L/R into `rx_ring`, pop a processed L/R from `tx_ring` → speakers.
   - `dsp_audio_tick` (the existing 44100 Hz `emu_timer`, which runs on the CPU/emulation timeline so the SHARC executes *between* ticks): (a) read the **previous** frame's result via `dsp_tx_read(0,…)` and push to `tx_ring`; (b) pull one TG frame from `rx_ring` and `dsp_rx_write(0,…)`; (c) assert IRQ0. This yields a deterministic **1-frame latency** and decouples the two clocks (both nominally 44100; rings absorb jitter).
4. **IRQ0 pulse:** the current tick asserts with no clear (kn7000.cpp:930). Confirm the kernel's edge-sensitive `IRQ0E` config (MODE2 bit0) latches on assert; if the core needs a return-to-low to re-trigger, add a matching `CLEAR_LINE` (e.g. assert then clear next tick, or a short second timer). Verify against the IRQ actually re-firing each frame.
5. **Dry/wet [HYPOTHESIS]:** the recovered reverb/chorus kernels keep an internal direct-path coefficient, so SPORT0-TX is already a dry+wet mix. Model **TG→DSP→speaker as the single path first**. Only if output sounds 100% wet, add a hardware dry-bypass sum — flag as unverified (needs the analog block diagram / M5218 op-amps).
6. **SPORT1 [HYPOTHESIS]:** configured identically but hardware has only one stereo ADC (PCM1800) + DAC (PCM69) on the DSP board. Leave SPORT1 unrouted until Step 5 shows the mainloop actually reads/writes the `0xC372/0xC352` buffers.

---

## Step 4 — Validation strategy (headless / offline is fine)

Prove an effect **actually processes** a known input, not merely that audio passes through.

1. **Buffer-address confirmation (do first, cheap):** in the driver's `machine_start`, `m_dsp->space(AS_DATA).install_read_tap(0xC342, 0xC381, "dsp_tx", …)` and an `install_write_tap` on `0xC362-0xC37A` (RX). Log to a file. Confirms at runtime that the kernel reads RX / writes TX at exactly the verified addresses and reveals **how many words per frame** it touches (settles the 1-sample-vs-block [HYPOTHESIS]).
2. **Impulse-response test (the decisive one):** drive `dsp_rx_write` with a **unit impulse** (one frame at full-scale, silence after) instead of the TG. Capture TX output for a few thousand frames — either via the write-tap log, or MAME's `-wavwrite out.wav` on the speaker stream (headless: `mame kn7000 -seconds_to_run N -wavwrite …`, offline at ~72% realtime is fine). A **passthrough** yields a single-frame spike then silence; a **reverb** yields an exponentially decaying tail; a **comb/chorus** yields periodic echoes. Measure: post-impulse energy vs input energy, and tail length. Non-zero decaying tail = the effect DSP is genuinely running the algorithm over the input.
3. **Known-tone test:** feed a pure 1 kHz sine into RX; FFT the TX capture. A reverb/EQ shifts the spectrum/adds a decay skirt; identity passthrough leaves a clean bin. 
4. **Coefficient sensitivity:** with the effect select set to a real preset (vs passthrough `0x8400`), the tail/spectrum must change — proving coefficients from the (now-aliased, Step 1) `0x9800`/`0x9C40` tables actually reach the math.
5. **Regression guard:** assert `tg_write_count() > 0` and TX-buffer energy > 0 after N frames, so future rebuilds don't silently regress to silence.

---

## Step 5 — Risks / unknowns and resolution

| # | Unknown | Status | Resolution |
|---|---|---|---|
| 1 | Frame = 1 sample vs block-of-N | **[HYPOTHESIS]** (buffers are 8 words; TCB `C`/`IM` not yet dumped) | Runtime: dump the 8 TCBs (`C` field = `dm_read32(op_ptr-2)`) after boot via debugger or a log in the CP-write handler; and the Step-4.1 write-tap shows words/frame directly. Then set injection block size accordingly. |
| 2 | A/B ping-pong granularity; `ASTAT 0x100000` toggle meaning | **[HYPOTHESIS]** (per-frame block-swap suspected) | Watch the ASTAT-bit-20 toggle vs which of A/B buffers the mainloop reads each frame (tap `0xC362` vs `0xC36A`). Definitive prose is in the 21065L *User's Manual* Ch.9 (not in the available TR PDF). |
| 3 | Which SPORT = TG input vs 2nd bus; must SPORT1 be modeled | **[HYPOTHESIS]** (SPORT0 = main path is proven; SPORT1 role open) | Step-4.1 taps on `0xC372/0xC352`: if never touched, leave SPORT1 unrouted. Board wiring (IC306 SPORT pins → PCM1800/PCM69) from the service manual confirms. |
| 4 | Real IRQ0 rate: per-sample 44.1 kHz vs per-block 44100/N | **[HYPOTHESIS]** | Resolves with #1 (block size). Throughput stays 44.1 kHz either way; only the tick divisor changes. |
| 5 | DMA chain-ptr→address rule on real HW (empirically +0x8000) | **[VERIFIED empirically]**, authoritative prose absent | `0x8000 + (cp&0x1ffff)` lands exactly on the uploaded descriptors — sufficient and validated for F.3. Use `irq_vector_base()`. |
| 6 | Aliasing under DRC self-modifying-code path | Low risk | The 65L's `pm_write32` DRC handler hits `CMP drc_sram_base(0x01000000); RETc COND_B` and returns before cache-invalidation, so data writes to the aliased PM region won't spuriously flush code. Confirm in a real DRC run (Step 1 test). |
| 7 | 40-bit (IMDW=1) or PX/48-bit data in effect paths beyond the recovered biquad | **[HYPOTHESIS]** (kernel never writes SYSCON/IMDW → 32-bit default) | The recovered kernel uses only 32-bit register-file PM loads. If a not-yet-recovered effect enables 40-bit data, the flat-32 alias would truncate 8 mantissa bits — revisit only if an effect misbehaves. |
| 8 | Codec MCLK crystal (16.9344 vs 11.2896 MHz) / dry-wet analog mixer | **[HYPOTHESIS]** | Trace the codec MCLK net and the M5218 op-amp block in the schematic. Not blocking: doesn't change the digital path. |

---

## Recommended build order (each independently testable)

1. **Step 1 aliasing** → verify PM(0x9800) == host-loaded DM table (no audio needed).
2. **Step 2 F.3a** IOP-write capture + TCB walk + `dsp_rx_write/dsp_tx_read` + the `schedule_chained_dma_op` base fix → verify with Step-4.1 taps that the kernel reads RX/writes TX at the verified addresses.
3. **Step 3 routing** with rings + frame tick → verify passthrough audio flows TG→DSP→speaker.
4. **Step 4.2 impulse test** with a real effect preset → prove the effect processes (decaying tail).
5. **Step 5 #1/#2** runtime TCB dump → graduate to Tier F.3b real SPORT-DMA if fidelity requires; resolve SPORT1.

Do **not** commit or blog any [HYPOTHESIS] item (frame size, ping-pong, SPORT1 role, exact codec clock, dry/wet) as established hardware fact — gate each on the runtime evidence in Steps 4-5 first.
