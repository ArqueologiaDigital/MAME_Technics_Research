# Producers for numbers quoted in `OVERLAY-GAPS.md`

| script                   | question it answers                                                                                | run                                                                         | result (2026-10-19)   |
|--------------------------|----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|-----------------------|
| `ic19_rom_test_sum.py`   | does IC19 give the 0x21D8 the service ROM test expects at 0x97800000 (G7)?                         | `python3 -I ic19_rom_test_sum.py technics_romsets/kn7000/c3cbmd000098.ic19` | `0x21d8`              |
| `ic307_chunk_lengths.py` | does any KN5000 IC307 recording exceed the overlay's 16.16 sample position (65,535 samples) (G16)? | `python3 -I ic307_chunk_lengths.py <kn5000 IC307 image>`                    | max 37,520; none over |

`ic307_chunk_lengths.py` was written by the 2026-10-19 sweep (its first copy is in
`research-scratch/overlay-gap-sweep/`); the IC307 image is the published folder's
`roms/kn5000/*ic307*`.
