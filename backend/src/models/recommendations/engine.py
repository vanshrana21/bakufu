"""Turn a shortfall SHAP explanation into corrective-action cards.

The engine consumes the `/shortfall/risk` response *shape* and nothing else.
It never imports the classifier, so rule logic is testable against a hand-built
response, and the endpoint can reuse an already-cached explanation rather than
paying the SHAP cost twice.

Ranking principle: only features with **positive** SHAP - those arguing *for* a
shortfall - generate corrective actions. Features with negative SHAP explain why
the forecast is currently healthy and do not warrant intervention. Ranking by
|SHAP| instead would, on the current live prediction, fire actions against
`production_history_signal`, whose contributions are all negative because last
month beat forecast by 7.4%. That would tell an operator to fix what is going
well.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.models.recommendations.rules import (
    ACTION_TYPES,
    COUNTERINTUITIVE,
    DRIVER_FEATURES,
    DRIVER_LABELS,
    PRIORITY_RANK,
    RULES,
    rules_for,
)

#: Risk bands. Below LOW nothing fires; at or above HIGH the response is
#: guaranteed to carry all three action types (subject to `limit`).
LOW_RISK_CEILING = 0.25
HIGH_RISK_FLOOR = 0.60

NO_ACTION_MESSAGE = "No corrective action needed at current risk level."

#: Used when no mine is named. Seven of ten MOIL mines are underground, so it
#: is the honest default for an aggregate view.
DEFAULT_MINE_TYPE = "underground"


def driver_scores(contributions: list[dict[str, Any]]) -> dict[str, float]:
    """Positive SHAP summed per driver. Negative contributions are ignored."""
    scores = {driver: 0.0 for driver in DRIVER_FEATURES}
    feature_to_driver = {
        feature: driver
        for driver, features in DRIVER_FEATURES.items()
        for feature in features
    }
    for entry in contributions:
        value = float(entry.get("shap_contribution", 0.0))
        driver = feature_to_driver.get(entry.get("feature_name", ""))
        if driver is not None and value > 0:
            scores[driver] += value
    return scores


def is_counterintuitive_contribution(feature: dict[str, Any]) -> bool:
    """True when a feature raises risk while its raw value reads as good news.

    Only three features can do this: a rising production trend, or either
    deviation term showing last month beating forecast. Each raises the level
    the coming month has to clear. Rainfall, forecast level and the seasonal
    terms raising risk are all intuitive and need no gloss.
    """
    name = feature.get("feature_name", "")
    rule = COUNTERINTUITIVE.get(name)
    if rule is None:
        return False
    if float(feature.get("shap_contribution", 0.0)) <= 0:
        return False
    try:
        value = float(feature.get("value"))
    except (TypeError, ValueError):
        return False
    return value > float(rule["positive_above"])


def footnotes_for(contributions: list[dict[str, Any]]) -> list[str]:
    """Explanations for any counterintuitive contribution, deduplicated.

    Empty when nothing needs explaining, so the frontend renders nothing.
    """
    notes: list[str] = []
    for entry in contributions:
        if is_counterintuitive_contribution(entry):
            note = str(COUNTERINTUITIVE[entry["feature_name"]]["footnote"])
            if note not in notes:
                notes.append(note)
    return notes


def _strongest_feature(driver: str, contributions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The largest positive contributor within one driver."""
    members = [
        entry
        for entry in contributions
        if entry.get("feature_name") in DRIVER_FEATURES[driver]
        and float(entry.get("shap_contribution", 0.0)) > 0
    ]
    if not members:
        return None
    return max(members, key=lambda entry: float(entry["shap_contribution"]))


def _render(
    rule: dict[str, Any],
    contributions: list[dict[str, Any]],
    trigger: dict[str, Any] | None,
) -> str:
    """Fill the rationale template from the response's display values.

    `{trigger_label}` and `{trigger_value}` name the feature that actually
    fired the driver. Templates use those for the evidence clause rather than
    hardcoding a group member: a driver can be triggered by any of its
    features, and quoting a different one produced sentences like "last month
    came in at +19.7% against forecast" as the reason to act on a shortfall -
    a positive number offered as evidence of a problem.
    """
    values = {
        entry["feature_name"]: entry.get("display_value", entry.get("value"))
        for entry in contributions
    }
    for name in DRIVER_FEATURES[rule["driver"]]:
        values.setdefault(name, name.replace("_", " "))
    values["trigger_label"] = (
        (trigger.get("human_label") or trigger["feature_name"]).lower()
        if trigger
        else "the leading signal"
    )
    values["trigger_value"] = trigger.get("display_value", "") if trigger else ""
    try:
        return rule["rationale_template"].format(**values)
    except KeyError:
        return rule["rationale_template"]


def _card(
    rule: dict[str, Any], driver: str, contributions: list[dict[str, Any]]
) -> dict[str, Any]:
    trigger = _strongest_feature(driver, contributions)
    return {
        "id": rule["id"],
        "action_type": rule["action_type"],
        "title": rule["title"],
        "rationale": _render(rule, contributions, trigger),
        "equipment_referenced": list(rule["equipment_referenced"]),
        "priority": rule["priority"],
        "driver": driver,
        "driver_label": DRIVER_LABELS[driver],
        "triggered_by": (
            [
                {
                    "signal": trigger["feature_name"],
                    "value": trigger.get("value"),
                    "display_value": trigger.get("display_value"),
                    "shap_contribution": float(trigger["shap_contribution"]),
                }
            ]
            if trigger
            else []
        ),
        "confidence": "rule_based",
    }


def _sort_key(card: dict[str, Any]) -> tuple[int, float]:
    contribution = (
        card["triggered_by"][0]["shap_contribution"] if card["triggered_by"] else 0.0
    )
    return (PRIORITY_RANK[card["priority"]], -contribution)


def _enforce_action_type_coverage(
    selected: list[dict[str, Any]],
    pool: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Guarantee one card per action type at high risk, within `limit`.

    `limit` wins over the guarantee - an explicit caller request is not
    overridden - but the truncated set preserves action-type *diversity*
    rather than taking top-N by priority alone, so `limit=2` returns two
    different action types instead of the two highest-priority cards which
    might share one.
    """
    by_type: dict[str, list[dict[str, Any]]] = {action: [] for action in ACTION_TYPES}
    for card in sorted(pool, key=_sort_key):
        by_type[card["action_type"]].append(card)

    ordered_types = sorted(
        (action for action in ACTION_TYPES if by_type[action]),
        key=lambda action: _sort_key(by_type[action][0]),
    )

    diverse: list[dict[str, Any]] = []
    for action in ordered_types:
        if len(diverse) >= limit:
            break
        diverse.append(by_type[action][0])

    # Fill any remaining slots with the best cards not already chosen.
    chosen = {card["id"] for card in diverse}
    for card in sorted(pool, key=_sort_key):
        if len(diverse) >= limit:
            break
        if card["id"] not in chosen:
            diverse.append(card)
            chosen.add(card["id"])

    return sorted(diverse, key=_sort_key)


def generate_recommendations(
    shortfall_response: dict[str, Any],
    mine_name: str | None = None,
    mine_type: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Corrective-action cards for one shortfall explanation.

    `mine_type` resolves the fleet vocabulary. It is passed in rather than
    looked up so the engine keeps no dependency on the mine reference data.
    """
    probability = float(shortfall_response.get("shortfall_probability", 0.0))
    contributions = list(shortfall_response.get("feature_contributions", []))
    resolved_type = mine_type or DEFAULT_MINE_TYPE

    scores = driver_scores(contributions)
    ranked = [
        (driver, score) for driver, score in sorted(scores.items(), key=lambda kv: -kv[1])
        if score > 0
    ]

    context = {
        "mine_name": mine_name,
        "mine_type": resolved_type,
        "shortfall_probability": probability,
        "forecast_month": shortfall_response.get("forecast_month"),
        "risk_level": shortfall_response.get("risk_level"),
        "drivers_ranked": [
            {"driver": driver, "label": DRIVER_LABELS[driver], "positive_shap": round(score, 4)}
            for driver, score in ranked
        ],
        "footnotes": footnotes_for(contributions),
    }

    # Low risk, or nothing arguing for a shortfall at all.
    if probability < LOW_RISK_CEILING or not ranked:
        # A footnote exists to explain a card that reads oddly. With no cards
        # it is an orphaned note under "no action needed", so it is suppressed.
        return {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "context": {**context, "footnotes": [], "message": NO_ACTION_MESSAGE},
            "recommendations": [],
            "coverage_complete": False,
            "action_types_included": [],
            "action_types_omitted": list(ACTION_TYPES),
        }

    high_risk = probability >= HIGH_RISK_FLOOR
    # Medium risk stays with the primary driver; high risk widens to two.
    drivers = [driver for driver, _ in ranked[: (2 if high_risk else 1)]]

    pool: list[dict[str, Any]] = []
    for driver in drivers:
        for rule in rules_for(driver, resolved_type):
            pool.append(_card(rule, driver, contributions))

    if not pool:
        return {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "context": {**context, "footnotes": [], "message": "No rules apply to this mine type."},
            "recommendations": [],
            "coverage_complete": False,
            "action_types_included": [],
            "action_types_omitted": list(ACTION_TYPES),
        }

    if high_risk:
        selected = _enforce_action_type_coverage([], pool, limit)
    else:
        # Medium risk: top 1-2 from the primary driver, no coverage guarantee.
        selected = sorted(pool, key=_sort_key)[: min(limit, 2)]

    included = sorted({card["action_type"] for card in selected})
    omitted = [action for action in ACTION_TYPES if action not in included]

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "context": context,
        "recommendations": selected,
        "coverage_complete": high_risk and not omitted,
        "action_types_included": included,
        "action_types_omitted": omitted,
    }


def catalog_size() -> int:
    return len(RULES)
