> Phase C / first-cut-audio recon (2026-07-09). Companion to sound-subsystem-plan.md.

# KN7000 audio-output implementation plan — first-cut tone-generator `sound_stream`

Scope: add a synthesizing tone-generator device + speaker so the KN7000 driver produces audio from the captured TG register file and the synthetic placeholder wave ROMs. No DSP effects. Boot-to-home must not regress.

Primary references consulted:
- KN5000 template device: `git -C /home/fsanches/compartilhado/mame show kn5000_research_tonegen:src/mame/matsushita/kn5000_tonegen.{h,cpp}` (device_sound_interface, 64-voice register file, `sound_stream_update`, missing-ROM handling).
- KN5000 wiring: same branch `kn5000.cpp:999-1006` (SPEAKER + KN5000_TONEGEN + add_route) and `:290-293` (addr_w/data_w/data_r map at 0x100000/0x100002) and `:1073-1077` ("waveform" region, IC307 dumped / IC304-306 NO_DUMP).
- Current KN7000 driver: `/home/fsanches/compartilhado/kn7000_mame/src/mame/matsushita/kn7000.cpp` — `io_w` TG capture `:500-513`, register file `m_tg_reg[2][0x1000]` `:241-242`, `machine_config kn7000()` `:1515-1575`, `ROM_START` `:1587-1616` (commented `wave` region `:1611-1615`), `MACHINE_NO_SOUND` on the SYST line `:1680`.
- Placeholder generator: `/home/fsanches/compartilhado/kn7000_disassembly/tools/make_placeholder_waveroms.py` — 4× 16 MiB files, even/odd parity split, master TG even=ic204 odd=ic203, sub even=ic208 odd=ic207; each chip = 8,388,608 words; bank 0 = 256-sample full-amplitude sine.
- TG register interface: `kn7000_mame/notes/tone-generator.md` (HIGH16=address→base+0, LOW16=data→base+2; address = `group<<8 | bank<<6 | channel`; playback voices are currently DORMANT — only 0xFC0x refresh + group 0x04/0x0C init traffic observed).
- Wave-ROM addressing / parity interleave / checksum targets: `kn7000_mame/notes/placeholder-wave-rom-spec.md` §1.1-1.2 (one TG's wave space = linear 16-bit-word window; two chips word-interleaved on parity; internal pair = 16 M words = 32 MB per TG).

---

## 1. ARCHITECTURE decision — standalone `kn7000_tonegen` device (recommended)

**Recommendation: add a standalone `kn7000_tonegen_device` (device_t + device_sound_interface), and instantiate TWO of them** (master IC201 @0x98040000, sub IC205 @0x98050000), exactly mirroring the KN5000. Do **not** put `device_sound_interface` on `kn7000_state`.

Justification:
- **Two identical TGs.** The KN7000 has two tone-generator LSIs (`tone-generator.md` header; driver `m_tg_reg[2][...]`). An inline sound interface on the state would have to multiplex two independent 64-voice engines, two wave regions, two `stream`s. A device instantiated twice is the natural fit and is exactly how MAME expects multi-instance sound blocks.
- **The KN5000 device drops in almost verbatim.** The register-indirect semantics (address latch + data port + 64 voices + group/bank/channel decode) are shared-codebase-identical per `tone-generator.md`. Reusing `kn5000_tonegen.{h,cpp}` as the skeleton is the lowest-risk path; a divergent inline implementation throws that away.
- **The inline `m_tg_reg` capture is a stopgap, not an asset to preserve.** `io_w` cases `0x20001`/`0x28001` (kn7000.cpp:504-509) just stash the latched word into `m_tg_reg[tg][addr]`. Moving that stash into the device's `data_w` is a two-line change per case (forward to `m_tonegen[tg]->data_w(...)`); nothing else reads `m_tg_reg` for synthesis, so there is no inline state worth keeping. (`m_tg_reg`/`m_tg_addr` can be deleted once forwarded, or left as a debug mirror.)
- **Cleaner save-state / logging / lifetime.** The device gets its own `save_item`s, `VERBOSE` log masks, and `device_reset`, isolated from the (large) `kn7000_state`.

The device should be KN7000-specific (`kn7000_tonegen`), copied from the KN5000 one, because the KN7000 wave space, parity interleave, and the (still-unknown) exact voice-register decode will diverge as they are reversed. Name it `KN7000_TONEGEN`.

---

## 2. CONCRETE STEPS to wire audio in `kn7000.cpp`

### 2.0 New files (copy + rename from KN5000)
Create `src/mame/matsushita/kn7000_tonegen.{h,cpp}` starting from the KN5000 device (section 3 gives the KN7000-adapted `sound_stream_update`). Rename the type `KN5000_TONEGEN`→`KN7000_TONEGEN`, class `kn5000_tonegen_device`→`kn7000_tonegen_device`, guard `MAME_MATSUSHITA_KN7000_TONEGEN_H`. Keep `NUM_VOICES=64`. Add the file to `src/mame/matsushita/` build list if the build uses an explicit source list (MAME's `matsushita.lst`/`mame.flt` picks up files referenced by a driver automatically via `#include`, but confirm the module list — the KN5000 device is already listed as a sibling and is the model to copy).

### 2.1 Includes + members (top of kn7000.cpp / kn7000_state)
```cpp
#include "speaker.h"          // near the other MAME includes (KN5000 kn5000.cpp:19)
#include "kn7000_tonegen.h"   // (KN5000 kn5000.cpp:24)
```
In `class kn7000_state`, next to `m_midi_uart` (kn7000.cpp:191):
```cpp
    required_device_array<kn7000_tonegen_device, 2> m_tonegen;   // [0]=master IC201, [1]=sub IC205
```
In the constructor initializer list (near `m_maincpu(*this,"maincpu")`, kn7000.cpp:158):
```cpp
        , m_tonegen(*this, "tonegen%u", 0U)
```

### 2.2 Route the TG register writes into the device (io_w)
Replace the inline capture in `io_w` (kn7000.cpp:503-512) so the address latch and data write forward to the device. The KN7000 packs HIGH16=address→base+0, LOW16=data→base+2 (`tone-generator.md`), which the existing offset decode already separates:
```cpp
    case 0x20000: m_tonegen[0]->addr_w(data); return;   // 0x98040000 master TG address latch
    case 0x20001: m_tonegen[0]->data_w(data); return;   // 0x98040002 master TG data
    case 0x28000: m_tonegen[1]->addr_w(data); return;   // 0x98050000 sub TG address latch
    case 0x28001: m_tonegen[1]->data_w(data); return;   // 0x98050002 sub TG data
    case 0x20002: case 0x20008:                         // master TG control (0x98040004/10) — no-op for now
        return;
    case 0x28002: case 0x28008:                         // sub TG control — no-op for now
        return;
```
(You may keep the old `m_tg_reg`/`m_tg_addr` stash in parallel as a debug mirror during bring-up, but the device is now the source of truth.) The voice-event FIFO reads at `0x9804/50004` (io_r, kn7000.cpp:465-478) stay as-is for this first cut — they are the key-bed input path, not synthesis.

### 2.3 machine_config additions (inside `kn7000()`, replacing the TODO at kn7000.cpp:1573-1574)
```cpp
    // --- Sound: two PCM tone generators (IC201 master @0x98040000, IC205 sub @0x98050000)
    SPEAKER(config, "lspeaker").front_left();
    SPEAKER(config, "rspeaker").front_right();

    KN7000_TONEGEN(config, m_tonegen[0], 0);              // master IC201
    m_tonegen[0]->set_waveform_region("wave_m");
    m_tonegen[0]->add_route(0, "lspeaker", 1.0);
    m_tonegen[0]->add_route(1, "rspeaker", 1.0);

    KN7000_TONEGEN(config, m_tonegen[1], 0);              // sub IC205
    m_tonegen[1]->set_waveform_region("wave_s");
    m_tonegen[1]->add_route(0, "lspeaker", 1.0);
    m_tonegen[1]->add_route(1, "rspeaker", 1.0);
```
(Mirrors KN5000 kn5000.cpp:999-1006. Two speakers = stereo; the TG's `sound_stream_update` already produces L/R.)

### 2.4 ROM regions for the placeholder waves (see 2b for the recommended loading form)
Replace the commented block at kn7000.cpp:1611-1615. Two regions, one per TG, each a 32 MB (16 M-word) interleaved master. Preferred = **empty region synthesized in-driver** (2b):
```cpp
    // Synthetic placeholder wave space, filled at machine_start (NOT a dump).
    // Each TG pair = 16 M words interleaved even/odd across its two 16 MiB chips.
    ROM_REGION16_LE(0x2000000, "wave_m", ROMREGION_ERASE00)   // master: IC204(even)+IC203(odd)
    ROM_REGION16_LE(0x2000000, "wave_s", ROMREGION_ERASE00)   // sub:    IC208(even)+IC207(odd)
```

### 2.5 Remove `MACHINE_NO_SOUND`
On the SYST line (kn7000.cpp:1680), drop the flag:
```cpp
SYST(2002, kn7000, 0, 0, kn7000, kn7000, kn7000_state, empty_init, "Technics", "SX-KN7000", MACHINE_NOT_WORKING)
```
Leave `MACHINE_NOT_WORKING`. **Do not** touch the kn6000/kn6500/kn2400/kn2600 SYST lines (:1683-1688) — they share `kn7000()` config, so they will now inherit the tonegen. That is acceptable (their wave regions are ERASE00 → silence), but to keep those siblings byte-for-byte behavior-neutral you should keep `MACHINE_NO_SOUND` on THEM (they don't declare `wave_m/wave_s` ROMs, so MAME would warn about missing regions). Cleanest: give the siblings their own tiny config that skips the tonegen, OR (least churn) also add empty `wave_m`/`wave_s` regions to their `ROM_START`s. Recommended for THIS task: only enable sound on `kn7000` and leave the siblings' NO_SOUND untouched, by guarding the tonegen behind a config flag or a separate `kn7000_sound(config)` helper called only from `kn7000()`. (See RISKS §4.)

---

## 2b. Placeholder-wave LOADING — recommendation

**Recommended (least friction for iteration): allocate empty `ROMREGION_ERASE00` regions (as in 2.4) and synthesize the placeholder waveform in C++ at `machine_start()`** — no external files, no CRCs, deterministic, and impossible to mistake for a dump.

Why, not the alternatives:
- **ROM_LOAD + BAD_DUMP + computed CRC is fragile** precisely because the files are generated: any tweak to `make_placeholder_waveroms.py` (amplitude, bank set, provenance string) changes the SHA1/CRC, breaking the ROM audit and forcing a driver edit each iteration. The spec itself flags the even/odd↔chip mapping as "PROVISIONAL … self-correcting" — you will be regenerating.
- **Loading a file from a hard path at machine_start** fights MAME's ROM-audit/sandbox model and isn't portable.

Implementation: port the tiny core of `make_placeholder_waveroms.py` into a helper that fills the region. Only bank 0 (256-sample sine) is needed to make the service SOUND SYSTEM sine test and a first audible note work; the other 15 banks are optional identifiers. Fill the interleaved 16 M-word master directly (word index = window word address):
```cpp
// in kn7000_state::machine_start() (kn7000.cpp:1432), after existing setup
static void fill_placeholder_wave(memory_region *rgn)
{
    if (!rgn) return;
    auto *w = reinterpret_cast<int16_t *>(rgn->base());
    const u32 nwords = rgn->bytes() / 2;                 // 16 M words
    // Bank 0 = full-amplitude 256-sample sine, tiled across the whole space.
    // (Matches make_placeholder_waveroms.py bank 0; AMP 30000.)
    int16_t cyc[256];
    for (int i = 0; i < 256; i++)
        cyc[i] = int16_t(30000.0 * sin(2.0 * M_PI * i / 256.0));
    for (u32 k = 0; k < nwords; k++) w[k] = cyc[k & 0xFF];
}
// ...
fill_placeholder_wave(memregion("wave_m"));
fill_placeholder_wave(memregion("wave_s"));
```
This makes the region ALWAYS present and deterministic; a note keyed onto any address plays a clean sine. When real dumps arrive, swap 2.4 for real `ROM_LOAD16_WORD … ROM_SKIP(2)` interleave pairs and delete the fill.

**Alternative to keep the actual generated `.bin` files** (if you prefer file provenance over in-driver synthesis): the even/odd word interleave is standard `ROM_LOAD16_WORD` + `ROM_SKIP(2)`:
```cpp
    ROM_REGION16_LE(0x2000000, "wave_m", ROMREGION_ERASE00)
    ROM_LOAD16_WORD("kn7000_wave_ic204_placeholder.bin", 0x000000, 0x1000000, BAD_DUMP CRC(...) SHA1(...)) ROM_SKIP(2)
    ROM_LOAD16_WORD("kn7000_wave_ic203_placeholder.bin", 0x000002, 0x1000000, BAD_DUMP CRC(...) SHA1(...)) ROM_SKIP(2)
```
Use only once the mapping is frozen. For active iteration, the ERASE00-fill approach wins.

---

## 3. `sound_stream_update` skeleton (KN7000-adapted)

Structurally real, minimal, stereo @ a fixed rate. Two honest caveats baked in as comments: (a) the exact KN7000 per-voice register decode is still provisional (KN5000-analogous per `tone-generator.md`), and (b) playback voices are presently DORMANT (no note-on traffic reaches the register file yet — `tone-generator.md` "playback is never triggered"), so this device produces **silence until the firmware actually keys a voice**, which is the correct safe default.

Header additions (kn7000_tonegen.h), mirroring KN5000's `voice_t` but with a KN7000 wave-space resolver:
```cpp
static constexpr int NUM_VOICES = 64;
static constexpr int REG_CHANNEL_MASK = 0x3F;   // address = group<<8 | bank<<6 | channel
static constexpr int REG_BANK_SHIFT   = 6;
static constexpr int REG_BANK_MASK     = 0x03;
static constexpr int REG_GROUP_SHIFT  = 8;

struct voice_t {
    uint16_t regs[32];        // group/bank-decoded, KN5000 layout (provisional)
    bool     active, key_on;
    uint32_t wave_offset;     // 16.16 fixed-point position in words
    uint32_t wave_start;      // start WORD index into the interleaved master
    uint32_t wave_length;     // loop length in words
    uint32_t pitch_step;      // 16.16 words/sample (0x10000 = native)
    int16_t  volume_l, volume_r;
    uint32_t release_counter, hold_counter;
    void reset() { std::fill(std::begin(regs),std::end(regs),0);
        active=key_on=false; wave_offset=wave_start=wave_length=0;
        pitch_step=0x10000; volume_l=volume_r=0; release_counter=hold_counter=0; }
};
```
`device_start` (rate: use 44100 as requested; the KN5000 uses 48000 — pick one and keep the resampler happy):
```cpp
void kn7000_tonegen_device::device_start()
{
    m_stream = stream_alloc(0, 2, 44100);
    memory_region *r = machine().root_device().memregion(m_waveform_region_tag);
    m_waveform_data = r ? reinterpret_cast<const int16_t *>(r->base()) : nullptr;
    m_waveform_words = r ? (r->bytes() / 2) : 0;
    // save_item(...) for m_addr_latch and every voice field (see KN5000 device_start)
}
```
The mixer:
```cpp
void kn7000_tonegen_device::sound_stream_update(sound_stream &stream)
{
    for (int s = 0; s < stream.samples(); s++)
    {
        int32_t mix_l = 0, mix_r = 0;

        for (int ch = 0; ch < NUM_VOICES; ch++)
        {
            voice_t &v = m_voice[ch];
            if (!v.active) continue;

            // Key-off hold timer keeps the voice "active" for firmware status
            // polling even with no PCM (mirrors KN5000; harmless if unused here).
            if (!v.key_on && v.hold_counter > 0) {
                if (--v.hold_counter == 0 && v.release_counter == 0) { v.active = false; continue; }
            }

            // No wave region loaded (siblings / pre-fill) -> track timing, emit nothing.
            const bool have_pcm = m_waveform_data && v.wave_length > 0
                                  && v.wave_start < m_waveform_words;
            if (!have_pcm) {
                if (v.wave_length) { v.wave_offset += v.pitch_step;
                    if ((v.wave_offset >> 16) >= v.wave_length) {
                        if (v.key_on) v.wave_offset = 0;
                        else if (!v.hold_counter && !v.release_counter) v.active = false; } }
                if (v.release_counter) v.release_counter--;
                if (!v.key_on && !v.hold_counter && !v.release_counter) v.active = false;
                continue;
            }

            // Fetch with linear interpolation (16.16). Positions are WORD indices
            // into the interleaved master; the wave space is tiled so any
            // start/loop address yields a clean waveform (placeholder-wave-rom-spec §1.1).
            uint32_t pos  = v.wave_offset >> 16;
            uint32_t frac = v.wave_offset & 0xFFFF;
            if (pos >= v.wave_length) {
                if (v.key_on) { v.wave_offset = 0; pos = 0; frac = 0; }
                else { if (!v.hold_counter && !v.release_counter) v.active = false; continue; }
            }
            int32_t s0 = read_word(v.wave_start + pos);
            int32_t s1 = read_word(v.wave_start + ((pos + 1 < v.wave_length) ? pos + 1 : 0));
            int32_t smp = s0 + ((s1 - s0) * int32_t(frac >> 1)) / 32768;

            if (v.release_counter) {                       // ~50ms linear fade
                smp = smp * int32_t(v.release_counter) / 2205;
                if (--v.release_counter == 0 && !v.hold_counter) v.active = false;
            }

            mix_l += (smp * v.volume_l) >> 15;
            mix_r += (smp * v.volume_r) >> 15;
            v.wave_offset += v.pitch_step;
        }

        stream.put(0, s, sound_stream::sample_t(std::clamp(mix_l,-32768,32767)) / 32768.0f);
        stream.put(1, s, sound_stream::sample_t(std::clamp(mix_r,-32768,32767)) / 32768.0f);
    }
}

int16_t kn7000_tonegen_device::read_word(uint32_t word_index) const   // header: inline helper
{ return (m_waveform_data && word_index < m_waveform_words) ? m_waveform_data[word_index] : 0; }
```
`data_w` (the register decode + key-on/off + param derivation) is copied from the KN5000 `data_w`/`update_pitch`/`update_voice_params`/`process_key_on`/`process_key_off` verbatim as the starting point; the group/bank→register-index map and the key-on strobe values are **provisional for the KN7000** and get corrected once a real note's voice writes are captured (`tone-generator.md` "Open / next": trace note 60 to pin the exact address/data). Note the KN7000 wave-resolve differs from KN5000's IC307 index-table trick — for the placeholder tiled space, `resolve_waveform` can simply set `v.wave_start = <bank<<20 word address from the voice's wave-select reg>` and `v.wave_length = 256` (one tiled cycle), which produces a clean tone from any captured address.

---

## 4. RISKS + keeping audio additive/safe

The boot-to-home behavior is precious; every change below is chosen to be behavior-neutral until the firmware itself keys a voice.

1. **`io_w` forwarding must stay pure-write and never throw/log-flood.** The current cases just stash a word; `addr_w`/`data_w` do the same plus (harmlessly) decode. Risk: if `data_w` mis-decodes the 0xFC0x refresh or the group-0x04/0x0C init sweep (the ONLY traffic that actually flows — `tone-generator.md`) and spuriously keys voices, you'd get noise at boot. Mitigation: gate key-on strictly on the exact strobe value/bit, and **verify the home screen is silent** after wiring (it should be — no note-on traffic exists yet). Keep `VERBOSE 0`.

2. **`MACHINE_NO_SOUND` removal implies MAME now expects real output.** Removing it on `kn7000` is fine because the device + speakers exist and default to silence. **Do NOT let the kn6000/kn6500/kn2400/kn2600 siblings inherit a sound config they have no ROM regions for** — they call `kn7000()`. Two safe options: (a) keep `MACHINE_NO_SOUND` on their SYST lines AND move the tonegen/speaker block out of `kn7000()` into a `kn7000_sound(config)` helper called only from the true `kn7000()` path (cleanest — zero change to siblings); or (b) add empty `wave_m`/`wave_s` ERASE00 regions to each sibling `ROM_START`. Recommended: option (a). This is the single most likely regression (missing-region fatalerror at sibling startup) and is fully avoidable.

3. **Device produces silence until voices are keyed** — this is the design, and it is what makes the change safe/additive. With `wave_m/wave_s` filled by the placeholder sine, a voice only sounds once `data_w` sees a genuine key-on. Since playback voices are dormant (`tone-generator.md`: MainSoundAdd/MainSeqRun never run on blind stimulus), the audible result of THIS task alone is silence at the home screen — expected. First audible proof comes from the **service SOUND SYSTEM / WAVE ROM sine test** (`placeholder-wave-rom-spec.md` §1.2, MainWaveRomTestFunc 0x484A2E3A) or from the already-working key-bed FIFO path once its events reach the voice allocator — those are the intended bring-up stimuli, tracked separately (Phase C).

4. **Sample-rate / resampler load.** Two 64-voice devices at 44.1 kHz is trivial CPU; the `if (!v.active) continue;` fast-path means idle cost ≈ zero. No boot-timing risk (audio streams are independent of the MN10300 clock).

5. **Region size / interleave correctness.** `0x2000000` bytes = 32 MB = 16 M words per TG, matching "internal pair = 16 M words" (`placeholder-wave-rom-spec.md` §1.2). If you later switch to file-loaded placeholders, the `ROM_LOAD16_WORD … ROM_SKIP(2)` even/odd interleave must match the generator's parity split (even=ic204/ic208, odd=ic203/ic207); getting it backwards only mistunes the tiled timbre, not correctness, and is "self-correcting" via the in-MAME WAVE ROM test (spec §1.1 flag).

6. **Don't delete `m_tg_reg` in the same commit as first bring-up.** Keep it as a parallel debug mirror until the device's `data_w` decode is confirmed against captured note traffic; removing it early loses your comparison baseline. Delete it in a follow-up once the device is trusted.

Net: the safe sequence is — (1) add device files, (2) add `kn7000_sound()` helper + speakers + regions + ERASE00 sine fill, (3) forward `io_w`, (4) drop `MACHINE_NO_SOUND` on `kn7000` only, (5) confirm home screen still boots and is silent, (6) exercise the service sine test for first audible output. Every step is additive and reversible.
