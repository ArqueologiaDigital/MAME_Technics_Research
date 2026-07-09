> Phase C / first-cut-audio recon (2026-07-09). Companion to sound-subsystem-plan.md.

# First-cut TG→audio mapping: keyed voice → audible placeholder samples

Sources: `kn7000_disassembly/tools/make_placeholder_waveroms.py` (bank layout), `kn7000_mame/notes/placeholder-wave-rom-spec.md` §2–3 (tiling + MAME loading), `kn7000_mame/notes/tone-generator.md` (register groups, dormancy), `kn5000-docs/waveform-rom-format.md:129,137-141` and `kn5000-docs/tone-generator.md:119,364` (pitch convention `0x8000 = 1.0×`, sample rate). Driver refs are `kn7000_mame/src/mame/matsushita/kn7000.cpp`.

## 0. Ground facts to build on (verified)

- **Placeholder bank 0 = a 256-word full-amplitude sine, `±30000`, tiled** across the whole bank. `make_placeholder_waveroms.py` `cycle_sine(n=256)`, `BANK_CYCLES[0]`, `AMP = 30000`.
- **A bank is `MASTER_WORDS // NBANKS = 16M // 16 = 1,048,576 window words`** (`build_master`, `bank_words = MASTER_WORDS // NBANKS`). Bank 0 spans window words `0x000000..0x0FFFFF` = 4096 back-to-back copies of the 256-sample sine.
- **Untransposed root pitch of the tile ≈ 172.3 Hz** = `Fs/256 = 44100/256` (spec §2.2 "≈172 Hz root"). The frequency the tile plays at ratio `1.0×`.
- **Samples are signed 16-bit little-endian.** `array('h')` on x86 → LE `tobytes()`; loaded `ROM_REGION16_LE`, so **window word `W` == `region_u16[W]`** as host `int16_t` (spec §3.2).
- **Sample rate uncertain; assume 44100 Hz** first cut (`kn5000-docs/waveform-rom-format.md:141`: "likely 48 kHz or 44.1 kHz" — not found definitively). Retargetable to 48000.
- **The firmware playback engine is dormant** (`tone-generator.md`: MainSoundAdd/MainSeqRun never ran on blind stimulus). A synth that only reads `m_tg_reg` stays silent until Phase C — forces the staging in §3.

## 1. Synthesis mapping: note → Hz → phase step into the sine tile

**Primary path — derive pitch from the key-on MIDI note number** (KN7000 pitch register semantics unconfirmed — `tone-generator.md` "Open / next").

```
Fs = 44100.0 ; L = 256 (full region) ; TILE_BASE = 0x1000 ; A4=440, A4_NOTE=69
f(n)   = 440.0 * 2^((n - 69)/12.0)        // Hz for MIDI note n
inc(n) = f(n) * L / Fs                      // tile entries advanced per output sample
```
`inc` stays below `L` across the musical range (C8≈4186 Hz → inc≈24.3).

Worked: C4(60)=261.63Hz→inc 1.519 ; A4(69)=440Hz→inc 2.554 ; C5(72)=523.25Hz→inc 3.037.

Per-voice render:
```cpp
const int16_t *wav = (const int16_t*)memregion(\"wave_a\")->base();
for (int s = 0; s < outputs[0].samples(); ++s) {
    float acc = 0.f;
    for (int v = 0; v < NVOICES; ++v) {
        if (!m_on[v]) continue;
        double inc = 440.0 * pow(2.0, (m_note[v]-69)/12.0) * L / Fs;
        int    idx = TILE_BASE + (int(m_phase[v]) & (L-1));
        acc += wav[idx] * (1.0f/32768.0f);
        m_phase[v] = fmod(m_phase[v] + inc, double(L));
    }
    outputs[0].put(s, acc / NVOICES);
}
```
- **Chip/parity/byte order:** read the reassembled full region `\"wave_a\"` (both chips interleaved by `ROM_LOAD32_WORD` @0/@2) — no parity math, `wav[idx]` is the window-word sample, host `int16_t`, already LE. `wave_a`=master TG @0x98040000, `wave_b`=sub TG @0x98050000 (provisional, self-correcting; spec §2.4).
- **Optional (only once firmware drives voices):** `0x8000=1.0×` (`kn5000-docs/tone-generator.md:119`) collapses to `inc = m_tg_reg[tg][0x40+channel] / 32768.0` since 1.0× = one tile-entry/output-sample at 44100 (`256·172.27/44100=1.0`). Pitch reg offset = group0·0x100+bank1·0x40+ch = `0x40+ch` (`kn7000.cpp` `group<<8|bank<<6|channel`). Keep behind a flag until Phase C confirms KN7000 uses KN5000 encoding.

## 2. Mapping onto the MAME region

`ROM_REGION16_LE(\"wave_a\")` + `ROM_LOAD32_WORD(ic204,0)`/`ROM_LOAD32_WORD(ic203,2)` (spec §3.2) → flat int16 LE array, **index = window word**. Bank 0 cycle = `wav[TILE_BASE+0..TILE_BASE+255]`.

**Parity/stamp caveat → why TILE_BASE=0x1000:** the generator (`stamp_provenance`) writes ASCII into each chip at chip-word `0x40` and `0x400` (reassembled ~`0x80`/`0x800`); reading a tile at word 0 splices those bytes in (audible click). `0x1000 = 16·256` is cycle-aligned and past all stamps → pristine sine. **Single-chip decimated fallback:** if only one chip file is loaded, consecutive indices are every-other master sample → 128-sample sine; set `L=128` (`0x1000 % 128 = 0`, still clean). Fine for a first tone, worst-case half-sample skew (inaudible). Guard reads with `ROMREGION_ERASE00` so strays are silence.

## 3. Simpler fallback + recommended staging

Dormant engine ⇒ `m_tg_reg`-driven synth emits nothing today. Prove the path with the working keybed FIFO (`kn7000.cpp` `kbd_push`/`kbd_key`, `KN_KEY` map, C4=0x3C).

**Stage 0 — pure synthesized sine, NO ROM read:** on `kbd_key` press set `m_on/m_note/m_phase`; in stream `acc += sinf(2π·phase); phase += f(note)/Fs; wrap`. Add `speaker_device`+`sound_stream`, drop `MACHINE_NO_SOUND` (`kn7000.cpp:1680`), trigger from `kbd_key`. Proves DAC/speaker/stream plumbing.

**Stage 1 — same trigger, read bank-0 samples** from `wave_a` per §1/§2 (swap `sinf()` for `wav[TILE_BASE+(int(phase)&(L-1))]`). Validates region indexing/endianness/tile layout.

**Stage 2 — drive from firmware voice writes:** move trigger to `m_tg_reg` events — key-on strobe group0.2 bit15 (`0x80+ch`)/group1.3 `0x8100` (`0x1C0+ch`), note group4.0 `note<<8|active` (`0x400+ch`) per `tone-generator.md`. Produces sound only once Phase C makes the engine emit voices; stays correctly silent until then.

**Recommendation:** land Stage 0 first (unblocks CI audio), then Stage 1 (validates placeholder ROM read), keep Stage 2 gated behind the same switch that un-gates real firmware voice traffic. Stages 0/1 stay honestly `MACHINE_IMPERFECT_SOUND`.

## 4. Headless audible verification (CI-friendly)

Capture:
```
mame kn7000 -rompath <roms> -sound none -samplerate 44100 \\
     -wavwrite /tmp/out.wav -seconds_to_run 5 -nothrottle -video none -window
```
`-wavwrite` taps the sound stream in the sound manager, independent of the output device (works with `-sound none`; if that yields an empty file on your build, drop `-sound none`). Hold a key during the run via autoboot/lua or the keybed input.

Check (stdlib `wave`, Goertzel — no numpy):
```python
import wave, struct, math, sys
TARGET_HZ = 261.63
w = wave.open(sys.argv[1] if len(sys.argv)>1 else \"/tmp/out.wav\", \"rb\")
fs,n,ch,sw = w.getframerate(),w.getnframes(),w.getnchannels(),w.getsampwidth()
raw = w.readframes(n); w.close(); assert sw==2
xs = struct.unpack(\"<%dh\"%(len(raw)//2), raw)[0::ch]
rms = math.sqrt(sum(v*v for v in xs)/len(xs)); nz = sum(1 for v in xs if v)
assert rms>50 and nz>0.01*len(xs), \"SILENT\"
def g(sig,f,fs):
    wct=2*math.cos(2*math.pi*f/fs); s1=s2=0.0
    for x in sig: s0=x+wct*s1-s2; s2,s1=s1,s0
    return s1*s1+s2*s2-wct*s1*s2
assert g(xs,TARGET_HZ,fs) > 8*g(xs,TARGET_HZ*1.335,fs), \"no tone at pitch\"
print(\"PASS\")
```
Asserts: nonzero RMS energy (path alive), most samples nonzero (not a lone click), spectral energy at the played pitch vs a detuned control bin. Exit code gates CI.

---

**Not found / open:** real waveform descriptor format, KN7000 pitch-register encoding (KN5000 `0x8000=1.0×` is a template only), true sample rate (44.1 vs 48 kHz). This mapping bypasses all three by treating bank 0 as a fixed single-cycle wavetable and deriving pitch from the note number.