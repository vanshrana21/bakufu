"""Write the API's route table to a file both sides of the repo can check.

The frontend declares which backend routes it calls (frontend/lib/api/routes.ts)
and which of those the browser may reach through the proxy. Nothing stopped that
declaration from drifting away from FastAPI: a renamed path or a changed method
would compile, pass every unit test, and only fail as a 404 in front of a judge.

This script is the shared fact. `tests/test_route_manifest.py` fails when the
checked-in file no longer matches the app, and the frontend's route-registry
test fails when it names a route this file does not contain.

Usage:
    python scripts/export_routes.py            # rewrite the manifest
    python scripts/export_routes.py --check    # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MANIFEST_PATH = ROOT.parent / "frontend" / "lib" / "api" / "backend-routes.json"

#: Methods FastAPI adds for free and nobody calls deliberately.
_IGNORED_METHODS = {"HEAD", "OPTIONS"}


def route_table() -> list[dict[str, Any]]:
    """Every (method, path) the app serves, with the query parameters it accepts.

    Read from the OpenAPI document rather than `app.routes`: recent FastAPI keeps
    included routers lazy, so `app.routes` holds unexpanded `_IncludedRouter`
    placeholders and would report a single route for the whole API. The OpenAPI
    document is also the contract the frontend is written against, including the
    exact query-parameter names, which is what makes drift detectable.
    """
    # Importing the app needs a key, because the settings refuse to load without
    # one. The value is irrelevant here: no request is made.
    os.environ.setdefault("API_KEY", "route-export-placeholder")

    from src.api.main import app

    rows: list[dict[str, Any]] = []
    for path, operations in app.openapi().get("paths", {}).items():
        for method, operation in operations.items():
            if method.upper() in _IGNORED_METHODS:
                continue
            query = sorted(
                parameter["name"]
                for parameter in operation.get("parameters", [])
                if parameter.get("in") == "query"
            )
            required_query = sorted(
                parameter["name"]
                for parameter in operation.get("parameters", [])
                if parameter.get("in") == "query" and parameter.get("required")
            )
            rows.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "query": query,
                    "required_query": required_query,
                }
            )
    return sorted(rows, key=lambda row: (row["path"], row["method"]))


def manifest() -> dict[str, Any]:
    return {
        "_generated_by": "backend/scripts/export_routes.py",
        "_do_not_edit": "Run the script; tests/test_route_manifest.py enforces it.",
        "routes": route_table(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when stale instead of rewriting")
    args = parser.parse_args(argv)

    current = manifest()
    serialised = json.dumps(current, indent=2) + "\n"

    if args.check:
        if not MANIFEST_PATH.exists():
            print(f"missing: {MANIFEST_PATH}", file=sys.stderr)
            return 1
        if MANIFEST_PATH.read_text(encoding="utf-8") != serialised:
            print(f"stale: {MANIFEST_PATH} — run python scripts/export_routes.py", file=sys.stderr)
            return 1
        print(f"up to date: {len(current['routes'])} routes")
        return 0

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(serialised, encoding="utf-8")
    print(f"wrote {len(current['routes'])} routes to {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
