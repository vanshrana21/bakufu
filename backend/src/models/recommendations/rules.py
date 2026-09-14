"""Corrective-action rule templates.

A Python module rather than JSON so the vocabulary constants can be imported
directly: every `equipment_referenced` entry is checked against the real MOIL
fleet lists at test time, which is what stops a rule quietly recommending an
LHD or a 100-tonne dumper. Public sources record neither at any MOIL mine.

Each rule fires from one SHAP driver and applies to one or both mine types.
`rationale_template` placeholders are filled from the shortfall response's
`display_value` fields, so a card quotes the same number the risk panel shows.

Nothing here is vague. "Monitor the situation" is not an action; every title
names something an operator can put on a shift plan.
"""

from __future__ import annotations

from typing import Any, Literal

ActionType = Literal["schedule_adjustment", "blasting_optimization", "equipment_redeployment"]
Priority = Literal["high", "medium", "low"]

#: Which raw features roll up into each driver. Verified against the shipped
#: shortfall_classifier_v1.pkl feature order.
DRIVER_FEATURES: dict[str, tuple[str, ...]] = {
    "rainfall_signal": ("rainfall_lag2_mm", "rainfall_lag1_mm", "rainfall_concurrent_mm"),
    "production_history_signal": ("deviation_lag1", "deviation_lag2", "production_trend_3mo"),
    "forecast_level_signal": ("prophet_forecast_level",),
    "seasonal_signal": ("month_sin", "month_cos"),
}

DRIVER_LABELS: dict[str, str] = {
    "rainfall_signal": "Rainfall and monsoon impact",
    "production_history_signal": "Recent production performance",
    "forecast_level_signal": "Forecast output level",
    "seasonal_signal": "Seasonal position",
}

ACTION_TYPES: tuple[ActionType, ...] = (
    "schedule_adjustment",
    "blasting_optimization",
    "equipment_redeployment",
)

PRIORITY_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}

#: Features whose raw value can read as *good news* while their SHAP pushes
#: risk *up*. A +27% three-month trend raising shortfall risk is genuine model
#: behaviour - mean reversion, where a run-up lifts the forecast the next month
#: must clear - but a card quoting it without explanation reads as a
#: non-sequitur. Each entry maps to the threshold above which the raw value
#: looks positive, plus the footnote that explains the mechanism.
#:
#: Everything else is intuitive: high rainfall, a high forecast level or a
#: seasonal term raising risk needs no explanation.
COUNTERINTUITIVE: dict[str, dict[str, object]] = {
    "production_trend_3mo": {
        "positive_above": 1.0,  # a ratio: >1.0 means output is trending up
        "footnote": (
            "Note: strong recent performance can raise short-term shortfall "
            "risk through mean reversion - the forecast rises with recent "
            "output, and next month must sustain the higher level."
        ),
    },
    "deviation_lag1": {
        "positive_above": 0.0,  # a fraction: >0 means last month beat forecast
        "footnote": (
            "Note: last month exceeding forecast raises next month's expected "
            "level. The shortfall model reflects that a higher bar is harder "
            "to clear."
        ),
    },
    "deviation_lag2": {
        "positive_above": 0.0,
        "footnote": (
            "Note: two months ago exceeding forecast pulled the trend upward. "
            "The shortfall model reflects continued upward pressure on "
            "expected output."
        ),
    },
}


def _rule(
    id: str,
    driver: str,
    action_type: ActionType,
    title: str,
    rationale_template: str,
    equipment_referenced: list[str],
    priority: Priority,
    applicable_mine_types: list[str],
) -> dict[str, Any]:
    return {
        "id": id,
        "driver": driver,
        "action_type": action_type,
        "title": title,
        "rationale_template": rationale_template,
        "equipment_referenced": equipment_referenced,
        "priority": priority,
        "applicable_mine_types": applicable_mine_types,
    }


RULES: list[dict[str, Any]] = [
    # --- rainfall_signal x underground ---------------------------------
    _rule(
        "ug_rain_stowing_capacity", "rainfall_signal", "equipment_redeployment",
        "Bring forward hydraulic sand stowing capacity",
        "{trigger_label} ({trigger_value}) is raising this month's "
        "shortfall risk. Stowing throughput limits how quickly worked-out faces "
        "return to production after wet-season inflow.",
        ["hydraulic_sand_stowing"], "high", ["underground"],
    ),
    _rule(
        "ug_rain_shift_sequence", "rainfall_signal", "schedule_adjustment",
        "Re-sequence development shifts away from wet-season faces",
        "{trigger_label} ({trigger_value}) is the leading risk "
        "driver. Move development effort to levels least exposed to inflow "
        "before the next cycle is planned.",
        ["rock_mechanics_monitoring"], "high", ["underground"],
    ),
    _rule(
        "ug_rain_blast_window", "rainfall_signal", "blasting_optimization",
        "Shorten the blast-to-mucking window while inflow is elevated",
        "With {trigger_label} ({trigger_value}) driving risk, a "
        "shorter interval between blasting and mucking limits how long broken "
        "ore sits in wet conditions.",
        ["electro_hydrostatic_drill", "SDL"], "medium", ["underground"],
    ),
    _rule(
        "ug_rain_sdl_allocation", "rainfall_signal", "equipment_redeployment",
        "Reallocate SDL units to drier levels",
        "Rainfall is the dominant risk driver this month. Concentrating side "
        "dump loaders on levels with lower inflow protects tramming rates.",
        ["SDL"], "medium", ["underground"],
    ),
    _rule(
        "ug_rain_strata_watch", "rainfall_signal", "schedule_adjustment",
        "Increase rock mechanics monitoring cadence after heavy rain",
        "Elevated {trigger_label} ({trigger_value}) raises the value of "
        "more frequent strata readings before committing shifts to affected "
        "sections.",
        ["rock_mechanics_monitoring"], "medium", ["underground"],
    ),
    _rule(
        "ug_rain_charge_protection", "rainfall_signal", "blasting_optimization",
        "Switch to moisture-resistant charging practice",
        "Wet conditions signalled by {trigger_label} ({trigger_value}) "
        "degrade charge performance; protected charging preserves fragmentation "
        "quality.",
        ["electro_hydrostatic_drill"], "medium", ["underground"],
    ),
    # --- rainfall_signal x opencast -------------------------------------
    _rule(
        "oc_rain_bench_drainage", "rainfall_signal", "schedule_adjustment",
        "Pull forward bench drainage and haul-road repair",
        "{trigger_label} ({trigger_value}) is the leading risk "
        "driver. Drainage and haul-road work scheduled now protects dig and "
        "haul rates through the coming month.",
        ["bench_management"], "high", ["opencast"],
    ),
    _rule(
        "oc_rain_dumper_rotation", "rainfall_signal", "equipment_redeployment",
        "Rotate 20-25 t dumpers onto hardened haul segments",
        "With rainfall raising shortfall risk, keeping the dumper fleet on "
        "hardened segments limits cycle-time loss and tyre damage on softened "
        "roads.",
        ["dumper_20_to_25t"], "high", ["opencast"],
    ),
    _rule(
        "oc_rain_blast_timing", "rainfall_signal", "blasting_optimization",
        "Move blasts to the driest window in the shift pattern",
        "{trigger_label} ({trigger_value}) is driving risk. Timing "
        "blasts to the driest available window reduces misfires and improves "
        "fragmentation.",
        ["drill_100mm"], "high", ["opencast"],
    ),
    _rule(
        "oc_rain_shovel_reposition", "rainfall_signal", "equipment_redeployment",
        "Reposition hydraulic shovels to higher benches",
        "Wet-season inflow signalled by {trigger_label} ({trigger_value}) makes lower "
        "benches the first to lose availability; working higher keeps the fleet "
        "productive.",
        ["hydraulic_shovel_0.9_to_1.7_m3"], "medium", ["opencast"],
    ),
    _rule(
        "oc_rain_hole_dewatering", "rainfall_signal", "blasting_optimization",
        "Dewater 100 mm blast holes before charging",
        "Rainfall is the dominant risk driver. Water in blast holes degrades "
        "explosive performance and is the most common cause of poor "
        "fragmentation in wet months.",
        ["drill_100mm"], "medium", ["opencast"],
    ),
    _rule(
        "oc_rain_sprinkler_standdown", "rainfall_signal", "schedule_adjustment",
        "Stand down water tankers during wet periods",
        "With {trigger_label} at {trigger_value}, dust suppression "
        "adds water to already-saturated haul roads. Standing the tankers down "
        "frees operators and avoids worsening road conditions.",
        ["water_tanker_sprinkler"], "low", ["opencast"],
    ),
    # --- production_history_signal x underground ------------------------
    _rule(
        "ug_hist_face_rebalance", "production_history_signal", "schedule_adjustment",
        "Rebalance shift allocation toward underperforming faces",
        "Production history is the leading risk driver, with {trigger_label} "
        "({trigger_value}) contributing most to the model's estimate. "
        "Rebalancing shifts targets the faces most exposed if it holds.",
        ["rock_mechanics_monitoring"], "high", ["underground"],
    ),
    _rule(
        "ug_hist_sdl_uplift", "production_history_signal", "equipment_redeployment",
        "Concentrate SDL capacity on the highest-grade faces",
        "With production history driving risk ({trigger_label} at {trigger_value}), "
        "prioritising loader capacity where grade is highest recovers tonnage "
        "fastest.",
        ["SDL", "rocker_shovel"], "high", ["underground"],
    ),
    _rule(
        "ug_hist_blast_cycle", "production_history_signal", "blasting_optimization",
        "Tighten the drill-and-blast cycle on lagging faces",
        "Production history is contributing via {trigger_label} ({trigger_value}). A tighter cycle on "
        "the lagging faces converts development metres into tonnage sooner.",
        ["electro_hydrostatic_drill"], "medium", ["underground"],
    ),
    _rule(
        "ug_hist_drill_pilot", "production_history_signal", "equipment_redeployment",
        "Extend the electro-hydrostatic drill pilot to a second face",
        "With {trigger_label} ({trigger_value}) among the risk drivers, "
        "widening the drill pilot tests whether the trial gains hold at scale.",
        ["electro_hydrostatic_drill"], "low", ["underground"],
    ),
    # --- production_history_signal x opencast ---------------------------
    _rule(
        "oc_hist_strip_ratio", "production_history_signal", "schedule_adjustment",
        "Re-plan the stripping schedule against the shortfall",
        "Production history leads the risk drivers, with {trigger_label} at "
        "{trigger_value}. Re-planning stripping restores exposed ore "
        "ahead of the next month.",
        ["bench_management"], "high", ["opencast"],
    ),
    _rule(
        "oc_hist_shovel_dumper_match", "production_history_signal", "equipment_redeployment",
        "Rematch shovel and dumper fleet sizing",
        "With production history driving risk ({trigger_label} at {trigger_value}), a shovel-dumper mismatch "
        "is the most common cause of lost cycles; rematching recovers "
        "throughput without new equipment.",
        ["hydraulic_shovel_0.9_to_1.7_m3", "dumper_20_to_25t"], "high", ["opencast"],
    ),
    _rule(
        "oc_hist_fragmentation", "production_history_signal", "blasting_optimization",
        "Review fragmentation against achieved dig rates",
        "Production history is contributing via {trigger_label} ({trigger_value}). Coarse "
        "fragmentation slows digging and is worth checking before adding "
        "fleet hours.",
        ["drill_100mm", "hydraulic_shovel_0.9_to_1.7_m3"], "medium", ["opencast"],
    ),
    _rule(
        "oc_hist_bench_height", "production_history_signal", "schedule_adjustment",
        "Revisit bench height on the lagging pit",
        "With {trigger_label} at {trigger_value} among the risk drivers, bench "
        "geometry rather than fleet capacity; a review is cheap relative to "
        "the tonnage at risk.",
        ["bench_management"], "low", ["opencast"],
    ),
    # --- forecast_level_signal x underground ----------------------------
    _rule(
        "ug_level_shaft_priority", "forecast_level_signal", "schedule_adjustment",
        "Prioritise shaft-sinking milestones against the target",
        "The forecast level itself ({prophet_forecast_level}) is driving risk: "
        "the target assumes capacity the current shaft programme has not yet "
        "delivered. Re-sequencing milestones protects the ramp.",
        ["shaft_sinking_rig"], "high", ["underground"],
    ),
    _rule(
        "ug_level_hoisting_window", "forecast_level_signal", "equipment_redeployment",
        "Extend hoisting windows to match the forecast level",
        "Meeting {prophet_forecast_level} requires hoisting capacity to keep "
        "pace with tramming; extending the window is the fastest lever "
        "available underground.",
        ["shaft_sinking_rig", "SDL"], "medium", ["underground"],
    ),
    _rule(
        "ug_level_round_length", "forecast_level_signal", "blasting_optimization",
        "Increase advance per round on main development",
        "The forecast level ({prophet_forecast_level}) is ambitious against "
        "current advance rates. Longer rounds raise metres per shift without "
        "adding crews.",
        ["electro_hydrostatic_drill"], "medium", ["underground"],
    ),
    _rule(
        "ug_level_stowing_balance", "forecast_level_signal", "equipment_redeployment",
        "Balance stowing capacity against planned extraction",
        "At {prophet_forecast_level}, stowing becomes the binding constraint "
        "before extraction does; balancing the two avoids a mid-month stall.",
        ["hydraulic_sand_stowing"], "low", ["underground"],
    ),
    # --- forecast_level_signal x opencast -------------------------------
    _rule(
        "oc_level_dumper_cycle", "forecast_level_signal", "schedule_adjustment",
        "Compress dumper cycle times to meet the forecast level",
        "The forecast level ({prophet_forecast_level}) is the leading risk "
        "driver. Cycle-time compression is the cheapest route to the extra "
        "tonnage before adding fleet.",
        ["dumper_20_to_25t"], "high", ["opencast"],
    ),
    _rule(
        "oc_level_shovel_hours", "forecast_level_signal", "equipment_redeployment",
        "Add hydraulic shovel hours on the primary bench",
        "Hitting {prophet_forecast_level} needs sustained dig availability; "
        "additional shovel hours on the primary bench are the most direct "
        "response.",
        ["hydraulic_shovel_0.9_to_1.7_m3"], "medium", ["opencast"],
    ),
    _rule(
        "oc_level_powder_factor", "forecast_level_signal", "blasting_optimization",
        "Review powder factor against the production target",
        "A target of {prophet_forecast_level} depends on consistent "
        "fragmentation; powder factor is the first parameter to check when dig "
        "rates limit output.",
        ["drill_100mm"], "medium", ["opencast"],
    ),
    _rule(
        "oc_level_bench_prep", "forecast_level_signal", "schedule_adjustment",
        "Advance bench preparation ahead of the target month",
        "Preparing benches early protects the {prophet_forecast_level} target "
        "against weather or equipment delays later in the month.",
        ["bench_management"], "low", ["opencast"],
    ),
    # --- seasonal_signal x underground ----------------------------------
    _rule(
        "ug_season_premonsoon_prep", "seasonal_signal", "schedule_adjustment",
        "Complete pre-monsoon stowing and pumping readiness",
        "The seasonal position is contributing to risk. Completing stowing and "
        "pumping readiness before the monsoon window is the highest-value "
        "preparatory action underground.",
        ["hydraulic_sand_stowing"], "high", ["underground"],
    ),
    _rule(
        "ug_season_blast_calendar", "seasonal_signal", "blasting_optimization",
        "Align the blast calendar to the seasonal pattern",
        "Seasonality is raising risk this month; concentrating blasting in the "
        "drier part of the calendar protects the cycle when inflow peaks.",
        ["electro_hydrostatic_drill"], "medium", ["underground"],
    ),
    _rule(
        "ug_season_equipment_stage", "seasonal_signal", "equipment_redeployment",
        "Stage SDL and rocker shovel spares before the monsoon window",
        "With the seasonal driver active, staging spares now avoids a "
        "wet-season outage becoming a multi-week availability loss.",
        ["SDL", "rocker_shovel"], "medium", ["underground"],
    ),
    # --- seasonal_signal x opencast -------------------------------------
    _rule(
        "oc_season_haul_hardening", "seasonal_signal", "schedule_adjustment",
        "Harden haul roads before the monsoon window",
        "The seasonal position is contributing to risk. Haul-road hardening "
        "ahead of the wet season is the single largest protection for opencast "
        "cycle times.",
        ["bench_management", "dumper_20_to_25t"], "high", ["opencast"],
    ),
    _rule(
        "oc_season_blast_frontload", "seasonal_signal", "blasting_optimization",
        "Front-load blasting ahead of the wet season",
        "Seasonality is raising shortfall risk; building a broken-ore buffer "
        "now sustains dig rates when blasting windows narrow.",
        ["drill_100mm"], "high", ["opencast"],
    ),
    _rule(
        "oc_season_fleet_shelter", "seasonal_signal", "equipment_redeployment",
        "Stage dumper and shovel maintenance for the low-production window",
        "With the seasonal driver active, moving planned maintenance into the "
        "weather-constrained window preserves fleet hours for productive "
        "months.",
        ["dumper_20_to_25t", "hydraulic_shovel_0.9_to_1.7_m3"], "medium", ["opencast"],
    ),
]


def rules_for(driver: str, mine_type: str) -> list[dict[str, Any]]:
    """Templates matching one driver and one mine type."""
    return [
        rule
        for rule in RULES
        if rule["driver"] == driver and mine_type in rule["applicable_mine_types"]
    ]
