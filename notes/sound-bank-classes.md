# The five voice-resource bank sources (2026-07-20)

Every sound the KN7000 can play is fetched out of one of **five resource
archives**. Which archive a given sound lives in is decided at lookup
time by a pair of classifier functions in region 1, and the number of
the winning archive — 0..4 — is the "class code" that the rest of the
firmware passes around.

All of the code below is converted and byte-verified in
`kn7000_disassembly` (`make verify`); names are in `kn7000_manual.sym`.

## The key is a MIDI triple

The classifier takes exactly the triple the **SOUND EXPLORER** screen
prints next to each sound — the manual's `[32.11-1 Concert Grand`
annotation (p35, `sound-gui-inventory.md`):

| register | meaning |
|---|---|
| `d0` | PROGRAM CHANGE number (masked `&0x7F` by the caller) |
| `d1` | BANK SELECT **LSB** |
| arg5 (stack) | BANK SELECT **MSB** |

packed into one 24-bit key:

```
key = (MSB << 16) | (LSB << 8) | PROGRAM
```

The independent confirmation that this is the byte order: the resource
fetcher `CustomVoiceRecFetch` (0x4844A42F) reads a stored **3-byte
`{program, bank LSB, bank MSB}` record** at `block+0x27+idx*3` and hands
those three bytes to `VoiceRecFetchBanked_entry` in exactly this order.

If the MSB is 0 the classifier short-circuits straight to the internal
archive with the 16-bit key `(LSB<<8)|PROGRAM`.

## The five sources

| class | window | directory pointer | what it is |
|---|---|---|---|
| **0** | `0x48000000` | `*(0x48000018)` | **INTERNAL** — the program+table flash's own resource archive: the factory PRESET sounds. Always present; the fallback for every miss. |
| **1** | `0x57000000` | `*(0x5700000C)` | the factory read-only **data flash** (see `initial-data-disk-and-custom-flash.md`) |
| **2** | `0x56000000` | `*(0x5600000C)` | the **CUSTOM flash** (disk-programmed data) |
| **3** | `0x41000000` | `*(0x4100000C)` | fourth archive window |
| **4** | `0x41800000` | `*(0x4180000C)` | fifth archive window |

Once a class is chosen, the bank descriptor is `0x5003A5A4 + class*4`
and its load base is `0x5003A554 + class*4`; `VoiceRecFetchBanked`
(0x484496C9) indexes the descriptor's `+0x14` pointer directory to get
the 0x8E-byte voice record, and `VoiceParamRecFetchBanked` (0x48449925)
indexes the `+0x1C` directory to get a 0x10-byte parameter record.

### How sources 1..4 are validated

All four are checked identically by the boot archive parser
(0x48449EF4..0x4844A3D1), one near-identical block per window:

1. header self-check — `*(base) + base == base + 0x200`;
2. a **16-byte signature compare against the string `"Expansion Board"`**
   stored at `0x485B8518` in the program flash (two 16-byte fields at
   `*(base+4)` and `*(base+8)` must both match);
3. on success the presence byte `0x501496B4 + n` is set to 1 and the
   directory pointers are cached into `0x5003A554..` / `0x5003A5A4..`;
   on failure the flags and pointers are zeroed and the source's
   descriptors alias the internal bank's.

`VoiceBankSourceFlagGet` (0x4844A3D4) is the reader —
`return (n >= 1 && n <= 4) ? presence[n-1] : 0` — and
`VoiceBankSourcePresent` (0x48448C0F) is the classifier's gate around
it (`0` = fitted, `-1` = absent). Two sibling probes,
0x4844A3EE and 0x4844A3F2, are compiled down to `return 0` stubs in this
firmware.

**Not settled here:** which panel button in the SOUND GROUP — the manual
lists both **MEMORY** and **EW EXPANSION** (p35) — corresponds to which
of classes 1..4. The signature string is the same for all four windows,
so the firmware itself does not distinguish them by name; only the
address window differs. Deciding that needs a live session with a card
or expansion board fitted, and guessing it would be an over-claim.

## The lookup itself

Each source has its own lookup routine, and there are two parallel
families of five (family **A** for voice records, family **B** for
parameter records). All ten are the same **multiplicative-hash bucket
walk** over the archive's sound directory:

```
dir     = base + *(base + 0x18);         # the archive's sound directory
params  = base + *(dir + 0x24);          # u16 mult, u16 nbuckets
bucket  = (key * params[0]) % params[1]; # *HashIndex
entry   = base + ((u32 *)(base + *(dir + 0x0C)))[bucket];
while (entry != base) {                  # a 0 offset terminates the chain
    if (KeyEqual(key, *(u32 *)(entry + 4)))
        return entry + 8;                # -> the payload halfword
    entry = base + *(u32 *)entry;        # chain link at +0
}
return NULL;
```

Every pointer inside an archive is a **base-relative offset**, which is
what lets the same four windows be relocated anywhere. `*HashIndex` is a
`mulu` followed by a `divu` whose *remainder* is taken, so the
multiplier and the bucket count both come out of the archive itself —
each archive carries its own hash parameters.

Family B (`VoiceParamBank*`) adds two things on top: it treats **bit15
of the payload halfword as "entry invalid"**, and on a miss it degrades
gracefully instead of returning nothing:

1. exact key `(MSB, LSB, PROGRAM)`;
2. **LSB rounded down to a multiple of 8** — `(LSB & ~7)<<8 | PROGRAM`,
   i.e. a bank *family* fallback (only for LSB >= 0x80);
3. LSB-only, MSB dropped;
4. the constant key `0x7F7F` — the built-in default.

Family A instead falls back to key `0` in the internal archive, which is
the archive's entry 0.

## Function map

| CPU | name |
|---|---|
| 0x485713D6 / DB | `VoiceBankClassify` (+`_entry`) |
| 0x4857150D / 12 | `VoiceBankLookupInternal` |
| 0x48571580 / 85 | `VoiceBankLookupSrc1` |
| 0x485715F3 / F8 | `VoiceBankLookupSrc2` |
| 0x48571666 / 6B | `VoiceBankLookupSrc3` |
| 0x485716D9 / DE | `VoiceBankLookupSrc4` |
| 0x4857174C | `VoiceBankKeyEqual` |
| 0x48571757 / 59 | `VoiceBankHashIndex` |
| 0x48570C41 / 46 | `VoiceParamBankClassify` (+`_entry`) |
| 0x48570DF8 / FD | `VoiceParamBankLookupInternal` |
| 0x48570E6B / 70 | `VoiceParamBankLookupSrc1` |
| 0x48570EDE / E3 | `VoiceParamBankLookupSrc2` |
| 0x48570F51 / 56 | `VoiceParamBankLookupSrc3` |
| 0x48570FC4 / C9 | `VoiceParamBankLookupSrc4` |
| 0x48571037 | `VoiceParamBankKeyEqual` |
| 0x48571042 / 44 | `VoiceParamBankHashIndex` |
| 0x48448C0F | `VoiceBankSourcePresent` |
| 0x4844A3D4 | `VoiceBankSourceFlagGet` |
| 0x484496C9 / CE | `VoiceRecFetchBanked` (existing) |
| 0x48449925 / 2A | `VoiceParamRecFetchBanked` |
| 0x4844A42F / 34 | `CustomVoiceRecFetch` |
| 0x4844ABF7 | `UserVoiceRecPtr` — `*(0x501496B8) + 0x70F7 + idx*0x8E` |

There are further sibling classifiers immediately after these two
(0x48571056, 0x4857176B, …) with the same five-source shape — likely the
rhythm/style and other resource kinds. They are left for a later pass.
