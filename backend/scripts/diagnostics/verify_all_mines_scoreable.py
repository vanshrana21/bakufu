"""Score all ten MOIL mines through POST /predict/point and report coverage.

Uses the real endpoint via TestClient, so each call also writes one row to the
predictions table in the configured database - the endpoint's normal
behaviour. Exits non-zero if any mine returns a non-200 or is scored without
real imagery.

Run: python scripts/diagnostics/verify_all_mines_scoreable.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402
from src.config.settings import get_verified_mines, settings  # noqa: E402
from src.data.preprocess.extract_features import BAND_FEATURES  # noqa: E402
from src.models.prospectivity.predict import ACTIVE_S2_PATH  # noqa: E402
from src.reference.moil_mines import OPENCAST_FLEET_VOCAB  # noqa: E402


def main() -> int:
    failures: list[str] = []
    print(f"serving mosaic: {ACTIVE_S2_PATH.name}\n")
    header = f"{'mine':14} {'lat':>8} {'lon':>8}  {'HTTP':>4}  {'score':>6}  {'imagery':7}  confidence"
    print(header)
    print("-" * len(header))

    with TestClient(app) as client:
        for name, mine in settings.MOIL_MINES.items():
            response = client.post("/predict/point", json={"lat": mine["lat"], "lon": mine["lon"]})
            score, imagery = None, False
            if response.status_code == 200:
                body = response.json()
                extracted = body["features_extracted"]
                imagery = all(extracted.get(band) not in (None, 0.0) for band in BAND_FEATURES)
                score = body["prospectivity_score"]
                if not imagery:
                    failures.append(f"{name}: scored without real imagery")
            else:
                failures.append(
                    f"{name}: HTTP {response.status_code} {response.json().get('error_code')}"
                )

            detail = client.get(f"/mines/{name}").json()
            if detail["confidence"] != mine["confidence"]:
                failures.append(f"{name}: /mines confidence {detail['confidence']} != settings")

            shown = f"{score:.4f}" if score is not None else "  —   "
            print(
                f"{name:14} {mine['lat']:8.4f} {mine['lon']:8.4f}  {response.status_code:>4}  "
                f"{shown:>6}  {'yes' if imagery else 'NO':7}  {mine['confidence']}"
            )

        sitapatore = client.get("/mines/Sitapatore").json()
        scenario = client.get(
            "/recommendations/scenario/2021-04", params={"mine_name": "Sitapatore"}
        ).json()
        equipment = {
            item for card in scenario["recommendations"] for item in card["equipment_referenced"]
        }
        opencast_ok = (
            sitapatore["mine_type"] == "opencast"
            and set(sitapatore["fleet_vocabulary"]["applicable"]) == set(OPENCAST_FLEET_VOCAB)
            and bool(equipment)
            and equipment <= set(OPENCAST_FLEET_VOCAB)
        )
        if not opencast_ok:
            failures.append(f"Sitapatore: recommendations not opencast ({sorted(equipment)})")

    print(f"\nSitapatore: {sitapatore['mine_type']}, {sitapatore['state']}/{sitapatore['district']}, "
          f"{len(scenario['recommendations'])} scenario cards, equipment {sorted(equipment)}")
    missing_urls = [name for name, mine in settings.MOIL_MINES.items() if mine["source_url"] is None]
    print(f"verified mines (confidence != none): {len(get_verified_mines())} of {len(settings.MOIL_MINES)}")
    print(f"mines without a full source URL: {', '.join(missing_urls) or 'none'}")

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("\nALL 10 MINES SCOREABLE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
