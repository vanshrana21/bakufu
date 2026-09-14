"""
MOIL mine reference data for the Phase 4 recommendation rules engine.

Extracted from docs/moil_reference/equipment_deployment.md, which compiles
what MOIL and the Indian Bureau of Mines disclose publicly. Nothing here is
inferred beyond what that document states, with two exceptions marked in
`district` and in the per-mine notes.

The equipment vocabularies are deliberately narrow. Public sources record no
LHD, no jumbo drill and no 100-tonne class dumper at any MOIL mine: the
underground fleet runs SDL / rocker shovel / electro-hydrostatic drill, and
the disclosed opencast dumper fleet is 20-25 t. A rules engine drawing on
generic large-scale metal-mine terminology would recommend equipment MOIL
does not operate, so recommendation text should draw its nouns from these
lists rather than from industry defaults.

Reference data only - this module is not wired into any rules engine, API
route or dashboard component. That integration is Phase 4 work.
"""

from __future__ import annotations

SOURCE_URLS: dict[str, str] = {
    "IBM_2020": "https://ibm.gov.in/writereaddata/files/04272022163406Manganese_2020.pdf",
    "IBM_2022": "https://ibm.gov.in/writereaddata/files/17125770456613da1576db0Manganese_Ore_2022.pdf",
    "MOIL_AR_2023-24": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2023-24.pdf",
    "MOIL_AR_2022-23": "https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2022-23.pdf",
    "MOIL_PROFILE": "https://moil.nic.in/userfiles/moilprofile.htm",
    "MPCB_KANDRI_EC": "https://mpcb.ecmpcb.in/notices/pdf/kandri.pdf",
    "IEEE_DONGRI_BUZURG": "https://ieeexplore.ieee.org/document/8635781",
    "WIKIPEDIA_MOIL": "https://en.wikipedia.org/wiki/MOIL",
}

#: Equipment nouns actually attested at MOIL underground mines.
UNDERGROUND_FLEET_VOCAB: list[str] = [
    "SDL",
    "rocker_shovel",
    "electro_hydrostatic_drill",
    "hydraulic_sand_stowing",
    "shaft_sinking_rig",
    "rock_mechanics_monitoring",
]

#: Equipment nouns actually attested at MOIL opencast mines.
OPENCAST_FLEET_VOCAB: list[str] = [
    "hydraulic_shovel_0.9_to_1.7_m3",
    "drill_100mm",
    "dumper_20_to_25t",
    "water_tanker_sprinkler",
    "bench_management",
]

#: Placeholders for the four mines with no equipment disclosure at all, so the
#: rules engine can fall back to generic vocabulary without special-casing.
GENERIC_FLEETS: tuple[str, str] = (
    "standard_underground_fleet",
    "standard_opencast_fleet",
)

#: Per the Wikipedia mine-by-mine classification drawn from company materials.
#: MOIL's AR 2022-23 instead says "four opencast and seven underground" (11
#: mines); the 10-mine split below matches the operating list in scope here.
MINE_TYPE_COUNTS: dict[str, int] = {"underground": 7, "opencast": 3}

# Not all mines have all fields. Sparse fields:
#   - type_note: Kandri only
# Access with .get(field, default) to avoid KeyError.
MOIL_MINES: dict[str, dict[str, object]] = {
    "Balaghat": {
        "state": "MP",
        # All four MP mines sit in Balaghat district, confirmed against the
        # International Manganese Institute, MOIL's About page, the IBM 2022
        # yearbook and a MOIL CMD interview.
        "district": "Balaghat",
        "mine_type": "underground",
        "equipment": ["SDL", "rocker_shovel", "shaft_sinking_rig"],
        "capacity_target_tonnes": 800000,
        "notes": (
            "Company's largest mine; described as the deepest underground "
            "manganese mine in Asia. Large-diameter high-speed vertical shaft "
            "under sinking (750 m planned, revised to 660 m); an earlier shaft "
            "deepening is already complete. SDL bucket capacity 0.66 cu.m."
        ),
        "sources": ["IBM_2022", "MOIL_AR_2023-24", "MOIL_AR_2022-23"],
    },
    "Ukwa": {
        "state": "MP",
        # All four MP mines sit in Balaghat district, confirmed against the
        # International Manganese Institute, MOIL's About page, the IBM 2022
        # yearbook and a MOIL CMD interview.
        "district": "Balaghat",
        "mine_type": "underground",
        # Rock mechanics monitoring is the one item any source names here.
        # Recording it alone - rather than a generic fallback - asserts
        # exactly what is known and nothing more; the rules engine still
        # falls back to UNDERGROUND_FLEET_VOCAB for generic recommendations.
        "equipment": ["rock_mechanics_monitoring"],
        "capacity_target_tonnes": None,
        "notes": (
            "No production fleet disclosure; the only equipment named in any "
            "source is rock mechanics monitoring instrumentation. Vertical "
            "shaft sinking to 324 m in progress as of the 2020 yearbook; a "
            "second vertical shaft is reported complete in AR 2023-24."
        ),
        "sources": ["IBM_2020", "MOIL_AR_2023-24"],
    },
    "Sitapatore": {
        "state": "MP",
        # All four MP mines sit in Balaghat district, confirmed against the
        # International Manganese Institute, MOIL's About page, the IBM 2022
        # yearbook and a MOIL CMD interview.
        "district": "Balaghat",
        "mine_type": "opencast",
        "equipment": ["standard_opencast_fleet"],
        "capacity_target_tonnes": None,
        "notes": (
            "No equipment disclosure found. Opencast classification comes from "
            "company material cited on Wikipedia and is not corroborated by a "
            "primary MOIL document. EC of 4.734 ha granted in FY2023-24."
        ),
        "sources": ["MOIL_AR_2023-24", "WIKIPEDIA_MOIL"],
    },
    "Tirodi": {
        "state": "MP",
        # All four MP mines sit in Balaghat district, confirmed against the
        # International Manganese Institute, MOIL's About page, the IBM 2022
        # yearbook and a MOIL CMD interview.
        "district": "Balaghat",
        "mine_type": "opencast",
        "equipment": [
            "drill_100mm",
            "hydraulic_shovel_0.9_to_1.7_m3",
            "dumper_20_to_25t",
            "bench_management",
        ],
        "capacity_target_tonnes": None,
        "notes": (
            "Dumper-shovel opencast operation and the most completely "
            "specified fleet in public sources. Overburden benches kept at "
            "7.5 m, ore benches at 6 m. EC of 4.419 ha granted in FY2023-24."
        ),
        "sources": ["IBM_2022", "MOIL_AR_2023-24"],
    },
    "Gumgaon": {
        "state": "MH",
        # district inferred from general geography, not source-cited
        "district": "Nagpur",
        "mine_type": "underground",
        "equipment": ["SDL", "electro_hydrostatic_drill", "shaft_sinking_rig"],
        "capacity_target_tonnes": 350000,
        "notes": (
            "Large-diameter high-speed vertical shaft sinking to 330 m in "
            "progress, INR 194 crore capital cost per the annual report. The "
            "electro-hydrostatic drill is an experimental introduction shared "
            "with Chikla."
        ),
        "sources": ["IBM_2020", "MOIL_AR_2023-24", "MOIL_AR_2022-23"],
    },
    "Kandri": {
        "state": "MH",
        # district inferred from general geography, not source-cited
        "district": "Nagpur",
        "mine_type": "underground",
        "type_note": (
            "Company classification underground; EC summary suggests mixed "
            "opencast/underground component"
        ),
        "equipment": [
            "dumper_20_to_25t",
            "water_tanker_sprinkler",
            "hydraulic_sand_stowing",
            "shaft_sinking_rig",
        ],
        "capacity_target_tonnes": 100000,
        "notes": (
            "Expansion proposal 0.063 MTPA to 0.100 MTPA. The EC executive "
            "summary describes the method as opencast/underground (ripping/"
            "dozing, drilling, manual sorting and sizing, mechanised loading "
            "and transport) and cites roughly 5-6 dumpers of 20 t for the "
            "added transport load. Hydraulic sand stowing replaced manual "
            "filling; shaft deepening to 245 m."
        ),
        "sources": ["IBM_2020", "MPCB_KANDRI_EC"],
    },
    "Munsar": {
        "state": "MH",
        # district inferred from general geography, not source-cited
        "district": "Nagpur",
        "mine_type": "underground",
        "equipment": ["standard_underground_fleet"],
        "capacity_target_tonnes": None,
        "notes": (
            "No equipment disclosure found. Shaft deepening to 160 m in "
            "progress per the 2020 yearbook; a second vertical shaft is "
            "reported complete in AR 2023-24. R&D on subsidence monitoring "
            "and on overburden/bottom ash as stowing fill material."
        ),
        "sources": ["IBM_2020", "MOIL_AR_2023-24"],
    },
    "Beldongri": {
        "state": "MH",
        # district inferred from general geography, not source-cited
        "district": "Nagpur",
        "mine_type": "underground",
        "equipment": ["standard_underground_fleet"],
        "capacity_target_tonnes": None,
        "notes": (
            "Thinnest disclosure of the ten. No equipment, production or "
            "project detail was found in annual reports, IBM yearbooks or EC "
            "portal searches; the underground classification rests solely on "
            "company material cited on Wikipedia."
        ),
        "sources": ["WIKIPEDIA_MOIL"],
    },
    "Chikla": {
        "state": "MH",
        # district inferred from general geography, not source-cited
        "district": "Bhandara",
        "mine_type": "underground",
        "equipment": ["SDL", "electro_hydrostatic_drill", "shaft_sinking_rig"],
        "capacity_target_tonnes": None,
        "notes": (
            "Vertical shaft deepening to 169 m in progress per the 2020 "
            "yearbook; a second vertical shaft is reported complete in AR "
            "2023-24 and an earlier deepening is also complete. EC of 150.65 "
            "ha granted in FY2023-24 - a lease/project area, not a tonnage."
        ),
        "sources": ["IBM_2020", "MOIL_AR_2023-24"],
    },
    "Dongri Buzurg": {
        "state": "MH",
        # district inferred from general geography, not source-cited
        "district": "Bhandara",
        "mine_type": "opencast",
        "equipment": ["standard_opencast_fleet"],
        "capacity_target_tonnes": None,
        "notes": (
            "Company's largest opencast mine; produces manganese dioxide ore "
            "for the dry-battery industry. Sources mention an excavator and "
            "dumper for the beneficiation plant but explicitly give no "
            "tonnage or model, so no capacity-bearing vocabulary term is "
            "asserted here."
        ),
        "sources": ["MOIL_PROFILE", "IEEE_DONGRI_BUZURG"],
    },
}
