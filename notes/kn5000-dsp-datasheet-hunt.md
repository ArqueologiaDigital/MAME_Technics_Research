# NEC uPD6383GF — documentation hunt (KN5000 effects DSP, IC311)

**Date:** 2026-07-22
**Goal:** find a datasheet / databook page / programming manual / assembler for the NEC
uPD6383GF-3BA, the effects DSP of the Technics SX-KN5000 (IC311), so its 36-bit instruction
set can be decoded and the core emulated in MAME.

**BOTTOM LINE (verdict): no instruction-set documentation for the uPD6383 exists on the
public web.** Nothing was found beyond distributor stock listings. The chip is an NEC
consumer-ASSP audio DSP that was never published in any general NEC databook, is absent from
every online datasheet aggregator checked, and has no community/forum footprint at all.
**The instruction set must be inferred.** One new lead of secondary value was found (the
family sibling uPD6380 in the NEC PC-9801-73 sound board — see §4), but it does not itself
yield an ISA.

---

## 1. What was searched, and the result

All searches below were run via WebSearch (US index) on 2026-07-22. "NOTHING" means no result
referred to the actual part in any technical sense.

| # | Query | Result |
|---|---|---|
| 1 | `uPD6383GF NEC datasheet` | NOTHING technical. Only distributor/stock pages (see §2). |
| 2 | `"uPD6383" NEC DSP` | NOTHING. Results were about uPD7720 / uPD77018 / modern NEC DSP PR. |
| 3 | `"D6383GF" service manual IC` | NOTHING but stock listings (encompass, ic2ic, jotrin). |
| 4 | `"upd6383" OR "d6383gf" schematic parts list keyboard effect` | NOTHING. |
| 5 | `"6383GF" -CDJ` | NOTHING (fishing tackle boxes, addresses). Confirms near-zero web presence. |
| 6 | `μPD6383 NEC データシート DSP` (Japanese) | NOTHING. alldatasheet.jp has no 6383. |
| 7 | `"uPD6383" OR "μPD6383" forum repair chip` | NOTHING. No forum/community mention anywhere. |
| 8 | `alldatasheet UPD6383 NEC` | NOTHING; alldatasheet's UPD63 series index has no 638x DSP. |
| 9 | `NEC uPD6380/6381/6382/6384 audio DSP datasheet` | No datasheets; led to bitsavers databooks (§3). |
| 10 | `"uPD6380" datasheet NEC DSP pinout` | NOTHING. No datasheet for the sibling either. |
| 11 | `NEC μPD6380 音声処理 DSP エフェクト LSI 100ピン` (Japanese) | Hit: uPD6380 = PC-9801-73 audio DSP (§4). No datasheet. |
| 12 | `PC-9801-73 DSP μPD6380 チップ 型番` | Same as above; confirms part, no docs. |
| 13 | `μPD6380 DSP PC-9801-73 エミュレーション 命令 解析 リバースエンジニアリング` | NOTHING. The PC-98 emulator scene has **not** reverse-engineered the uPD6380 (the -73's DSP effects were reportedly used by almost no software, so emulators ignore it). |
| 14 | `"BRAKST" instruction DSP` | NOTHING. The mnemonic appears nowhere on the indexed web. |
| 15 | `"BR-RQ" "BR-AK" DSP NEC emulator mode "SETRDY"` | NOTHING. The distinctive pin names appear nowhere. |
| 16 | `NEC patent DSP 24-bit multiplier 44-bit ALU external DRAM delay audio effect 1994` | NOTHING relevant (results were Motorola/NXP DSP563xx and unrelated patents). |
| 17 | `patents.google.com NEC "digital signal processor" reverberation delay DRAM flag instruction 1993 uPD audio effect LSI Nippon Electric` | NOTHING relevant. |
| 18 | `Pioneer CDJ-500II service manual IC302 DSP uPD6383 pin description` | Only manual-shop pages; no confirmation the CDJ-500II uses the same IC (see §5). |

## 2. Everything that *was* found for the exact part (all non-technical)

Verification status: seen in search results only; these are e-commerce inventory pages with no
technical content beyond package type. Not worth fetching individually.

* `https://instrumentalparts.com/ic-cmos-up-upd6383gf/` — "IC,(CMOS),UP - UPD6383GF".
  A **Panasonic/Technics service-parts listing** (instrumentalparts sells musical-instrument
  spares) — consistent with the KN5000 use.
* `https://instrumentalparts.com/ic-upd6383gf-3ba-ggc1163/` — "IC,UPD6383GF-3BA", Panasonic
  part code **GGC1163**. This is the Panasonic internal part number for the chip — potentially
  useful if searching Panasonic/Technics parts lists for *other* models that use the same DSP.
* `https://encompass.com/item/1863220/Panasonic/D6383GF-3BA/Ic` — Panasonic spare, same part.
* `https://www.ic2ic.com/search.jsp?sSearchWord=D6383GF&prefix=D` — broker listing, "NEC,
  QFP100". Confirms package only.

**No datasheet aggregator has it.** Explicitly checked and found *absent*:
* alldatasheet.com / alldatasheet.jp (UPD63 series index lists 6325/6326/6335/6336/6345/6360/
  6376/6379/63210/63310/63335 — DACs and audio converters, **no 638x DSP**)
* chipdocs.com UPD63 series index (same list; fetch failed on TLS, but its full part list is
  reproduced in the search-result title and contains no 638x)
* datasheetarchive.com NEC "U" index page 9 — **fetched and verified**: jumps from UPD29x to
  higher series, no UPD638x entry.

## 3. Databooks checked directly (downloaded and grepped) — all negative

* `http://www.bitsavers.org/components/nec/_dataBooks/1989_DSP_and_Speech_Products_Data_Book.pdf`
  — downloaded (14 MB), `pdftotext | grep 638[0-9]` → **no match**. Covers uPD7720/7725/77C25/
  77220 and speech parts only.
* `.../1992_NEC_DSP_and_Speech_Processor_Products.pdf` — downloaded (27 MB), grepped → **no
  match** for 638x.
* NEC Semiconductors Selection Guide, October 1996 (archive.org item
  `nec-semiconductors-selection-guide-databook-october-1996`) — **full OCR text downloaded and
  grepped**: no "6383", no "638x" at all. Its DSP entry for 1996 is the uPD77018 (16-bit,
  100-pin QFP) plus uPD77529 codec. The uPD6383 was in production in 1996 but is **not in NEC's
  own selection guide** → strong evidence it was a *custom/ASSP consumer part* sold direct to
  set makers, never catalogued for general sale. That is exactly the class of part whose
  documentation was distributed only under NDA and essentially never leaks.
* bitsavers `components/nec/_dataBooks/` full directory listing **fetched and verified**: there
  is no NEC consumer-audio / ASSP / 63xx databook there at all. The only consumer-oriented
  volume is `1983_NEC_Integrated_Circuits_for_Consumer_Use.pdf` — a decade too early for a
  1990s DSP, not worth fetching for 6383 (would be worth a 60-second grep if someone is
  passing by, but the part cannot predate ~1990 given its architecture).
* bitsavers `components/nec/` top level: directories are 78K, _appNotes, _dataBooks,
  _dataSheets, mips, speech, uPD7220, uPD783xx, V-Series, V830, V850. **No uPD63xx directory.**

## 4. The one genuinely new lead: the family sibling uPD6380

**Finding (verified by fetching the page):** `https://www.wdic.org/w/CUL/PC-9801-73` — the
Japanese technical dictionary 通信用語の基礎知識 entry for NEC's **PC-9801-73 sound board**
lists among its components "オーディオ用DSP（μPD6380）" — *audio DSP (μPD6380)*. Corroborated
by a second Japanese source in search result #12.

Why this matters: it establishes that **uPD638x is a family of NEC audio-effects DSPs**, that
NEC used one in its *own* PC-98 sound board, and gives a second, much more heavily documented
platform on which a family member appears. PC-98 hardware has a large Japanese hobbyist and
emulator community (Neko Project II / np21w, T. Takeda's emulators, wiki3.jp/pc98emu).

Why it did not pay off (yet): search #13 found **no reverse engineering of the uPD6380**. The
consensus in the Japanese sources is that virtually no software ever used the -73's DSP effects,
so PC-98 emulators never implemented it and no one disassembled its microcode. No uPD6380
datasheet exists online either (#10).

**Unexploited follow-ups on this lead** (for whoever picks this up):
* PC-9801-73 / PC-9801-86 board photos and any circuit tracing on Japanese hobby sites — could
  give a uPD6380 pinout to compare against the CDJ's uPD6383 pin table.
* NEC's own PC-9801-73 *technical* documentation ("PC-9801-73 テクニカルリファレンス" or the
  sound-board section of the PC-9801 hardware books) — if NEC documented how to drive the DSP
  on its own board, that book is by far the most likely place an instruction format was ever
  printed in a publicly-sold volume. **This was NOT checked** (no online copy located in the
  time available; the Japanese used-book / 国立国会図書館 route would be needed). Rated: the
  best remaining shot, but low probability — such refs normally document the *host* interface
  and a canned effect-preset API, not the DSP core ISA.
* Japanese auction/used-book listings for NEC ASSP catalogues (NEC 民生用IC / オーディオ用LSI
  データブック 1993–1996). Not checked; these are the volumes that *would* carry a 638x page,
  and they are not on bitsavers or archive.org.

## 5. Other products / second pin tables

* **Pioneer CDJ-500 / CDJ-500G, service manual RRV1087, IC302** — the known-good source we
  already hold locally at
  `/home/fsanches/compartilhado/kn5000_project/pioneer_cdj-500_cdj-500g_rrv1087.pdf`.
  **Note for future work: this PDF is a pure scan with no text layer** (`pdftotext` yields one
  line for the whole document), so it cannot be grepped — the pin table on manual pages 1-15 to
  1-17 must be read visually or OCR'd. It gives block diagram + 100 pin descriptions, and **no
  instruction set**.
* **Pioneer CDJ-500II (CDJ-500-2)** — service manuals are freely available (elektrotanya
  `pioneer_cdj-500-2_cdj-500ii_sm.pdf`, nodevice, audioservicemanuals, ManualsLib). **NOT yet
  fetched/verified**, and it is **not confirmed** that the II uses the same uPD6383 (search #18
  did not confirm the part number in that manual). Worth 15 minutes: if the II carries the same
  DSP, its manual is a candidate *second* pin table / block diagram, which could confirm or
  extend the RRV1087 information. This is the single cheapest unexplored action.
* No other product using uPD6383 was identified. Searches against keyboards, karaoke, guitar
  processors, home theatre etc. produced nothing. The Panasonic part code **GGC1163** (§2) is
  an untried search key for Panasonic/Technics parts lists of sibling models (KN3000/KN4000/
  KN6000-era, WSA1, SX-PR series) that might share the DSP board.

## 6. Patents

Searched Google Patents indirectly via web search (#16, #17) for NEC audio-DSP architecture
patents matching the distinctive combination (24×24 multiplier → 44-bit ALU, two accumulators,
two shifters, on-chip external-DRAM controller for delay memory, 36-bit instruction word).
**Nothing matching was found.** The hits returned were Motorola/Freescale DSP563xx material and
US5517436 (Digital signal processor for audio applications — **not NEC**; assignee is not NEC
and the architecture does not match). WO1995010138A1 was **fetched and ruled out**: assignee is
Iowa State University Research Foundation, an Am29200-based hardware sampler, entirely unrelated.

This avenue is **not exhausted** — a proper structured Google Patents query
(`assignee:"NEC Corporation"` + CPC G10H/G06F, priority 1990–1995, Japanese-language JP
applications) was not performed, and NEC's JP-only filings would not surface in a plain web
search. Rated: moderate value, since 1990s Japanese DSP patents do sometimes disclose
instruction-field layouts. **Recommended as the top remaining research action.**

## 7. Explicitly ruled out (near-miss parts — do not confuse)

* **uPD63xx D/A converters and audio DACs** (uPD6325, 6335, 6336, 6345, 6360, 6376, 6379,
  63210, 63310, 63335) — these are what fills the "UPD63 series" datasheet indexes. They are
  **converters, not DSPs**, and are irrelevant.
* **uPD7720 / 7725 / 77C25 / 77220** — NEC's famous 1980s 16-bit DSP family (SNES DSP-1, arcade).
  Well documented (bitsavers 1989/1992 databooks) but a **completely different architecture**
  (16/23-bit, no external DRAM delay controller). Not a relative in any usable sense.
* **uPD77016 / 77017 / 77018 / 77210 / 77529** — NEC's 1990s 16-bit general-purpose DSP line.
  Documented, but different word widths and a different core. Not this part.
* **D64083GF, D63A408, D6461, D6571** — distributor fuzzy-match noise from Jotrin.

---

## Verdict and recommendation

**Documentation does not appear to be reachable. Plan on inferring the instruction set.**

Reasoning:
1. The part is absent from every NEC databook and selection guide of its era, including NEC's
   own October 1996 selection guide — it was a set-maker ASSP, not a catalogue product.
2. It has essentially zero web footprint: even the exact string "6383GF" returns nothing but
   two spare-parts shops. Distinctive strings from its own pin table (`BRAKST`, `SETRDY`,
   `BR-RQ`/`BR-AK`) return **zero** hits worldwide, which is about as strong a negative as this
   kind of search can produce.
3. Its documented sibling uPD6380 shipped in NEC's own PC-9801-73 board and *still* was never
   documented publicly nor reverse-engineered by the very active PC-98 community.

Residual actions, in descending value-per-hour, if anyone wants to spend more time:
1. **Structured Google Patents search** — assignee NEC, 1990–1996, audio DSP / 残響 /
   ディジタル信号処理装置, including JP-language filings. Patents are the one channel that
   publishes ASSP internals against the maker's wishes.
2. **Pioneer CDJ-500II service manual** — cheap, and might yield a second pin table.
3. **Japanese used-book hunt** for a mid-90s NEC consumer/audio LSI databook, and the
   PC-9801-73 technical reference.
4. Search Panasonic parts code **GGC1163** across Technics service parts lists to find sibling
   models (more schematics = more pin/interface detail).

None of these are likely to produce an ISA. The inference route (analysing the extracted 36-bit
program words against the known register/pointer set from the CDJ pin table, plus observed host
behaviour) should be treated as the primary path, not the fallback.
