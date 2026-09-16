"""Point serving at a model version in the registry.

Promotion is deliberate here: a training run publishes an immutable version,
and this script decides which one inference loads. The API picks the change up
without a restart.

  python -m scripts.promote_model --list
  python -m scripts.promote_model <version>
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from src.models import registry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", help="version directory name to activate")
    parser.add_argument("--list", action="store_true", help="list published versions and exit")
    args = parser.parse_args(argv)

    published = registry.versions()
    active = registry.active_model()
    if args.list or not args.version:
        print(f"active: {active.version} ({active.source}, fence {active.fence})")
        print("published versions:")
        for version in published:
            print(f"  {version}{'  <- active' if version == active.version else ''}")
        if not published:
            print("  (none yet - POST /train publishes one)")
        return 0 if args.list else 2

    if args.version not in published:
        print(f"no version {args.version}; run --list", file=sys.stderr)
        return 2
    promoted = registry.activate_version(args.version)
    print(f"active: {promoted.version} ({promoted.source}, fence {promoted.fence})")
    print(f"  model: {promoted.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
