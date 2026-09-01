#!/usr/bin/env python3
"""Migrate ambiguous valuation symbols to explicit semantic identities.

The migration is deliberately narrow.  It only rewrites ``V_cash`` when the
surrounding section proves that it means distribution-weighted value or when
the same line explicitly identifies a cash balance.  Ambiguous occurrences
remain untouched and block completion.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "metric-namespace-migration.v1"
_TOKEN = re.compile(r"V[_\s]*cash", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _classify(line: str, section_heading: str) -> tuple[str, str, float | None] | None:
    context = section_heading + " " + line
    if re.search(r"分红率|派息率|distribution|M\s*[×x*]\s*IV", context, re.I):
        return "V_distribution", "distribution_weighted_intrinsic_value", None
    if re.search(r"净现金|net\s*cash", line, re.I):
        source_value = re.search(r"\bnet_cash\s*=\s*([0-9][0-9,]*(?:\.\d+)?)", line, re.I)
        canonical = float(source_value.group(1).replace(",", "")) if source_value else None
        return "net_cash_broad", "broad_net_cash", canonical
    if re.search(r"现金及银行|cash\s+and\s+bank", line, re.I):
        return "cash_and_bank_balances", "cash_and_bank_balances", None
    return None


def migrate_metric_namespace(output_dir: str | os.PathLike[str], *, apply: bool = False) -> dict[str, Any]:
    output = Path(output_dir)
    chapter_dir = output / "chapters" if (output / "chapters").is_dir() else output
    changes: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    pending: dict[Path, str] = {}
    for chapter in range(15):
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        lines = original.splitlines()
        section_heading = ""
        for index, line in enumerate(lines):
            if line.startswith("### "):
                section_heading = line
            if not _TOKEN.search(line):
                continue
            classified = _classify(line, section_heading)
            if classified is None:
                unresolved.append({"chapter": chapter, "line": index + 1, "text": line})
                continue
            symbol, metric_id, canonical_value = classified
            rewritten = _TOKEN.sub(symbol, line)
            if canonical_value is not None:
                cells = rewritten.split("|")
                if len(cells) >= 4 and cells[1].strip() == symbol:
                    suffix = "M" if "M" in cells[2] else ""
                    rendered = f"{canonical_value:,.2f}".rstrip("0").rstrip(".") + suffix
                    cells[2] = " " + rendered + " "
                    rewritten = "|".join(cells)
            if rewritten != line:
                lines[index] = rewritten
                changes.append({
                    "chapter": chapter, "line": index + 1, "metric_id": metric_id,
                    "old_symbol": "V_cash", "new_symbol": symbol,
                    "canonical_value_from_same_line_source": canonical_value,
                    "before": line, "after": rewritten,
                })
        new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
        if new_text != original:
            pending[path] = new_text
    if apply and unresolved:
        state = "BLOCKED"
    else:
        state = "MIGRATED" if changes else "NO_CHANGE"
        if apply:
            for path, value in pending.items():
                path.write_text(value, encoding="utf-8")
    result = {
        "schema_version": SCHEMA_VERSION, "generated_at": _now(),
        "applied": bool(apply and not unresolved), "state": state,
        "changed_lines": changes, "unresolved_lines": unresolved,
    }
    if apply:
        (output / "metric_namespace_migration.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate ambiguous valuation metric symbols")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = migrate_metric_namespace(args.output_dir, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
