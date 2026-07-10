# F.3 — loading a reverb effect (investigation, 2026-07-10)

Goal (Felipe): make the effects DSP audibly apply a REVERB. Status: the DSP already
applies its DEFAULT effect audibly (dry+wet sum, commit a988ecf); loading a REVERB
specifically is blocked by the SD-menu boot state. Full findings below.

## The effects engine IS working

After the kernel (805 words), the firmware uploads effect microprograms to PM 0x8400
(+ DM 0x9800 / 0xC000 params/state) repeatedly (~84x over a boot). Verified by logging
every post-kernel PM/DM commit in dsp_data_w. So effects DO load and the DSP DOES
process them: with an effect active the kernel writes FOUR output words per frame
(0xC350/1 and 0xC352/3 = two sends), vs two for the bare passthrough. Summing the two
sends (a988ecf) makes the processed (wet) send audible.

## Two effect paths — the normal one is gated by the SD menu

1. **DspEffectSelect(unit, type)** (thunk 0x48405815 -> real 0x48415793). DECODED:
   - Reads the per-unit param block ptr at `*(0x500A01E0)`; allocates it via
     DspAllocParamBlock (0x484057A9) if it is -1.
   - Calls DspEffectAssign (0x4840562C): validates (unit<=9, DspEffectTypeValid
     whitelist 0x48406132), then into the 0x120-byte per-unit struct at
     `param_block + unit*0x120` writes **dirty=1 at +6** and **type at +8**.
   - So a reverb = assign unit9 a reverb type; unit9 = Reverb, valid types
     0x01/0x02/0x04 -> rec06/07/09 (type 0x00 = rec05 = passthrough). Catalog:
     notes/dsp-effect-catalog.md.
   - BUT: `*(0x500A01E0)` stays **0xFFFFFFFF (unallocated) the entire run** -> this
     path NEVER runs in the current (TG-gate) boot. DspBootDefaultEffects (0x4840537D,
     "select unit8/type0 + unit0/type0x14") and DspEffectSelect are not reached.
   - LIKELY because opening the TG gate (CONFIG bit1) advances boot into the paused SD
     subsystem -> the SD menu, NOT the play screen where sound/effect selection runs
     (memory kn7000-sd-strap-gate). This is the recurring SD-menu blocker.

2. **The ACTIVE upload path** (what actually loads the ~84 effects): maincpu PC
   **0x48404EDD** calls the low-level host-port write HAL **0x48404E8D** (writes index
   0x98000000 / data 0x9C000000; gated on the DSP-present flag 0x500066CC == 0). This
   streams whatever effect the current sound uses (a subtle EQ/Enhancer-like effect on
   the default Concert Grand, hence the mix is only subtly different from dry). The
   effect-TYPE source for THIS path is higher up the call stack -- NOT yet traced.

## Routes to an audible REVERB (next)

A. **Resolve the SD-menu boot state** so boot reaches the play screen, where
   DspBootDefaultEffects/DspEffectSelect run (param block allocates) and the panel can
   select a reverb sound/effect. Cleanest + most faithful, but the SD-menu root cause is
   unknown (memory kn7000-sd-strap-gate). Would also fix the long-standing gate issue.
B. **Trace the active path's effect-type source** (up from 0x48404EDD) to the variable
   that selects the effect record, and set it to a reverb type. Faithful-ish, contained.
C. **Poke DspEffectSelect's path into action**: allocate the param block + set unit9
   type/dirty, then get the firmware to upload via the param-block path -- but that path
   isn't the active one here, so it may not take effect without A.
D. **Directly upload a reverb record** (rec06/07/09) to PM 0x8400 from the driver,
   bypassing the firmware. A HACK (not how the device selects effects) -- only as a last-
   resort demonstration; label clearly, do NOT present as faithful.

RECOMMENDED: B first (contained RE), then A (also fixes the SD menu). To VALIDATE a
reverb once loaded: use a note with RELEASE (press then release) and look for a decaying
TAIL after note-off (a sustained note only shows coloration). And re-derive the output
offset per effect (tap the TX0 write address; the passthrough uses TX0+0xE=0xC350).

Tooling: interleave the ROMs with kn7000_disassembly/tools/interleave_evenodd.py, then
`unidasm PROG.bin -arch mn10300 -basepc ADDR` -- but unidasm does NOT seek; extract the
bytes at the file offset first (dd skip=OFFSET) or you disassemble offset 0. OFFSET =
ADDR - 0x48400000.
