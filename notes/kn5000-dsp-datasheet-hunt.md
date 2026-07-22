# NEC uPD6383GF — documentation hunt (KN5000 effects DSP, IC311)

**Date:** 2026-07-22
**Goal:** find a datasheet / databook page / programming manual / assembler for the NEC
uPD6383GF-3BA, the effects DSP of the Technics SX-KN5000 (IC311), so its 36-bit instruction
set can be decoded and the core emulated in MAME.

**BOTTOM LINE (verdict): no instruction-set documentation for the uPD6383 exists on the
public web.** Nothing was found beyond distributor stock listings. The chip is an NEC
consumer-ASSP audio DSP that was never published in any general NEC databook, is absent from
every online datasheet aggregator checked, and has no community/forum footprint at all.
**The instruction set must be inferred.** (See **ROUND 2** at the end of this file for the
follow-up actions, which found the family's host-interface register semantics, an NEC patent
describing the memory/pointer subsystem, and a lead on a second microprogram corpus — but still
no ISA.) One new lead of secondary value was found (the
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

---

# ROUND 2 (same day) — the residual actions were carried out

The four follow-ups listed above were executed. The **verdict is unchanged** (no ISA
documentation exists), but round 2 produced **one genuinely useful primary source** and **one
strong new actionable lead**. Details below.

## R2.1 ★ NEW PRIMARY SOURCE: the uPD6380 host-interface registers, documented

**URL:** `https://www.webtech.co.jp/company/doc/undocumented_mem/io_sound.txt`
(index: `https://www.webtech.co.jp/company/doc/undocumented_mem/`)
**Status: DOWNLOADED AND READ IN FULL** (Shift-JIS plain text, 31 KB). This is the well-known
Japanese *PC-9801 undocumented I/O* reference by Terumasa Kodaka & Takeshi Kono (1994-1997),
hosted by Webtech/CRI. It is a serious, long-standing reverse-engineering document.

It contains a dedicated section **［オーディオ用DSP(μPD6380)の概要］** and per-port entries.
Verbatim content (translated), for the **PC-98GS and PC-9801-73** sound hardware:

* The PC-9801-73 sound function uses the audio DSP **μPD6380**; the DSP implements ADPCM and
  **real-time effects**. DSP control is provided by the extended sound driver
  **AVSDRV.SYS / AVSDRV.EXE**.
* **I/O A462h — μPD6380 control** (byte, R/W):
  * WRITE: bit7 = *Command/data control*; bit6 = *DSPEXT-R read flag*; bit5 = **DSP reset flag**;
    bit1 = *SO2 output on/off*; bit0 = *SO1 output on/off*.
  * READ: bit7 = *Command/data status*; bit6 = **DSP read busy flag**; bit5 = **I-RAM modify
    status**; bit3 = **DSP write ready flag**; bit1 = **DSP GF**; bit0 = **DSP OVF**.
* **I/O A464h — μPD6380 data port** (byte, R/W): bits 7-0 = DSP data port.
* The document then says: *"For details of the DSP, refer to the manufacturer-issued
  datasheet."* — i.e. even these authors had no datasheet and did not reproduce one. (Another
  independent confirmation that the datasheet was never public.)

**Why this matters to the KN5000 work.** It is the first *independent* corroboration of the
uPD638x family host-interface model, and it lines up point-for-point with the uPD6383 pin table
in the Pioneer RRV1087 manual:
* `GF` — the general flags GF1-GF3 that instructions set/reset/toggle, visible to the host.
* `OVF` — an ALU overflow/saturation status also exported to the host.
* **`I-RAM modify status`** — direct confirmation that the host uploads the instruction RAM and
  that there is a *status bit telling the host when an I-RAM write is in progress/complete*.
  Anything the KN5000 firmware does around its DSP status port should be re-read with this
  mapping in mind.
* A **byte-wide** data port plus a **command/data** discriminator bit — the same "parallel or
  serial host interface" the RRV1087 pin table describes, here in its parallel form.
* `SO1`/`SO2` output enables map onto the "3 serial audio out" of the 6383.

This is a *pin/interface-level* find only. **It contains no instruction set, no opcode field
layout, and no register file description.**

## R2.2 ★ NEW ACTIONABLE LEAD: AVSDRV.SYS contains uPD6380 microcode

Following directly from R2.1: NEC's own **AVSDRV.SYS / AVSDRV.EXE** (the PC-9801-73 / PC-98GS
extended sound driver, shipped by NEC with MS-DOS 5.0/6.2 for those machines) **drives the
uPD6380 and therefore must contain the I-RAM images it uploads** — a *second corpus of
uPD638x DSP microprograms whose effects are named and whose semantics are known* (the -73's
advertised effects were reverb and chorus, the same two we care about on the KN5000).

For ISA inference this is potentially worth as much as a datasheet: two independent program
corpora for the same instruction set, one of them with a labelled host-side API, massively
constrains opcode-field hypotheses.

**Status: NOT YET OBTAINED.** A search for a download did not turn up a direct link. Where to
look next (untried):
* PC-98 driver archives and DOS 5.0/6.2 for PC-98 disk images (Neko Project / np21w community
  distributions, `simk98.github.io/np21w`, PC-98 software archives, dw230.com driver lists).
* NEC's own legacy download server appeared in results
  (`search.casnavi.nec.co.jp/download/pc/module/...`) — worth probing for the -73/-86 sound
  modules.
* Any PC-98GS system disk image (the GS shipped with the DSP and its driver).

**Availability update (verified):** `AVSDRV.SYS` is **not rare** — it was bundled onto PC-98
*game* boot floppies. Confirmed by fetching dosbox-x issue #1210
(`https://github.com/joncampbell123/dosbox-x/issues/1210`), where AVSDRV.SYS is present on the
boot floppy of *Policenauts* (PC-9821) and DOSBox-X fails to install it. So any decent PC-98
floppy-image archive should yield a copy in minutes. **Caution:** the dosbox-x thread calls
AVSDRV.SYS "the Qvision PCM audio card" driver and says nothing about the uPD6380 — the name
may be reused across NEC AV sound products, so *verify the copy you obtain actually touches
I/O A462h/A464h* (trivial to check: search the binary for those port numbers) before assuming
it contains uPD638x microcode.

Caveat before anyone invests: it is possible AVSDRV only exposes canned firmware already in a
board ROM. Check whether the -73 board carries a ROM next to the uPD6380 before assuming the
microcode is in the driver file.

## R2.3 Patents — done properly this time (via the Google Patents XHR API)

Method that works (the HTML UI is a JS SPA and returns nothing to WebFetch):
`https://patents.google.com/xhr/query?url=<urlencoded query string>`, e.g.
`q=reverberation+"digital+signal+processor"&assignee=NEC&before=priority:19970101&after=priority:19880101`.
Returns JSON. **Note: it rate-limits hard (503) after ~5 queries; back off for several minutes.**

Verified negative: `q="μPD6383"` and `q="uPD6383"` → **0 results across all of Google Patents.**

Results of the structured NEC searches (all publication data verified from the API response):

* **JPH08166795A — NEC Corp, priority 1994-12-14, "ディジタルシグナルプロセッサ (Digital
  signal processor)"** — **FETCHED AND READ. This is the closest architectural disclosure
  found anywhere, and it is very probably about this chip family.** It describes a DSP that
  **unifies PCM sound-source generation and audio effects in one chip** (explicitly motivated by
  prior art needing separate LSIs), with a **memory address generation circuit** that divides a
  **large external memory into predetermined block regions — "echo area, reverb area A, reverb
  area B"** plus PCM sample areas. Hardware: an **offset memory** (per-region base), a **pointer
  memory** (per-region current position), an **adder** producing offset+pointer, an **AND circuit**
  for boundary detection / pointer wrap, latches and selectors. Regions behave as **ring buffers**
  for delay effects while PCM areas are accessed at fixed locations. This is exactly the
  "external DRAM controller for digital delay + CP/DP/BP1/BP2/PR1/PR2 pointer set + bank
  register" arrangement seen in the uPD6383 pin table, described in words. Timing (Dec 1994)
  fits a part in production by 1996. **It does NOT disclose instruction word width, opcode
  fields, flag names, or the host interface** — it is an address-generator patent, not a core
  patent. Still: it is the best public description of *what the pointer/bank machinery does*,
  and should be read in full by whoever infers the ISA.
* **JPH04142600A — NEC Corp, priority 1990-10-04, "Memory address generator of voice
  processor"** — **FETCHED AND READ.** Earlier, simpler relative of the above: counter +
  subtracter generating ring-buffer addresses for **multiple delay lines with differing delay
  amounts**, upper address bits fixed per unit, lower bits cycling. Confirms the design lineage.
  No ISA content.
* Other hits noted but not fetched (Google Patents began returning 503): **JPH05313889A** (NEC
  Corp, priority 1992-05-07, "Digital signal processor" — surfaced by a *loop counter* query, so
  it is the **most promising unread candidate** given the 6383's LC1-LC3 loop counters);
  **JPH052479A** (NEC IC Microcomputer Systems, priority 1991-06-25, "Digital signal
  processor"); JPH02295400A / JPH04328797A / JPH08314684A (NEC Home Electronics — sound-field
  and audio-information processing, application-level).
* Ruled out as irrelevant: EP0712231A2 (echo canceller), US5790657A (echo suppressor),
  US5375238A (loop nesting, general CPU).

**Verdict on patents: the avenue is real but has now largely been mined.** NEC patented the
*memory/address* subsystem, not the instruction encoding. Two candidate patents remain unread
(JPH05313889A, JPH052479A) — cheap to check when Google Patents un-throttles, and JPH05313889A
is the one worth reading.

## R2.4 Pioneer CDJ-500II — ruled out as a second pin table

`https://www.manualslib.com/manual/962593/Pioneer-Cdj-500ii.html` — **fetched.** The CDJ-500II
service manual is **order no. RRV2031 and only 6 pages** — a *supplement* to the CDJ-500 manual,
containing a parts-difference list and schematic sheets, not a full IC-description section. It
does reference "TO IC302 BUS" on the schematic (so the II very likely carries the same DSP), but
it will not contain a second pin table. **Not worth pursuing further.**
Also noted: elektrotanya's copy is behind a **captcha** (verified — the download page returns a
captcha form, no direct PDF href), so it is not fetchable by tooling anyway.

## R2.5 Panasonic part code GGC1163 — negative

Searched `"GGC1163" Panasonic Technics part`. **NOTHING** — no parts list, no other model, only
generic Panasonic parts-portal pages. The code is only visible on the instrumentalparts listing.
Panasonic's own parts portal (`panasonic.encompass.com`) would need an interactive search to
enumerate which models order GGC1163; not doable with these tools, and unlikely to yield ISA
information even if it worked (it would only find sibling *products*).

## R2.6 PC-9801-73 / PC-98GS technical references — partially answered

Japanese searches confirmed (multiple independent sources, wdic.org fetched and verified) that
the uPD6380 was NEC's **PC-98GS** audio DSP first, inherited by the **PC-9801-73**, doing
**chorus and reverb**; the PC-9801-86 is a -73 with the effects (and the DSP) removed. No NEC
technical reference reproducing the DSP's programming model was found online. The Webtech
document (R2.1) is the community's best effort and it explicitly defers to a datasheet it did
not have. Also checked and found to contain **no** DSP material: the same site's `io_gs.txt`
(PC-98GS I/O) and `io_music.txt` — downloaded and grepped, zero hits for 6380/DSP.

---

## REVISED BOTTOM LINE

**Unchanged: there is no instruction-set documentation. The uPD6383 ISA must be inferred.**
Round 2 did not find a datasheet and produced a third independent confirmation that none was
ever published (the Webtech authors, who reverse-engineered the host ports in the 1990s, had to
tell readers to "refer to the manufacturer's datasheet" because they did not have one).

What round 2 *did* change:
1. We now have **independently-sourced host-interface semantics** for the family (GF, OVF,
   I-RAM modify status, read-busy, write-ready, command/data, DSP reset) — directly useful for
   interpreting the KN5000 firmware's DSP port accesses.
2. We now have a **patent (JPH08166795A) describing the pointer/offset/ring-buffer memory
   subsystem** in prose — useful background for decoding pointer-manipulation instructions.
3. There is a **new, high-value lead worth real effort: obtaining AVSDRV.SYS** (or a PC-98GS /
   PC-9801-73 system disk) to recover a second corpus of uPD638x microprograms with known
   effect semantics.

Recommended next actions, in order:
1. **Hunt AVSDRV.SYS** in PC-98 software archives (§R2.2). Highest expected value of anything
   remaining.
2. Read **JPH05313889A** (and JPH052479A) when Google Patents un-throttles — the loop-counter
   query surfaced it, so it may touch the control unit.
3. Proceed with ISA inference regardless; do not block on any of the above.

---

# ROUND 3 — acquisition (uPD6380 corpus / MAME angle)

## R3.1 ★ ACQUIRED: NEC's own PC-9800 Technical Data Books (CD-ROM editions)

Found via the archive.org advanced-search API and **downloaded in full**. Item:
`https://archive.org/details/pc-9800-tdb-cd` — *PC-9800シリーズテクニカルデータブック
CD-ROM版*. Two ISOs, **both now stored locally at `/home/fsanches/compartilhado/pc98_tdb/`**:

* **`PC98Docs1stEd.iso`** (601 MB, Publisher: **NEC CORPORATION**, 1994-09-01). Contains
  `BI.ABV`, `HW.ABV` and — the important one — **`MM.ABV`**, whose header reads (verified by
  decoding the Shift-JIS at offset 0x24):
  `PC-9800シリーズ テクニカルデータブック MULTIMEDIA編`
  The MULTIMEDIA volume is precisely where NEC documented the PC-98GS / PC-9801-73 sound
  subsystem — i.e. the **uPD6380**. Raw strings in `MM.ABV` include index entries `PCM/DSP`
  and `DSP`.
* **`PC98TDB.ISO`** (83 MB, 1995-09-28) — a later, Windows-installer edition with `HW.ABV`,
  `APL.ABV`, `WIN95.ABV`.

**Blocker: the `.ABV` container is compressed and undecoded.** The bundled reader is
`ABV.EXE` = **"ASCII Book Viewer Version 2.0, Copyright(C) ASCII Corp. 1994-1995"**, a 16-bit
**NE Windows 3.1** executable. Body text is not plain Shift-JIS; only the title header and a few
index strings are readable raw. Searched for an existing converter (`abv2txt`, "ASCII Book
Viewer" format, Japanese and English queries) — **none exists publicly.**

Two ways forward, both straightforward but not doable in this environment (no `wine`, no
`dosbox-x` installed here):
* **Run ABV.EXE** under wine with win16 support (needs a 32-bit prefix) or in a Japanese
  Windows 3.1 / 95 VM, and read/print the sound chapter. Fastest path.
* **Reverse the ABV container** (it is a 1994 ASCII Corp e-book format; header at 0x00 has a
  small table of 32-bit offsets/sizes, title at 0x24). A modest RE task, and it would unlock
  *all three volumes* of NEC's technical data books for the PC-98 preservation community — a
  worthwhile artifact in its own right.

**This is now the single most promising documentation lead in the whole hunt.** It is NEC's own
technical documentation for a machine NEC built around a uPD638x DSP. It will almost certainly
document the host registers and the effect API; whether it goes as far as the DSP's *instruction
set* is unknown (probably not — but the "MULTIMEDIA" volume is a hardware-programming book, so
it is not a silly hope).

## R3.2 MAME status for the uPD6380 platform — checked in the local tree

* **MAME has no PC-9801-73 device.** `src/devices/bus/pc98_cbus/` has `pc9801_26`, `_86`, `_96`,
  `_118`, `speakboard`, `wavestar`, etc., but no `_73`.
* **MAME already knows the ports.** `src/devices/bus/pc98_cbus/pc9801_86.cpp` contains, in the
  I/O map, the commented-out lines:
  `//  map(0xa462, 0xa462) μPD6380 for PC9801-73 control`
  `//  map(0xa464, 0xa464) μPD6380 for PC9801-73 data`
  and its board-ID table already enumerates `0001 ---- PC-98GS built-in` and
  `0010/0011 ---- PC-9801-73/-76`.
* `src/mame/nec/pc9801.cpp` line ~2973 has a comment describing PC-98GS as having the
  "-73 sound board (a superset of later -86)". So the PC-98GS driver skeleton is aware of it.

**Implication:** if a uPD638x CPU core is ever written for the KN5000, a `pc9801_73` C-bus
device is a small, natural, upstreamable MAME contribution that would give the core a *second*
independent test platform with real software. Conversely, the -73 board almost certainly carries
a sound-BIOS ROM that is **not dumped** in MAME; that would need hardware.

## R3.3 Negative: AVSDRV.SYS not yet located

* `archive.org` full-item search for `AVSDRV` → **0 results.**
* Downloaded and checked **NEC MS-DOS 5.0A Rev.5 + Expansion**
  (`https://archive.org/details/nec-msdos50ar5`, all five `.hdm` floppy images incl.
  `extdev.hdm` = 拡張デバイス disk): **no AVSDRV.SYS** (that disk carries NECAI.SYS etc.).
* Remaining candidates, **not downloaded**: the Policenauts PC-98 item
  (`https://archive.org/details/policenauts-pc98`, a 584 MB zip whose boot floppy is reported by
  dosbox-x issue #1210 to contain AVSDRV.SYS) — but note that thread calls it the *Qvision PCM*
  driver, so it may be the PC-9801-86 variant that never touches the uPD6380. **Verify by
  searching any recovered copy for the byte patterns of ports A462h/A464h.**
* Best untried sources: NEC's own legacy module server (`search.casnavi.nec.co.jp/download/pc/
  module/...`), Japanese PC-98 driver archives (`dw230.com/98/dr2.php`,
  `navitoku.jp/archive/nx-station/support_pc98.html`), and any **PC-98GS** system/utility disk.

## R3.4 ★ URLs I could NOT fetch — for Felipe to grab

Highest value first:

1. **PC-9801-73 (or PC-98GS) driver / utility floppy containing `AVSDRV.SYS`** — no single URL;
   this needs a human with access to Japanese PC-98 archives or a PC-98GS disk set. Payload
   wanted: `AVSDRV.SYS` / `AVSDRV.EXE`, and anything else on the -73's bundled disk. Verify it
   references I/O **A462h/A464h** before assuming it drives the uPD6380.
2. **Anything that decodes `.ABV`** — or simply: run `ABV.EXE` from
   `/home/fsanches/compartilhado/pc98_tdb/PC98Docs1stEd.iso` under wine/Win3.1 and export the
   **MULTIMEDIA volume's sound chapter** (µPD6380 / PCM / DSP sections). The ISOs are already
   on disk here; only the viewer is missing.
3. **Google Patents pages that 503'd on me** (rate limiting, not access control — they may work
   for you, or for me later):
   * `https://patents.google.com/patent/JPH05313889A/ja` — NEC, priority 1992-05-07, "Digital
     signal processor". **Most promising unread patent** (surfaced by a loop-counter query).
   * `https://patents.google.com/patent/JPH052479A/ja` — NEC IC Microcomputer Systems,
     priority 1991-06-25, "Digital signal processor".
   * `https://patents.google.com/patent/JPH08166795A/ja` — the Japanese original of the
     address-generator patent I read in English translation; the JA text may name registers.
4. **Pioneer CDJ-500II service manual** — `https://elektrotanya.com/pioneer_cdj-500-2_cdj-500ii_sm.pdf/download.html`
   (**captcha-gated**, verified: the download page returns a captcha form and no direct PDF
   href). ⚠️ **Low value** — it is only the 6-page supplement RRV2031, not a second pin table.
   Do not spend effort on this unless it is free.
5. **chipdocs UPD63 series index** — `http://www.chipdocs.com/datasheets/datasheet-pdf/NEC-Electronics-Inc/UPD63.html`
   — WebFetch failed with *"unable to verify the first certificate"* (broken TLS chain). Its
   part list was visible in search-result text and contains no 638x, so this is **almost
   certainly a dead end**; listed only for completeness.
6. **OCR of our own Pioneer RRV1087 PDF** — not a URL, but worth doing: the local file
   `/home/fsanches/compartilhado/kn5000_project/pioneer_cdj-500_cdj-500g_rrv1087.pdf` has **no
   text layer**, so the uPD6383 pin table cannot be grepped or diffed against the uPD6380 port
   description in §R2.1. Running OCR over pages 1-15…1-17 would make it searchable.
