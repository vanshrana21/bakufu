# MOIL Mine Coordinates — Reconciled from MOIL AR FY2023-24, MoEFCC/PARIVESH EC Documents, and Wikipedia

## Method actually used (important caveat)

Your instruction assumed all three sources would carry coordinates. In practice:

- **MOIL Annual Report FY2023-24** (`Annual_Report_2023-24.pdf`, moil.nic.in) lists the 10 mines and groups them by district (Nagpur/Bhandara, Maharashtra; Balaghat, Madhya Pradesh) but contains **no latitude/longitude anywhere in the document** — the "Geographic Footprint" section is a graphic map, not a coordinate table. So source (a) contributed *district-level* context only, never a tiebreak-worthy number.
- **parivesh.nic.in / environmentclearance.nic.in (MoEFCC)** did carry real numbers, but only for the mines that have had a recent Pre-Feasibility Report (PFR), Environmental Clearance filing, or MPCB public-hearing Executive Summary put online. These give either a full boundary-pillar table (best case) or a single stated center point.
- **Wikipedia** has infoboxes only for the *settlements* Ukwa, Tirodi, and Kandri — there is no Wikipedia article for a "Chikla mine," "Gumgaon mine," etc. So it served as a tiebreak/cross-check for 3 of 10 mines, not all 10.

Where a regulatory (MoEFCC-adjacent) document and Wikipedia agreed, I adopted that value with high confidence. Where they diverged (Kandri), I followed your stated precedence and kept the regulatory document. Where neither MOIL AR nor MoEFCC had anything and Wikipedia had no article, I labeled the entry low-confidence and used the best secondary source I could verify, rather than silently inventing a number.

## Final coordinates

| # | Mine | State | Adopted coordinates (decimal) | Adopted coordinates (DMS) | Confidence | Primary source |
|---|------|-------|-------------------------------|----------------------------|------------|----------------|
| 1 | Balaghat | Madhya Pradesh | 21.8333°N, 80.2333°E | 21°50′N 80°14′E | High | Govt. subsidence report (forestsclearance.nic.in) + MoEFCC PFR boundary centroid (21.8385°N, 80.2272°E) agree to within ~1 km |
| 2 | Ukwa | Madhya Pradesh | 21.9667°N, 80.4667°E | 21°58′N 80°28′E | High | Govt. subsidence report (forestsclearance.nic.in), **exact match** with Wikipedia (21.97°N, 80.47°E) |
| 3 | Dongri Buzurg | Maharashtra | 21.5500°N, 79.6941°E | 21°33′00″N 79°41′39″E | Low–Medium | Wikipedia (Dongri Buzurg railway station, a proxy — no EC/PFR coordinate document could be located) |
| 4 | Chikla | Maharashtra | 21.5443°N, 79.7614°E | ≈21°32′40″N 79°45′41″E | High | MPCB Executive Summary for EC (mpcb.gov.in), boundary-pillar centroid; toposheet 55 O/10 & 14 |
| 5 | Tirodi | Madhya Pradesh | 21.6830°N, 79.7310°E | 21°40′59″N 79°43′52″E | Low–Medium | Wikipedia (Tirodi town, a proxy — no mine-specific EC/PFR coordinate found) |
| 6 | Gumgaon | Maharashtra | 21.400°N, 78.980°E | ≈21°24′N 78°58′48″E | High | MoEFCC PFR (environmentclearance.nic.in), full 95-pillar boundary table, centroid |
| 7 | Kandri | Maharashtra | 21.4125°N, 79.2667°E | 21°24′45″N 79°16′00″E | High | MPCB EC Executive Summary — **overrides Wikipedia**, which resolves to a different village (19.98°N, 80.43°E, a Kandri elsewhere in Maharashtra) |
| 8 | Munsar | Maharashtra | 21.3958°N, 79.2792°E | ≈21°23′45″N 79°16′45″E | Medium–High | MoEFCC PFR (environmentclearance.nic.in), stated center of the two lease blocks; toposheet 55 O/7 |
| 9 | Beldongri | Maharashtra | 21.3495°N, 79.3003°E | 21°20′58″N 79°18′01″E | Low | USGS MRDS via TheDiggings.com (no MOIL AR, MoEFCC, or Wikipedia coordinate available) |
| 10 | Sitapatore | Maharashtra | **Not found** | — | None | No coordinate in any of the three specified sources, nor in MPCB/IBM records searched. Only the district (Bhandara) and tehsil (Tumsar) context is confirmable. |

## Notes on discrepancy handling

- **Kandri** is the one case where sources genuinely disagreed. The Wikipedia article titled "Kandri" carries coordinates (19°59′N 80°26′E) for a different village of the same name, inconsistent with the MPCB Executive Summary's explicit statement that the mine is "42 km NE of Nagpur in Ramtek Tehsil" (i.e., ~21.4°N 79.3°E) — which is also corroborated by the adjacent Munsar mine's PFR, which lists "Kandri" as one of its own lease villages at the same coordinates. Per your precedence rule, the regulatory document wins.
- **Balaghat** and **Ukwa**: MoEFCC-adjacent regulatory filings (subsidence reports lodged with forestsclearance.nic.in, a MoEFCC portal) and Wikipedia independently agree to within about a kilometer or exactly, respectively — a good validation that both are reliable for these two.
- **Gumgaon** and **Chikla** have the best precision of all ten, because their PFR/EC filings include full cadastral boundary-pillar tables (not just a center point) — I computed simple centroids from those tables; the underlying pillar-by-pillar coordinates are available if you need the polygon rather than a point.
- **Dongri Buzurg, Tirodi, Beldongri, Sitapatore**: despite searching MOIL's AR/SDU pages, environmentclearance.nic.in, MPCB, MPPCB, IBM, and Wikipedia, I could not locate a mine-specific coordinate in any of your three named sources for these four. Dongri Buzurg and Tirodi fall back to a nearby settlement's Wikipedia coordinate (labeled proxy, not mine-boundary); Beldongri falls back to a USGS-derived third-party database; Sitapatore has no located coordinate at all — flagging this rather than guessing.

## Suggested next step for the three weakest entries (Beldongri, Sitapatore, Dongri Buzurg precision)

MOIL's own Mining Plans (filed with IBM, not published online) or an RTI request to MOIL/IBM Nagpur Regional Office would carry the exact lease boundary coordinates. The MPCB public-hearing process (mpcb.gov.in) is also worth periodically re-checking — Executive Summaries appear there only when a mine files for expansion/renewal, and Sitapatore's may simply not have gone through that process recently.

---

## Implementation notes (2026-09-13)

The coordinates were loaded into `src/config/settings.py` (`MOIL_MINES`) and
are served by `/mines`. Where the submitted table differed from this document,
or broke the citation rules, the handling was:

**Sitapatore uses the MOIL Mining Plan point, not "Not found".** A later
submission supplied it with a full URL:

- 21.7000 N, 79.6667 E, Madhya Pradesh / Balaghat, opencast, confidence high
- <https://forestsclearance.nic.in/DownloadPdfFile.aspx?FileName=611712291216JLTFUMiningplan.pdf>
- Note: *"Village Sitapatore, PO Sukli, Tirodi tehsil. Located ~12 km from the
  larger Tirodi Manganese Mine. Regional deposit area extends slightly south
  (21.6667N 79.6667E per Mindat)."*

This supersedes row 10 above, which placed it in Maharashtra/Bhandara. The
state and district match `src/reference/moil_mines.py`.

**Six sources have no full URL yet.** The submitted links were truncated
(`https://…nic.in/...`), so `source_url` is `null` rather than a guessed
address. The source is still named.

| mine | named source | URL needed |
|---|---|---|
| Balaghat | MoEFCC PFR boundary centroid + subsidence report (forestsclearance.nic.in) | yes |
| Chikla | MPCB EC Executive Summary boundary centroid (mpcb.gov.in) | yes |
| Gumgaon | MoEFCC PFR 95-pillar boundary centroid (environmentclearance.nic.in) | yes |
| Kandri | MPCB EC Executive Summary | yes |
| Munsar | MoEFCC PFR stated center of two lease blocks (environmentclearance.nic.in) | yes |
| Beldongri | USGS MRDS via TheDiggings.com | yes |

For every mine this document still lacks an **access date**, a **document
ID** (EC or PFR reference) and the **section or page** that held the
coordinate.

**Mine type not verified against a primary source: Tirodi, Dongri Buzurg.**
The submission listed both as underground, citing only Wikipedia settlement
proxies (Tirodi town, Dongri Buzurg railway station). The served type stays
**opencast**, as recorded in `src/reference/moil_mines.py`, until a MOIL
annual report or EC filing states otherwise.

**Confidence tiers as served:**

| tier | mines |
|---|---|
| high | Balaghat, Ukwa, Chikla, Gumgaon, Kandri, Sitapatore |
| medium_high | Munsar |
| low_medium | Dongri Buzurg, Tirodi (settlement proxies, approximate) |
| low | Beldongri (third-party USGS database, approximate) |

`/mines` returns a `coordinate_note` for every low, low_medium or approximate
entry, so the frontend can caution against reading those points as surveyed
mine boundaries.
