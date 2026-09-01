#!/usr/bin/env python3
"""Read a fresh, auditable market snapshot from the standalone Niangao system.

Niangao owns quote acquisition and provider failover.  Turtle consumes its
SQLite projection read-only and materializes an immutable research-run input;
it never duplicates provider logic or writes back to Niangao.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SCHEMA_VERSION = "niangao-market-snapshot.v1"
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "_niangao" / "portfolio.db"
# Niangao persists provider timestamps without an offset.  Its CN/HK markets
# use the same local clock, so decoding must not inherit the CI runner's zone.
MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _now_text() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _parse_local_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MARKET_TIMEZONE)
    return parsed


def normalize_ts_code(value: object) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    if "." in raw:
        code, suffix = raw.rsplit(".", 1)
        if suffix == "HK" and code.isdigit():
            return f"{int(code):05d}.HK"
        return raw
    if raw.isdigit() and len(raw) <= 5:
        return f"{int(raw):05d}.HK"
    return raw


def _canonical_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_snapshot_file(
    path: str | os.PathLike[str], *, expected_code: str = "",
) -> dict[str, Any]:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"market_snapshot_unreadable:{target}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("market_snapshot_schema_invalid")
    claimed_hash = str(payload.get("snapshot_hash") or "")
    hash_input = dict(payload)
    hash_input.pop("snapshot_hash", None)
    if claimed_hash != _canonical_hash(hash_input):
        raise ValueError("market_snapshot_hash_mismatch")
    if expected_code and normalize_ts_code(payload.get("normalized_symbol")) != normalize_ts_code(expected_code):
        raise ValueError(
            f"market_snapshot_symbol_mismatch:{payload.get('normalized_symbol')}:{normalize_ts_code(expected_code)}"
        )
    try:
        if float(payload.get("price")) <= 0:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError("market_snapshot_price_invalid") from exc
    return payload


def read_niangao_snapshot(
    ts_code: str,
    *,
    db_path: str | os.PathLike[str] = DEFAULT_DB_PATH,
    max_age_minutes: int = 60,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a validated quote snapshot without mutating either system."""
    normalized = normalize_ts_code(ts_code)
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"niangao_db_missing:{path}")
    uri = f"file:{path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT ts_code, name, market, live_price, live_source,
                   live_fetched_at, live_prev_close, live_change_pct,
                   live_volume, live_open, live_high, live_low
              FROM watchlist WHERE ts_code = ?
            """,
            (normalized,),
        ).fetchone()
        refresh = conn.execute(
            """
            SELECT id, trigger_mode, status, started_at, finished_at,
                   source_counts_json, updated_codes_json
              FROM market_refresh_log
             WHERE status = 'success'
             ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    except sqlite3.Error as exc:
        raise ValueError(f"niangao_db_error:{exc}") from exc
    finally:
        if "conn" in locals():
            conn.close()
    if row is None:
        raise ValueError(f"niangao_symbol_missing:{normalized}")
    try:
        price = float(row["live_price"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"niangao_price_invalid:{normalized}") from exc
    if price <= 0:
        raise ValueError(f"niangao_price_invalid:{normalized}")
    fetched = _parse_local_time(row["live_fetched_at"])
    if fetched is None:
        raise ValueError(f"niangao_fetched_at_invalid:{normalized}")
    current = now or datetime.now(MARKET_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=MARKET_TIMEZONE)
    age_seconds = int((
        current.astimezone(MARKET_TIMEZONE) - fetched.astimezone(MARKET_TIMEZONE)
    ).total_seconds())
    if age_seconds < -300:
        raise ValueError(f"niangao_snapshot_from_future:{normalized}")
    if age_seconds > max(0, int(max_age_minutes)) * 60:
        raise ValueError(
            f"niangao_snapshot_stale:{normalized}:age_minutes={age_seconds // 60}:max={max_age_minutes}"
        )
    source = str(row["live_source"] or "").strip()
    if not source:
        raise ValueError(f"niangao_source_missing:{normalized}")
    refresh_payload = dict(refresh) if refresh is not None else {}
    updated_codes = []
    try:
        updated_codes = json.loads(refresh_payload.get("updated_codes_json") or "[]")
    except json.JSONDecodeError:
        pass
    batch_contains_symbol = normalized in updated_codes
    core = {
        "schema_version": SCHEMA_VERSION,
        "normalized_symbol": normalized,
        "name": str(row["name"] or ""),
        "market": str(row["market"] or ""),
        "currency": "HKD" if normalized.endswith(".HK") else "CNY",
        "price": price,
        "source": source,
        "fetched_at": fetched.isoformat(),
        "as_of": fetched.date().isoformat(),
        "age_seconds_at_capture": max(0, age_seconds),
        "quote": {
            "prev_close": row["live_prev_close"],
            "change_pct": row["live_change_pct"],
            "volume": row["live_volume"],
            "open": row["live_open"],
            "high": row["live_high"],
            "low": row["live_low"],
        },
        "refresh_run": {
            "id": refresh_payload.get("id"),
            "trigger_mode": refresh_payload.get("trigger_mode"),
            "status": refresh_payload.get("status"),
            "started_at": refresh_payload.get("started_at"),
            "finished_at": refresh_payload.get("finished_at"),
            "source_counts_json": refresh_payload.get("source_counts_json"),
            "batch_contains_symbol": batch_contains_symbol,
        },
        "provenance": {
            "system": "niangao",
            "database_path": str(path),
            "access_mode": "sqlite_read_only",
        },
        "captured_at": _now_text(),
    }
    core["snapshot_hash"] = _canonical_hash(core)
    return core


def write_snapshot(
    output_dir: str | os.PathLike[str], ts_code: str, **kwargs: Any,
) -> dict[str, Any]:
    snapshot = read_niangao_snapshot(ts_code, **kwargs)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    target = output / "market_snapshot.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)
    archive = output / "market_snapshots"
    archive.mkdir(parents=True, exist_ok=True)
    stamp = str(snapshot["fetched_at"]).replace(":", "").replace("+", "_")
    immutable = archive / f"{stamp}_{snapshot['snapshot_hash'][:12]}.json"
    if not immutable.exists():
        immutable.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot["snapshot_path"] = str(immutable)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a read-only Niangao quote snapshot")
    parser.add_argument("--code", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--max-age-minutes", type=int, default=60)
    args = parser.parse_args()
    try:
        snapshot = write_snapshot(
            args.output_dir, args.code, db_path=args.db, max_age_minutes=args.max_age_minutes,
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "snapshot": snapshot}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
