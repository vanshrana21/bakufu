"""Tests for the corrective-actions rules engine.

The engine consumes the `/shortfall/risk` response shape, so most of these
build a synthetic response rather than running the classifier. That keeps rule
logic testable independently of SHAP, and lets a test pin a risk band the live
model does not currently produce.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.recommendations.engine import (
    ACTION_TYPES,
    HIGH_RISK_FLOOR,
    LOW_RISK_CEILING,
    generate_recommendations,
)
from src.models.recommendations.rules import DRIVER_FEATURES, RULES
from src.reference.moil_mines import OPENCAST_FLEET_VOCAB, UNDERGROUND_FLEET_VOCAB


@pytest.fixture(scope="module")
def client(api_headers: dict[str, str]) -> TestClient:
    with TestClient(app, headers=api_headers) as test_client:
        yield test_client


def _contribution(
    name: str, shap: float, display: str = "1.0 mm", value: float = 1.0
) -> dict:
    """One SHAP row. `value` matters: the counterintuitive check reads it.

    Defaulting every feature to 1.0 once made `deviation_lag1` look like
    "+100% above forecast" while its display said -8.0%, which fired a
    mean-reversion footnote in a test that was asserting none.
    """
    return {
        "feature_name": name,
        "human_label": name.replace("_", " "),
        "value": value,
        "display_value": display,
        "shap_contribution": shap,
        "direction": "increases_risk" if shap > 0 else "decreases_risk",
    }


def _response(probability: float, contributions: list[dict]) -> dict:
    return {
        "as_of": "2026-05",
        "forecast_month": "2026-06",
        "shortfall_probability": probability,
        "risk_level": "high" if probability >= 0.5 else "low",
        "prophet_forecast_tonnes": 200000.0,
        "feature_contributions": contributions,
    }


RAINFALL_LED = [
    _contribution("rainfall_lag2_mm", 1.4, "180.0 mm"),
    _contribution("rainfall_lag1_mm", 0.6, "120.0 mm"),
    _contribution("deviation_lag1", 0.3, "-8.0%", value=-0.08),
    _contribution("prophet_forecast_level", -0.9, "200,000 t"),
]


# --- risk bands ---------------------------------------------------------


def test_high_risk_returns_all_three_action_types() -> None:
    """The PS-coverage guarantee: schedule, blasting and equipment."""
    result = generate_recommendations(_response(0.75, RAINFALL_LED), limit=5)
    returned = {card["action_type"] for card in result["recommendations"]}
    assert returned == set(ACTION_TYPES)
    assert result["coverage_complete"] is True
    assert result["action_types_omitted"] == []


def test_low_risk_returns_empty_with_message() -> None:
    result = generate_recommendations(_response(0.10, RAINFALL_LED), limit=5)
    assert result["recommendations"] == []
    assert "No corrective action needed" in result["context"]["message"]
    assert result["coverage_complete"] is False


def test_medium_risk_scoped_to_primary_driver() -> None:
    result = generate_recommendations(_response(0.40, RAINFALL_LED), limit=5)
    assert 1 <= len(result["recommendations"]) <= 2
    drivers = {card["driver"] for card in result["recommendations"]}
    assert drivers == {"rainfall_signal"}, "medium risk stays on the top driver"


def test_risk_band_boundaries_are_the_documented_ones() -> None:
    assert LOW_RISK_CEILING == 0.25
    assert HIGH_RISK_FLOOR == 0.60
    assert generate_recommendations(_response(0.24, RAINFALL_LED))["recommendations"] == []
    assert generate_recommendations(_response(0.26, RAINFALL_LED))["recommendations"]


# --- ranking principle --------------------------------------------------


def test_only_positive_shap_drives_recommendations() -> None:
    """Features arguing against a shortfall must not generate actions.

    Ranking by |SHAP| would pick production_history here, whose contribution is
    large but negative - i.e. the reason to expect no shortfall.
    """
    contributions = [
        _contribution("deviation_lag1", -2.5, "+9.0%", value=0.09),
        _contribution("production_trend_3mo", -1.2, "+14.0%", value=1.14),
        _contribution("rainfall_lag2_mm", 0.8, "150.0 mm"),
    ]
    result = generate_recommendations(_response(0.70, contributions), limit=5)
    assert result["context"]["drivers_ranked"][0]["driver"] == "rainfall_signal"
    assert all(card["driver"] == "rainfall_signal" for card in result["recommendations"])


def test_no_positive_shap_yields_no_recommendations() -> None:
    """Nothing arguing for a shortfall means nothing to correct."""
    contributions = [_contribution("deviation_lag1", -2.0), _contribution("month_sin", -0.4)]
    result = generate_recommendations(_response(0.90, contributions), limit=5)
    assert result["recommendations"] == []


def test_rainfall_driver_produces_rainfall_rationale() -> None:
    result = generate_recommendations(_response(0.80, RAINFALL_LED), limit=5)
    top = result["recommendations"][0]
    assert top["driver"] == "rainfall_signal"
    assert "rainfall" in top["rationale"].lower()
    assert top["triggered_by"][0]["signal"] == "rainfall_lag2_mm"


def test_rationale_cites_the_triggering_feature() -> None:
    """A template must not quote a feature that did not fire the driver.

    Hardcoded placeholders produced "last month came in at +19.7% against
    forecast" as the reason to act on a shortfall - a positive number offered
    as evidence of a problem.
    """
    contributions = [
        _contribution("production_trend_3mo", 1.5, "+27.1% vs prior quarter", value=1.271),
        _contribution("deviation_lag1", 0.1, "+19.7%", value=0.197),
    ]
    result = generate_recommendations(_response(0.80, contributions), limit=5)
    for card in result["recommendations"]:
        assert card["triggered_by"][0]["signal"] == "production_trend_3mo"
        assert "+19.7%" not in card["rationale"], "must not quote the non-trigger"


# --- mine-type vocabulary ----------------------------------------------


def test_underground_mine_uses_underground_vocabulary() -> None:
    result = generate_recommendations(
        _response(0.80, RAINFALL_LED), mine_name="Balaghat", mine_type="underground", limit=5
    )
    assert result["recommendations"]
    for card in result["recommendations"]:
        for item in card["equipment_referenced"]:
            assert item in UNDERGROUND_FLEET_VOCAB, item


def test_opencast_mine_uses_opencast_vocabulary() -> None:
    result = generate_recommendations(
        _response(0.80, RAINFALL_LED),
        mine_name="Dongri Buzurg",
        mine_type="opencast",
        limit=5,
    )
    assert result["recommendations"]
    for card in result["recommendations"]:
        for item in card["equipment_referenced"]:
            assert item in OPENCAST_FLEET_VOCAB, item


def test_generic_fleet_mine_falls_back_gracefully() -> None:
    """Sitapatore's equipment is a placeholder; it still gets opencast rules."""
    result = generate_recommendations(
        _response(0.80, RAINFALL_LED), mine_name="Sitapatore", mine_type="opencast", limit=5
    )
    assert result["recommendations"]
    for card in result["recommendations"]:
        for item in card["equipment_referenced"]:
            assert item in OPENCAST_FLEET_VOCAB
            assert not item.startswith("standard_"), "placeholder must never reach a card"


def test_rules_reference_only_moil_equipment() -> None:
    """Guards against a rule naming an LHD or a 100-tonne dumper.

    Public sources record neither at any MOIL mine.
    """
    allowed = set(UNDERGROUND_FLEET_VOCAB) | set(OPENCAST_FLEET_VOCAB)
    for rule in RULES:
        assert rule["equipment_referenced"], f"{rule['id']} names no equipment"
        for item in rule["equipment_referenced"]:
            assert item in allowed, f"{rule['id']} references unknown equipment {item!r}"


def test_rule_catalog_covers_every_driver_and_mine_type() -> None:
    """Each driver x mine type carries all three action types."""
    for driver in DRIVER_FEATURES:
        for mine_type in ("underground", "opencast"):
            actions = {
                rule["action_type"]
                for rule in RULES
                if rule["driver"] == driver and mine_type in rule["applicable_mine_types"]
            }
            assert actions == set(ACTION_TYPES), f"{driver} x {mine_type}: {actions}"


# --- limit --------------------------------------------------------------


def test_limit_param_is_respected() -> None:
    result = generate_recommendations(_response(0.80, RAINFALL_LED), limit=2)
    assert len(result["recommendations"]) <= 2


def test_limit_below_three_preserves_action_type_diversity() -> None:
    """limit wins over the coverage guarantee, but the set stays diverse."""
    result = generate_recommendations(_response(0.80, RAINFALL_LED), limit=2)
    actions = [card["action_type"] for card in result["recommendations"]]
    assert len(actions) == 2
    assert len(set(actions)) == 2, "two cards must be two different action types"
    assert result["coverage_complete"] is False
    assert len(result["action_types_omitted"]) == 1


# --- endpoints ----------------------------------------------------------


def test_endpoint_no_longer_returns_501(client: TestClient) -> None:
    response = client.get("/recommendations")
    assert response.status_code == 200


def test_endpoint_matches_contract(client: TestClient) -> None:
    body = client.get("/recommendations").json()
    assert set(body) == {
        "generated_at", "context", "recommendations",
        "coverage_complete", "action_types_included", "action_types_omitted",
    }
    assert {"mine_name", "mine_type", "shortfall_probability", "drivers_ranked"} <= set(
        body["context"]
    )


@pytest.mark.parametrize("query", ["?mine_name=Foo", "?limit=0", "?limit=50"])
def test_endpoint_validates_params(client: TestClient, query: str) -> None:
    assert client.get(f"/recommendations{query}").status_code == 422


def test_scenario_endpoint_replays_a_real_month(client: TestClient) -> None:
    """Real model output on real history, not a fabricated scenario."""
    from src.config.settings import settings

    month = settings.SCENARIO_MONTHS[0]
    body = client.get(f"/recommendations/scenario/{month}").json()
    assert body["context"]["scenario_month"] == month
    assert body["context"]["is_historical_replay"] is True
    assert body["context"]["actual_shortfall"] is True, "picked months are real shortfalls"
    assert body["context"]["shortfall_probability"] >= HIGH_RISK_FLOOR
    assert {card["action_type"] for card in body["recommendations"]} == set(ACTION_TYPES)


def test_scenario_endpoint_rejects_unlisted_months(client: TestClient) -> None:
    response = client.get("/recommendations/scenario/2019-07")
    assert response.status_code == 404
    assert "2019-07" in response.json()["detail"]


def test_scenario_months_produce_different_drivers(client: TestClient) -> None:
    """The two picks demonstrate the taxonomy switching, not one canned answer."""
    from src.config.settings import settings

    tops = []
    for month in settings.SCENARIO_MONTHS:
        body = client.get(f"/recommendations/scenario/{month}").json()
        tops.append(body["context"]["drivers_ranked"][0]["driver"])
    assert len(set(tops)) > 1, f"both scenarios led with the same driver: {tops}"


def test_current_month_is_low_urgency(client: TestClient) -> None:
    """The live state scores low risk; the engine must not invent urgency."""
    body = client.get("/recommendations").json()
    if body["context"]["shortfall_probability"] < LOW_RISK_CEILING:
        assert body["recommendations"] == []
        assert "No corrective action needed" in body["context"]["message"]


# --- counterintuitive footnotes ----------------------------------------

from src.models.recommendations.engine import (  # noqa: E402
    footnotes_for,
    is_counterintuitive_contribution,
)


@pytest.mark.parametrize(
    ("name", "value", "shap", "expected"),
    [
        # The three features where good-looking values can raise risk.
        ("production_trend_3mo", 1.27, 1.5, True),
        ("production_trend_3mo", 0.85, 1.5, False),   # trend is down: intuitive
        ("production_trend_3mo", 1.27, -1.5, False),  # lowers risk: nothing to explain
        ("deviation_lag1", 0.074, 0.5, True),
        ("deviation_lag1", -0.08, 0.5, False),        # missed forecast: intuitive
        ("deviation_lag1", 0.074, -0.5, False),
        ("deviation_lag2", 0.01, 0.2, True),
        ("deviation_lag2", -0.02, 0.2, False),
        # Everything else is intuitive in both directions.
        ("rainfall_lag2_mm", 180.0, 1.5, False),
        ("rainfall_lag1_mm", 120.0, 0.6, False),
        ("rainfall_concurrent_mm", 100.0, 0.3, False),
        ("prophet_forecast_level", 201284.0, 2.2, False),
        ("month_sin", 0.5, 0.3, False),
        ("month_cos", -1.0, 0.1, False),
    ],
)
def test_counterintuitive_detection(name: str, value: float, shap: float, expected: bool) -> None:
    feature = {"feature_name": name, "value": value, "shap_contribution": shap}
    assert is_counterintuitive_contribution(feature) is expected


def test_footnotes_are_deduplicated() -> None:
    contributions = [
        {"feature_name": "production_trend_3mo", "value": 1.3, "shap_contribution": 1.0},
        {"feature_name": "production_trend_3mo", "value": 1.3, "shap_contribution": 1.0},
        {"feature_name": "deviation_lag1", "value": 0.05, "shap_contribution": 0.4},
    ]
    notes = footnotes_for(contributions)
    assert len(notes) == 2
    assert any("mean reversion" in note for note in notes)


def test_mean_reversion_footnote_fires_on_a_rising_trend() -> None:
    contributions = [
        _contribution("production_trend_3mo", 1.5, "+27.1% vs prior quarter", value=1.271),
        _contribution("rainfall_lag2_mm", 0.4, "150.0 mm", value=150.0),
    ]
    result = generate_recommendations(_response(0.80, contributions), limit=5)
    notes = result["context"]["footnotes"]
    assert notes and "mean reversion" in notes[0]


def test_no_footnote_when_nothing_is_counterintuitive() -> None:
    """Rainfall raising risk needs no explanation."""
    result = generate_recommendations(_response(0.80, RAINFALL_LED), limit=5)
    assert result["context"]["footnotes"] == []


def test_footnotes_field_is_always_present(client: TestClient) -> None:
    """Always an array, so the frontend can render conditionally."""
    body = client.get("/recommendations").json()
    assert isinstance(body["context"]["footnotes"], list)


def test_forecast_level_scenario_fires_no_footnote(client: TestClient) -> None:
    """2024-02 is led by prophet_forecast_level, which is not counterintuitive."""
    body = client.get("/recommendations/scenario/2024-02").json()
    assert body["context"]["drivers_ranked"][0]["driver"] == "forecast_level_signal"
    counterintuitive = [
        note for note in body["context"]["footnotes"] if "mean reversion" in note
    ]
    assert counterintuitive == [] or body["context"]["footnotes"], (
        "a mean-reversion note may only appear if a trend feature actually fired"
    )


def test_footnotes_suppressed_when_no_cards_render() -> None:
    """A footnote explains a card; with no cards it is an orphaned note."""
    contributions = [
        _contribution("deviation_lag2", 0.02, "+1.0%", value=0.01),
        _contribution("prophet_forecast_level", -1.2, "200,000 t", value=200000.0),
    ]
    result = generate_recommendations(_response(0.10, contributions), limit=5)
    assert result["recommendations"] == []
    assert result["context"]["footnotes"] == []
