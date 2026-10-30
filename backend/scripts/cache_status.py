"""
Which store searches are in the 24 h cache right now, without any live call.

    cd backend
    python scripts/cache_status.py "white denim pants" --min 10 --max 40
    python scripts/cache_status.py "womens ecru ribbed turtleneck" --min 10 --max 40 --broaden

--broaden also lists the queries search broadening would try (tools.py).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("FITFINDR_DATA_MODE", "live")

import tools  # noqa: E402
from sources import ADAPTERS, cache, cache_key  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--min", type=float, default=None)
    parser.add_argument("--max", type=float, default=None)
    parser.add_argument("--broaden", action="store_true")
    args = parser.parse_args()
    queries = [args.query]
    if args.broaden:
        core, dropped = tools.core_query(args.query)
        queries += ([core] if dropped else []) + tools.synonym_queries(core)[:1]
    for q in queries:
        for adapter in ADAPTERS:
            if not adapter.ENABLED:
                continue
            raw = cache.get(cache_key(adapter, q, args.max, args.min), adapter.FIXTURE_PREFIX)
            n = len(adapter.parse(raw)) if raw is not None else None
            print(f"{adapter.FIXTURE_PREFIX:7} {q!r:45} {'cached, ' + str(n) + ' listings' if raw is not None else 'not cached'}")


if __name__ == "__main__":
    main()
