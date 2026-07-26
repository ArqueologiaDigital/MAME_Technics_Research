# data-output/ — the live measurements behind `kn5000-output-design.md`

| file | what it is |
|---|---|
| `panprobe.lua` / `panprobe.txt` | sub-CPU RAM + IC303 register dump while a C4 is held on the default Piano. Establishes `desc[+0x17]` = the patch's partial block, `desc[+0x27]` = the part's tone slot, and the five-way agreement `partial_block[+0x01]` == `subrec[+0x23]/[+0x24]` == `desc[+0x2b]` == `+0x180`. |
| `panprobe2.lua` / `panprobe2.txt` | the CAUSAL test: poke the tone-slot pan byte to 0x2A / 0x55 **before** the note-on and predict the chip is told `+0x0180 = 002A` / `+0x0181 = 0055`. PREDICT-THEN-CHECK: exact hit. |
| `concur.lua` / `concur.txt` | gated-voice concurrency during a dense accompaniment passage. Shows the count ramping 0 -> 64 and STAYING at 64 — the GAP LIFE-1 symptom, which is why today's peak measurements over-state hardware density. |
| `concur_wav_analysis.txt` | peak / RMS / recovered pre-limiter sum for the WAV of that passage (the WAV itself is 13 MB and is not committed; regenerate with `-wavwrite`). |

Reproduce: see `kn5000-output-design.md` §5. The Lua tap handle must be kept in a GLOBAL or
Lua GC silently disables it.
