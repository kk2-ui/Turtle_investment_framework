#!/usr/bin/env python3
"""Controlled registration CLI for canonical Frozen J1 bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
from typing import Any

try:
    from scripts import enterprise_judgment_reconstruction as reconstruction
    from scripts import enterprise_judgment_source_packet as source_packet
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_reconstruction as reconstruction
    import enterprise_judgment_source_packet as source_packet


def _read(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def register_from_artifacts(
    conn: sqlite3.Connection,
    *,
    source_packet_receipt: dict[str, Any],
    decision_contract: dict[str, Any],
    enterprise_model: dict[str, Any],
    decision_ledger: dict[str, Any],
    spec: dict[str, Any],
    frozen_at: str,
) -> dict[str, Any]:
    """Compile and freeze J1 from its five approved cutoff-visible artifacts."""
    source_result = source_packet.compile_core_source_package(source_packet_receipt)
    if not source_result["valid"]:
        raise ValueError("invalid source packet: " + "; ".join(source_result["findings"]))
    source_package = source_result["source_package"]
    compiled = reconstruction.compile_enterprise_reconstruction(
        spec,
        source_packet_receipt=source_packet_receipt,
        source_package=source_package,
        enterprise_model=enterprise_model,
        decision_ledger=decision_ledger,
        decision_contract=decision_contract,
    )
    if not compiled["valid"]:
        raise ValueError("invalid J1 reconstruction: " + "; ".join(compiled["findings"]))
    inputs = {
        "spec": spec,
        "source_packet_receipt": source_packet_receipt,
        "source_package": source_package,
        "enterprise_model": enterprise_model,
        "decision_ledger": decision_ledger,
        "decision_contract": decision_contract,
    }
    return reconstruction.register_frozen_reconstruction(
        conn,
        compiled["reconstruction"],
        inputs,
        frozen_at=frozen_at,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=reconstruction.CANONICAL_REGISTRY_PATH)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--decision-contract", type=Path, required=True)
    parser.add_argument("--enterprise-model", type=Path, required=True)
    parser.add_argument("--decision-ledger", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--frozen-at", required=True)
    args = parser.parse_args()
    conn = sqlite3.connect(args.db)
    try:
        result = register_from_artifacts(
            conn,
            source_packet_receipt=_read(args.receipt),
            decision_contract=_read(args.decision_contract),
            enterprise_model=_read(args.enterprise_model),
            decision_ledger=_read(args.decision_ledger),
            spec=_read(args.spec),
            frozen_at=args.frozen_at,
        )
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
