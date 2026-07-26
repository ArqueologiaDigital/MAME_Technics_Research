# data-gaps — probes and captures for notes/audit/kn5000-gaps-applied.md

* `life.lua`        — starts the rhythm and counts group0/bank0 GATE (0x81xx) vs FREE (0x7E00) per
                      channel, sampling how many channels are gated-and-not-yet-freed. This is the
                      GAP LIFE-1 measurement.
* `life_before.txt` — its output on the pre-change binary: 152 gates / 64 frees, 64 stuck.
* `life_after.txt`  — its output on the final binary:     154 gates / 154 frees, peak 3 live, 0 stuck.
* `hold12.lua`      — holds C4 for 12.0 s and logs every gate/free, to prove a held key is never
                      reclaimed by the honest status_r.
* `hold12_after.txt`— its output: two gates at press, ZERO frees for 12 s, both freed 128 ms after
                      key-up.
* `battery.sh`      — runs the 7-check no-regression battery (tvf/reg.mid on -midiin2).
* `runlua.sh` / `runlua_before.sh` — run one lua probe on the current / pre-change binary.
* `ab.sh`           — the timbre/pan register capture (Piano / Bright Piano / Mellow Piano).

All runs use an isolated copy of the pre-init nvram and are timeout-wrapped.
