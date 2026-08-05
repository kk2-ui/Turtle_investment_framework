#!/usr/bin/env python3
"""Refresh gg_override.json files from existing Zone B partials."""

import argparse
import json
import os
from pathlib import Path

from zone_b_v8 import build_gg_override_from_partials


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_BASE = ROOT / "output"


def refresh_stock_dir(stock_dir: Path) -> bool:
    partials = {}
    for path in sorted(stock_dir.glob("zone_b_*_partial.json")):
        year = path.stem.replace("zone_b_", "").replace("_partial", "")
        try:
            partials[year] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    override = build_gg_override_from_partials(partials, stock_dir=str(stock_dir))
    gg_path = stock_dir / "gg_override.json"
    if override:
        gg_path.write_text(json.dumps(override, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    if gg_path.exists():
        gg_path.unlink()
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", help="Stock code prefix, e.g. 02669")
    args = parser.parse_args()

    targets = []
    for path in sorted(OUTPUT_BASE.iterdir()):
        if not path.is_dir():
            continue
        if args.code and not path.name.startswith(args.code):
            continue
        if any(path.glob("zone_b_*_partial.json")):
            targets.append(path)

    refreshed = 0
    for stock_dir in targets:
        if refresh_stock_dir(stock_dir):
            refreshed += 1
            print(f"✅ {stock_dir.name}")
        else:
            print(f"⚪ {stock_dir.name}")

    print(f"refreshed={refreshed}/{len(targets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
