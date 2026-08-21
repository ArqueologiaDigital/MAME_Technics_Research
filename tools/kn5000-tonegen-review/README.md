# KN5000 tone-generator correctness probes

Standalone C++ replicas of the device's arithmetic, run against the **real** `ic307` dump and the
real `table_data` pair, written for the pre-submission correctness review of the three tone
generator PR branches (2026-08-21). Each transcribes the loop body from `kn5000_tonegen.cpp` /
`kn5000.cpp` verbatim so the numbers describe the shipped code, not a paraphrase of it.

    g++ -O2 -o probeN probeN.cpp && ./probeN
    g++ -O2 -fsanitize=address -o probe6 probe6.cpp && ./probe6      # probe6 needs ASan

| probe | question it answers | what it found |
|---|---|---|
| `probe.cpp`, `probe2.cpp` | Does any waveform page validate on the random fill MAME gives a `NO_DUMP` socket? How big are the chunks? | No. All 12 undumped pages are rejected at the first `head & 3` check. Only IC307's 4 real pages validate: 198/168/1072/57 recordings. |
| `probe3.cpp` | Concrete failing cases for the two arithmetic findings. | **7038** adjacent sample pairs overflow `(b - a) * frac` as `int32`. Worst shown: a=32358, b=-31295, frac=49152 -> correct -15382, code gives +50154. |
| `probe4.cpp` | Can `pcm_inc` overflow uint32 at any playable frequency? | **No** -- the lowest frequency reaching 2^32 is 430 kHz, far above the 23999 Hz clamp. A suspicion, measured and retracted. |
| `probe5.cpp` | Does `build_pitch_constants` complete on the real ROM, and how much slack is there? | Completes; highest byte touched 0x63076 of 0x200000. The defect is unreachable with this dump. |
| `probe6.cpp` | Is the missing bound in `build_pitch_constants` real? | **Yes, proven with ASan**: a crafted 2 MB region passing every check in the function yields `heap-buffer-overflow ... 254 bytes after 2097152-byte region`. |
| `probe7.cpp` | How loud are the real recordings against the `SINE_PEAK = 11585` placeholder? | Mean per-chunk RMS **16098**, and **1484 of 1495** chunks peak above 20000 -- roughly 6 dB hotter than the placeholder, with no compensating gain. |

⚠ THE REVIEW PREMISE WAS WRONG, IN THE SAFE DIRECTION. These probes were commissioned to check
bounds against a *zero-filled* `NO_DUMP` region. MAME does not zero-fill this one: the `waveform`
region is 16 MB, above the 4 MB threshold at `romload.cpp` that triggers the memset, so
`rom_fread` fills the missing sockets with `machine().rand()`. The sockets hold deterministic
pseudo-random bytes, and rejection is structural -- the directory's self-referential
back-reference -- rather than a heuristic that a zero fill might accidentally satisfy.

Paths are hardcoded to the local ROM set. `ic307` is the one hardware-rooted waveform dump; the
other three sockets are genuinely undumped.
