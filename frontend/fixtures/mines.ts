/** Reference snapshot of GET /mines, taken 2026-09-21 from the live backend.
 *
 * Used only when no backend is configured, so the Mine Fleet page and the
 * Explorer still show the ten real MOIL mines and their cited coordinates.
 * It carries no scores: those come from the live model and are never invented.
 */

import type { WireMine } from "@/lib/api/wire";

export const MINES_REFERENCE_DATE = "2026-09-21T00:00:00Z";

export const MINES_REFERENCE: readonly WireMine[] = [
  {
    "mine_name": "Balaghat",
    "state": "MP",
    "district": "Balaghat",
    "mine_type": "underground",
    "equipment": [
      "SDL",
      "rocker_shovel",
      "shaft_sinking_rig"
    ],
    "capacity_target_tonnes": 800000,
    "notes": "Company's largest mine; described as the deepest underground manganese mine in Asia. Large-diameter high-speed vertical shaft under sinking (750 m planned, revised to 660 m); an earlier shaft deepening is already complete. SDL bucket capacity 0.66 cu.m.",
    "sources": [
      {
        "tag": "IBM_2022",
        "url": "https://ibm.gov.in/writereaddata/files/17125770456613da1576db0Manganese_Ore_2022.pdf"
      },
      {
        "tag": "MOIL_AR_2023-24",
        "url": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2023-24.pdf"
      },
      {
        "tag": "MOIL_AR_2022-23",
        "url": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2022-23.pdf"
      }
    ],
    "type_note": null,
    "lat": 21.8333,
    "lon": 80.2333,
    "confidence": "high",
    "source": "MoEFCC PFR boundary centroid + subsidence report (forestsclearance.nic.in)",
    "source_url": null,
    "coordinate_precision": null,
    "coordinate_note": null
  },
  {
    "mine_name": "Ukwa",
    "state": "MP",
    "district": "Balaghat",
    "mine_type": "underground",
    "equipment": [
      "rock_mechanics_monitoring"
    ],
    "capacity_target_tonnes": null,
    "notes": "No production fleet disclosure; the only equipment named in any source is rock mechanics monitoring instrumentation. Vertical shaft sinking to 324 m in progress as of the 2020 yearbook; a second vertical shaft is reported complete in AR 2023-24.",
    "sources": [
      {
        "tag": "IBM_2020",
        "url": "https://ibm.gov.in/writereaddata/files/04272022163406Manganese_2020.pdf"
      },
      {
        "tag": "MOIL_AR_2023-24",
        "url": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2023-24.pdf"
      }
    ],
    "type_note": null,
    "lat": 21.9667,
    "lon": 80.4667,
    "confidence": "high",
    "source": "MoEFCC subsidence report + Wikipedia agree",
    "source_url": "https://en.wikipedia.org/wiki/Ukwa",
    "coordinate_precision": null,
    "coordinate_note": null
  },
  {
    "mine_name": "Sitapatore",
    "state": "MP",
    "district": "Balaghat",
    "mine_type": "opencast",
    "equipment": [
      "standard_opencast_fleet"
    ],
    "capacity_target_tonnes": null,
    "notes": "No equipment disclosure found. Opencast classification comes from company material cited on Wikipedia and is not corroborated by a primary MOIL document. EC of 4.734 ha granted in FY2023-24.",
    "sources": [
      {
        "tag": "MOIL_AR_2023-24",
        "url": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2023-24.pdf"
      },
      {
        "tag": "WIKIPEDIA_MOIL",
        "url": "https://en.wikipedia.org/wiki/MOIL"
      }
    ],
    "type_note": null,
    "lat": 21.7,
    "lon": 79.6667,
    "confidence": "high",
    "source": "MOIL Mining Plan (forestsclearance.nic.in) + cross-referenced with MOIL AR 2025-26",
    "source_url": "https://forestsclearance.nic.in/DownloadPdfFile.aspx?FileName=611712291216JLTFUMiningplan.pdf",
    "coordinate_precision": null,
    "coordinate_note": "Village Sitapatore, PO Sukli, Tirodi tehsil. Located ~12 km from the larger Tirodi Manganese Mine. Regional deposit area extends slightly south (21.6667N 79.6667E per Mindat)."
  },
  {
    "mine_name": "Tirodi",
    "state": "MP",
    "district": "Balaghat",
    "mine_type": "opencast",
    "equipment": [
      "drill_100mm",
      "hydraulic_shovel_0.9_to_1.7_m3",
      "dumper_20_to_25t",
      "bench_management"
    ],
    "capacity_target_tonnes": null,
    "notes": "Dumper-shovel opencast operation and the most completely specified fleet in public sources. Overburden benches kept at 7.5 m, ore benches at 6 m. EC of 4.419 ha granted in FY2023-24.",
    "sources": [
      {
        "tag": "IBM_2022",
        "url": "https://ibm.gov.in/writereaddata/files/17125770456613da1576db0Manganese_Ore_2022.pdf"
      },
      {
        "tag": "MOIL_AR_2023-24",
        "url": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2023-24.pdf"
      }
    ],
    "type_note": null,
    "lat": 21.683,
    "lon": 79.731,
    "confidence": "low_medium",
    "source": "Wikipedia Tirodi town proxy (no mine-specific EC found)",
    "source_url": "https://en.wikipedia.org/wiki/Tirodi",
    "coordinate_precision": "approximate — town centroid, mine may be 1-3 km offset",
    "coordinate_note": "Coordinate confidence is low_medium (approximate — town centroid, mine may be 1-3 km offset). Treat as an approximate location, not a surveyed mine boundary."
  },
  {
    "mine_name": "Gumgaon",
    "state": "MH",
    "district": "Nagpur",
    "mine_type": "underground",
    "equipment": [
      "SDL",
      "electro_hydrostatic_drill",
      "shaft_sinking_rig"
    ],
    "capacity_target_tonnes": 350000,
    "notes": "Large-diameter high-speed vertical shaft sinking to 330 m in progress, INR 194 crore capital cost per the annual report. The electro-hydrostatic drill is an experimental introduction shared with Chikla.",
    "sources": [
      {
        "tag": "IBM_2020",
        "url": "https://ibm.gov.in/writereaddata/files/04272022163406Manganese_2020.pdf"
      },
      {
        "tag": "MOIL_AR_2023-24",
        "url": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2023-24.pdf"
      },
      {
        "tag": "MOIL_AR_2022-23",
        "url": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2022-23.pdf"
      }
    ],
    "type_note": null,
    "lat": 21.4,
    "lon": 78.98,
    "confidence": "high",
    "source": "MoEFCC PFR 95-pillar boundary centroid (environmentclearance.nic.in)",
    "source_url": null,
    "coordinate_precision": null,
    "coordinate_note": null
  },
  {
    "mine_name": "Kandri",
    "state": "MH",
    "district": "Nagpur",
    "mine_type": "underground",
    "equipment": [
      "dumper_20_to_25t",
      "water_tanker_sprinkler",
      "hydraulic_sand_stowing",
      "shaft_sinking_rig"
    ],
    "capacity_target_tonnes": 100000,
    "notes": "Expansion proposal 0.063 MTPA to 0.100 MTPA. The EC executive summary describes the method as opencast/underground (ripping/dozing, drilling, manual sorting and sizing, mechanised loading and transport) and cites roughly 5-6 dumpers of 20 t for the added transport load. Hydraulic sand stowing replaced manual filling; shaft deepening to 245 m.",
    "sources": [
      {
        "tag": "IBM_2020",
        "url": "https://ibm.gov.in/writereaddata/files/04272022163406Manganese_2020.pdf"
      },
      {
        "tag": "MPCB_KANDRI_EC",
        "url": "https://mpcb.ecmpcb.in/notices/pdf/kandri.pdf"
      }
    ],
    "type_note": "Company classification underground; EC summary suggests mixed opencast/underground component",
    "lat": 21.4125,
    "lon": 79.2667,
    "confidence": "high",
    "source": "MPCB EC Executive Summary (overrides Wikipedia — different village)",
    "source_url": null,
    "coordinate_precision": null,
    "coordinate_note": "Wikipedia's Kandri entry refers to a different village at 19.98N 80.43E"
  },
  {
    "mine_name": "Munsar",
    "state": "MH",
    "district": "Nagpur",
    "mine_type": "underground",
    "equipment": [
      "standard_underground_fleet"
    ],
    "capacity_target_tonnes": null,
    "notes": "No equipment disclosure found. Shaft deepening to 160 m in progress per the 2020 yearbook; a second vertical shaft is reported complete in AR 2023-24. R&D on subsidence monitoring and on overburden/bottom ash as stowing fill material.",
    "sources": [
      {
        "tag": "IBM_2020",
        "url": "https://ibm.gov.in/writereaddata/files/04272022163406Manganese_2020.pdf"
      },
      {
        "tag": "MOIL_AR_2023-24",
        "url": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2023-24.pdf"
      }
    ],
    "type_note": null,
    "lat": 21.3958,
    "lon": 79.2792,
    "confidence": "medium_high",
    "source": "MoEFCC PFR stated center of two lease blocks (environmentclearance.nic.in)",
    "source_url": null,
    "coordinate_precision": null,
    "coordinate_note": null
  },
  {
    "mine_name": "Beldongri",
    "state": "MH",
    "district": "Nagpur",
    "mine_type": "underground",
    "equipment": [
      "standard_underground_fleet"
    ],
    "capacity_target_tonnes": null,
    "notes": "Thinnest disclosure of the ten. No equipment, production or project detail was found in annual reports, IBM yearbooks or EC portal searches; the underground classification rests solely on company material cited on Wikipedia.",
    "sources": [
      {
        "tag": "WIKIPEDIA_MOIL",
        "url": "https://en.wikipedia.org/wiki/MOIL"
      }
    ],
    "type_note": null,
    "lat": 21.3495,
    "lon": 79.3003,
    "confidence": "low",
    "source": "USGS MRDS via TheDiggings.com (no MoEFCC/AR/Wikipedia coord)",
    "source_url": null,
    "coordinate_precision": "approximate — USGS third-party database",
    "coordinate_note": "Coordinate confidence is low (approximate — USGS third-party database). Treat as an approximate location, not a surveyed mine boundary."
  },
  {
    "mine_name": "Chikla",
    "state": "MH",
    "district": "Bhandara",
    "mine_type": "underground",
    "equipment": [
      "SDL",
      "electro_hydrostatic_drill",
      "shaft_sinking_rig"
    ],
    "capacity_target_tonnes": null,
    "notes": "Vertical shaft deepening to 169 m in progress per the 2020 yearbook; a second vertical shaft is reported complete in AR 2023-24 and an earlier deepening is also complete. EC of 150.65 ha granted in FY2023-24 - a lease/project area, not a tonnage.",
    "sources": [
      {
        "tag": "IBM_2020",
        "url": "https://ibm.gov.in/writereaddata/files/04272022163406Manganese_2020.pdf"
      },
      {
        "tag": "MOIL_AR_2023-24",
        "url": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2023-24.pdf"
      }
    ],
    "type_note": null,
    "lat": 21.5443,
    "lon": 79.7614,
    "confidence": "high",
    "source": "MPCB EC Executive Summary boundary centroid (mpcb.gov.in)",
    "source_url": null,
    "coordinate_precision": null,
    "coordinate_note": null
  },
  {
    "mine_name": "Dongri Buzurg",
    "state": "MH",
    "district": "Bhandara",
    "mine_type": "opencast",
    "equipment": [
      "standard_opencast_fleet"
    ],
    "capacity_target_tonnes": null,
    "notes": "Company's largest opencast mine; produces manganese dioxide ore for the dry-battery industry. Sources mention an excavator and dumper for the beneficiation plant but explicitly give no tonnage or model, so no capacity-bearing vocabulary term is asserted here.",
    "sources": [
      {
        "tag": "MOIL_PROFILE",
        "url": "https://moil.nic.in/userfiles/moilprofile.htm"
      },
      {
        "tag": "IEEE_DONGRI_BUZURG",
        "url": "https://ieeexplore.ieee.org/document/8635781"
      }
    ],
    "type_note": null,
    "lat": 21.55,
    "lon": 79.6941,
    "confidence": "low_medium",
    "source": "Wikipedia railway station proxy (no EC/PFR found)",
    "source_url": "https://en.wikipedia.org/wiki/Dongri_Buzurg_railway_station",
    "coordinate_precision": "approximate — 1-2 km from actual mine boundary",
    "coordinate_note": "Coordinate confidence is low_medium (approximate — 1-2 km from actual mine boundary). Treat as an approximate location, not a surveyed mine boundary."
  }
];
