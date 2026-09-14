"""Integrity checks for the MOIL mine reference data.

These guard the contract the Phase 4 rules engine will rely on: ten mines,
every field populated, equipment drawn only from attested vocabulary, and
every source tag resolvable to a URL.
"""

from __future__ import annotations

import pytest

from src.reference.moil_mines import (
    MINE_TYPE_COUNTS,
    MOIL_MINES,
    OPENCAST_FLEET_VOCAB,
    SOURCE_URLS,
    UNDERGROUND_FLEET_VOCAB,
)

REQUIRED_FIELDS = ("state", "district", "mine_type", "equipment", "notes", "sources")
VALID_TYPES = {"underground", "opencast", "mixed"}
GENERIC = {"standard_underground_fleet", "standard_opencast_fleet"}


def test_ten_mines_present() -> None:
    assert len(MOIL_MINES) == 10


def test_all_mines_have_required_fields() -> None:
    for name, mine in MOIL_MINES.items():
        for field in REQUIRED_FIELDS:
            assert field in mine, f"{name} is missing {field}"
            assert mine[field], f"{name}.{field} must not be empty"
        assert isinstance(mine["equipment"], list) and mine["equipment"], name
        assert isinstance(mine["sources"], list) and mine["sources"], name
        # Present on every mine, but allowed to be None when undisclosed.
        assert "capacity_target_tonnes" in mine, name


def test_mine_types_valid() -> None:
    for name, mine in MOIL_MINES.items():
        assert mine["mine_type"] in VALID_TYPES, f"{name}: {mine['mine_type']}"


def test_state_split() -> None:
    """Six mines in Maharashtra, four in MP - matches the problem-statement scope."""
    states = [mine["state"] for mine in MOIL_MINES.values()]
    assert states.count("MH") == 6
    assert states.count("MP") == 4


def test_equipment_vocab_consistency() -> None:
    allowed = set(UNDERGROUND_FLEET_VOCAB) | set(OPENCAST_FLEET_VOCAB) | GENERIC
    for name, mine in MOIL_MINES.items():
        for item in mine["equipment"]:
            assert item in allowed, f"{name} uses unknown equipment term {item!r}"


def test_sources_resolvable() -> None:
    for name, mine in MOIL_MINES.items():
        for tag in mine["sources"]:
            assert tag in SOURCE_URLS, f"{name} cites unknown source tag {tag!r}"


def test_mine_type_counts_match_the_mine_table() -> None:
    """The declared split must agree with the mines themselves."""
    counts: dict[str, int] = {}
    for mine in MOIL_MINES.values():
        counts[mine["mine_type"]] = counts.get(mine["mine_type"], 0) + 1
    assert counts == MINE_TYPE_COUNTS
    assert sum(MINE_TYPE_COUNTS.values()) == len(MOIL_MINES)


def test_kandri_ambiguity_is_recorded() -> None:
    """Kandri defaults to underground but must carry the EC caveat."""
    kandri = MOIL_MINES["Kandri"]
    assert kandri["mine_type"] == "underground"
    assert "type_note" in kandri
    assert "mixed" in kandri["type_note"].lower()


def test_generic_fleets_are_used_alone() -> None:
    """A generic fallback must not be mixed with specific equipment.

    Mixing them would let the rules engine emit both a concrete recommendation
    and a generic one for the same mine.
    """
    for name, mine in MOIL_MINES.items():
        equipment = set(mine["equipment"])
        if equipment & GENERIC:
            assert equipment <= GENERIC, f"{name} mixes generic and specific terms"


def test_undisclosed_mines_fall_back_to_their_type() -> None:
    """Mines with no disclosure at all get the fallback matching their type.

    Ukwa is deliberately not in this list: rock mechanics monitoring is named
    for it, so it records that one item rather than a generic fallback. The
    rules engine still reaches UNDERGROUND_FLEET_VOCAB for generic advice.
    """
    expected = {
        "Munsar": "standard_underground_fleet",
        "Beldongri": "standard_underground_fleet",
        "Sitapatore": "standard_opencast_fleet",
    }
    for name, fleet in expected.items():
        assert MOIL_MINES[name]["equipment"] == [fleet], name


def test_ukwa_records_its_one_disclosed_item() -> None:
    """Ukwa asserts exactly what is known - no more, no less."""
    ukwa = MOIL_MINES["Ukwa"]
    assert ukwa["equipment"] == ["rock_mechanics_monitoring"]
    assert "rock_mechanics_monitoring" in UNDERGROUND_FLEET_VOCAB
    assert not set(ukwa["equipment"]) & GENERIC, "no generic fallback alongside it"


def test_capacity_targets_only_where_disclosed() -> None:
    """Only the three mines with a stated numeric target carry one."""
    disclosed = {
        name: mine["capacity_target_tonnes"]
        for name, mine in MOIL_MINES.items()
        if mine["capacity_target_tonnes"] is not None
    }
    assert disclosed == {"Balaghat": 800000, "Gumgaon": 350000, "Kandri": 100000}
    for value in disclosed.values():
        assert isinstance(value, int) and value > 0


def test_every_source_url_is_used() -> None:
    """No orphan entries in the lookup - a stale URL is a maintenance trap."""
    cited = {tag for mine in MOIL_MINES.values() for tag in mine["sources"]}
    assert cited == set(SOURCE_URLS), f"unused: {set(SOURCE_URLS) - cited}"


@pytest.mark.parametrize("url", SOURCE_URLS.values())
def test_source_urls_are_well_formed(url: str) -> None:
    assert url.startswith("https://")
