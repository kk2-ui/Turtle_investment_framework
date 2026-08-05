import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.market_refresh import (
    JUDGMENT_FRONTIER, build_market_decision_candidate, build_market_refresh,
    evaluate_output_market_refresh,
)
from scripts.metric_namespace_migration import migrate_metric_namespace
from scripts.decision_compiler import _scan_metric_identity_conflicts
from scripts.market_refresh_promotion import propagate_market_refresh_chapters, promote_market_refresh
from scripts.niangao_market_bridge import (
    normalize_ts_code, read_niangao_snapshot, verify_snapshot_file, write_snapshot,
)


def _db(path: Path, *, code: str = "01502.HK", price: float = 1.99, fetched_at: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE watchlist (
          ts_code TEXT PRIMARY KEY, name TEXT, market TEXT, live_price REAL,
          live_source TEXT, live_fetched_at TEXT, live_prev_close REAL,
          live_change_pct REAL, live_volume REAL, live_open REAL,
          live_high REAL, live_low REAL
        );
        CREATE TABLE market_refresh_log (
          id INTEGER PRIMARY KEY, trigger_mode TEXT, status TEXT, started_at TEXT,
          finished_at TEXT, source_counts_json TEXT, updated_codes_json TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO watchlist VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (code, "测试公司", "H", price, "stock-sdk", fetched_at, 2.0, -0.5, 10, 2.0, 2.1, 1.9),
    )
    conn.execute(
        "INSERT INTO market_refresh_log VALUES (1,'background_loop','success',?,?,?,?)",
        (fetched_at, fetched_at, '{"stock-sdk":1}', json.dumps([code])),
    )
    conn.commit()
    conn.close()


def test_symbol_normalization_preserves_explicit_a_and_normalizes_hk():
    assert normalize_ts_code("1502.HK") == "01502.HK"
    assert normalize_ts_code("000651.SZ") == "000651.SZ"
    assert normalize_ts_code("600036.SH") == "600036.SH"


def test_fresh_snapshot_is_read_only_hashed_and_archived(tmp_path: Path):
    now = datetime(2026, 8, 4, 9, 0, tzinfo=timezone(timedelta(hours=8)))
    db = tmp_path / "portfolio.db"
    _db(db, fetched_at="2026-08-04 08:50:00")
    before = db.read_bytes()
    snapshot = write_snapshot(tmp_path / "out", "1502.HK", db_path=db, now=now, max_age_minutes=30)
    assert snapshot["price"] == 1.99
    assert snapshot["source"] == "stock-sdk"
    assert snapshot["refresh_run"]["batch_contains_symbol"] is True
    assert db.read_bytes() == before
    verified = verify_snapshot_file(tmp_path / "out" / "market_snapshot.json", expected_code="01502.HK")
    assert verified["snapshot_hash"] == snapshot["snapshot_hash"]
    assert len(list((tmp_path / "out" / "market_snapshots").glob("*.json"))) == 1


def test_stale_or_wrong_symbol_snapshot_fails_closed(tmp_path: Path):
    now = datetime(2026, 8, 4, 9, 0, tzinfo=timezone(timedelta(hours=8)))
    db = tmp_path / "portfolio.db"
    _db(db, fetched_at="2026-08-04 07:00:00")
    with pytest.raises(ValueError, match="niangao_snapshot_stale"):
        read_niangao_snapshot("01502.HK", db_path=db, now=now, max_age_minutes=30)
    with pytest.raises(ValueError, match="niangao_symbol_missing"):
        read_niangao_snapshot("000651.SZ", db_path=db, now=now, max_age_minutes=180)


def test_refresh_candidate_does_not_mutate_frozen_ledger(tmp_path: Path, monkeypatch):
    output = tmp_path / "output"
    output.mkdir()
    bundle = {
        "market": {"price_native": 2.02, "shares_m": 100.0, "pricing_code": "01502.HK"},
        "params": {"II": 5.5, "g_base": 2.0, "b_penalty": 0.04, "dps_latest": 0.1},
    }
    entries = [
        {"entry_id": "D001", "metric_id": "market.price.current", "value": 2.02, "as_of": "2025-12-31", "status": "active"},
        {"entry_id": "D002", "metric_id": "return.gg.base", "value": 6.2, "as_of": "FY2023-2025", "status": "active"},
        {"entry_id": "D003", "metric_id": "return.gg.fcfe", "value": 8.0, "as_of": "FY2023-2025", "status": "active"},
        {"entry_id": "D004", "metric_id": "return.gg.normalized", "value": 6.2, "as_of": "FY2023-2025", "status": "active"},
    ]
    (output / "compute_bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    (output / "decision_ledger.json").write_text(json.dumps({"report_id": "01502.HK", "entries": entries}), encoding="utf-8")
    original_ledger = (output / "decision_ledger.json").read_bytes()

    snapshot = {
        "price": 1.99, "source": "stock-sdk", "fetched_at": "2026-08-04T08:50:00+08:00",
        "as_of": "2026-08-04", "snapshot_hash": "a" * 64,
    }
    monkeypatch.setattr("scripts.market_refresh.write_snapshot", lambda *a, **k: snapshot)
    monkeypatch.setattr(
        "scripts.market_refresh.compute_from_db",
        lambda *a, **k: {
            "market": {"price_native": 1.99},
            "factor3": {"gg": {"base": 6.3}, "gg_fcfe": {"base": 8.1}, "gg_normalized": {"base": 6.3}},
        },
    )
    monkeypatch.setattr(
        "scripts.market_refresh.build_market_decision_candidate",
        lambda ledger, bundle, snapshot, manifest: (
            ledger, {"combined_buy_price_native": 1.6, "return_margin_pct": -2.6}
        ),
    )
    result = build_market_refresh(output, "01502.HK")
    assert result["state"] == "RECOMPUTE_REQUIRED"
    assert result["promotion_allowed"] is False
    assert result["judgment_frontier"] == list(JUDGMENT_FRONTIER)
    assert (output / "decision_ledger.json").read_bytes() == original_ledger
    candidate = json.loads((output / "compute_bundle.market_candidate.json").read_text())
    assert candidate["market"]["price_source"] == "niangao:stock-sdk"
    validation = evaluate_output_market_refresh(output)
    assert validation["state"] == "RECOMPUTE_REQUIRED"
    assert validation["status"] == "INCOMPLETE"


def test_timestamp_only_refresh_does_not_reopen_action_judgments(tmp_path: Path, monkeypatch):
    output = tmp_path / "output"
    output.mkdir()
    (output / "compute_bundle.json").write_text(json.dumps({
        "market": {"price_native": 1.99, "shares_m": 100.0, "pricing_code": "01502.HK"},
        "params": {"II": 5.5, "g_base": 2.0, "b_penalty": 0.04, "dps_latest": 0.1},
    }), encoding="utf-8")
    values = {
        "market.price.current": 1.99, "return.gg.base": 6.3,
        "return.gg.fcfe": 8.1, "return.gg.normalized": 6.3,
    }
    entries = [
        {"entry_id": f"D00{i}", "metric_id": metric, "value": value,
         "as_of": "2025-12-31" if i == 1 else "FY2023-2025", "status": "active"}
        for i, (metric, value) in enumerate(values.items(), 1)
    ]
    (output / "decision_ledger.json").write_text(json.dumps({"report_id": "01502.HK", "entries": entries}), encoding="utf-8")
    monkeypatch.setattr("scripts.market_refresh.write_snapshot", lambda *a, **k: {
        "price": 1.99, "source": "stock-sdk", "fetched_at": "2026-08-04T08:50:00+08:00",
        "as_of": "2026-08-04", "snapshot_hash": "b" * 64,
    })
    monkeypatch.setattr("scripts.market_refresh.compute_from_db", lambda *a, **k: {
        "market": {"price_native": 1.99},
        "factor3": {"gg": {"base": 6.3}, "gg_fcfe": {"base": 8.1}, "gg_normalized": {"base": 6.3}},
    })
    result = build_market_refresh(output, "01502.HK")
    assert result["state"] == "RECOMPUTE_REQUIRED"
    assert result["judgment_frontier"] == ["market.price.current"]
    assert result["required_next_step"] == "refresh_market_identity_and_recompile_protected_chapters"


def test_metric_namespace_migration_splits_distribution_and_cash_balance(tmp_path: Path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "_ch12.md").write_text(
        "## Ch12\n### 分红率与V_cash\nV_cash = 50%×IV = 605M\n| V_cash | 605M | 分红率×IV |\n",
        encoding="utf-8",
    )
    (chapters / "_ch14.md").write_text(
        "## Ch14\n| V_cash | 1,695M | 净现金(含存款) [source: compute_aa net_cash=1,724.75M] |\n", encoding="utf-8",
    )
    before = _scan_metric_identity_conflicts(tmp_path)
    assert any(item.startswith("metric_identity_conflict:valuation.v_cash") for item in before)
    result = migrate_metric_namespace(tmp_path, apply=True)
    assert result["state"] == "MIGRATED"
    assert result["unresolved_lines"] == []
    assert "V_distribution" in (chapters / "_ch12.md").read_text()
    ch14 = (chapters / "_ch14.md").read_text()
    assert "net_cash_broad" in ch14
    assert "1,724.75M" in ch14
    assert _scan_metric_identity_conflicts(tmp_path) == []


def test_single_legacy_v_cash_is_still_ambiguous(tmp_path: Path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "_ch12.md").write_text("## Ch12\n| V_cash | 605M | value |\n", encoding="utf-8")
    assert _scan_metric_identity_conflicts(tmp_path) == [
        "ambiguous_metric_symbol:valuation.v_cash:Ch12:L2=605"
    ]


def test_market_decision_candidate_uses_combined_return_hurdle():
    metrics = [
        ("D001", "market.price.current", 2.02, "HKD"),
        ("D002", "return.gg.base", 6.2, "%"),
        ("D003", "return.gg.fcfe", 8.0, "%"),
        ("D004", "return.gg.normalized", 6.2, "%"),
        ("D005", "hurdle.ii", 5.5, "%"),
        ("D006", "valuation.v_final", 2.8, "HKD"),
        ("D007", "moat.lambda", 0.625, "ratio"),
        ("D008", "return.required", 10.0, "%"),
        ("D009", "moat.decay", 3.2, "%"),
        ("D010", "margin.price", 27.9, "%"),
        ("D011", "margin.return", -2.7, "pct"),
        ("D012", "decision.position.recommended", 1.5, "%"),
        ("D013", "trigger.buy", 1.98, "HKD"),
        ("D014", "trigger.reduce", "毛利率规则", "condition"),
        ("D015", "trigger.exit", "审计规则", "condition"),
    ]
    entries = [{
        "entry_id": entry_id, "metric_id": metric_id, "value": value, "unit": unit,
        "scenario": "base", "basis": "old", "as_of": "2025-12-31", "version": 1,
        "status": "active", "chapters": [], "source_ids": ["old"], "affects_action": True,
    } for entry_id, metric_id, value, unit in metrics]
    manifest = {
        "qualitative_decision": "pause", "quantitative_decision": "hold",
        "unified_decision": "hold", "display_label": "Hold Review",
        "decision_family": "Hold", "position_pct": 1.5,
    }
    ledger = {
        "schema_version": "decision-ledger.v1", "report_id": "01502.HK", "revision": 1,
        "lifecycle": "decision_ready", "change_reason": "old", "decision": manifest,
        "entries": entries, "freeze": {"frozen": False, "fingerprint": "", "frozen_at": None},
    }
    bundle = {
        "market": {"shares_m": 373.5, "fx": 0.9346, "mc_rmb": 694.66},
        "params": {"g_base": 2.0},
        "factor3": {
            "gg": {"base": 6.3}, "gg_fcfe": {"base": 8.1},
            "gg_normalized": {"base": 6.3}, "g_adj": 2.0,
        },
        "factor4": {"dividend_identity": {"dps_native": 0.1551, "yield_pretax_pct": 7.8}},
    }
    candidate, derivation = build_market_decision_candidate(
        ledger, bundle,
        {"price": 1.99, "source": "stock-sdk", "as_of": "2026-08-04"},
        manifest=manifest,
    )
    by_metric = {item["metric_id"]: item for item in candidate["entries"]}
    assert by_metric["trigger.buy"]["value"] == 1.6
    assert "r*+decay" in by_metric["trigger.buy"]["rationale"]
    assert by_metric["margin.price"]["value"] == 28.9
    assert by_metric["margin.return"]["value"] == -2.6
    assert "既有持仓" in by_metric["decision.position.recommended"]["basis"]
    assert derivation["combined_buy_price_native"] == pytest.approx(1.5993, abs=0.001)


def test_structured_refresh_return_decomposition_does_not_double_count_margin():
    from scripts.market_refresh_structured import _refresh_return_decomposition_model

    model = {
        "assumptions": {
            "growth_value_return_pct": 2.8,
            "required_return_pct": 10.0,
            "moat_decay_pct": 3.2,
        },
        "result": {"gross_return_pct": 18.4, "return_safety_margin_pct": -2.6},
    }
    _refresh_return_decomposition_model(model, dividend_yield_pct=7.8)
    assert model["result"]["gross_return_pct"] == 10.6
    assert model["result"]["return_safety_margin_pct"] == -2.6


def test_market_propagation_keeps_ddm_threshold_separate_from_buy_action(tmp_path: Path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "_ch13.md").write_text(
        "## Ch13\nP*=1.98来自DPS与10%年化DDM公式。\n"
        "主买价P*=1.98 HKD，价≤P*才买。 [decision: D013]\n"
        "当前价2.02 HKD。 [decision: D001]\n"
        "Step 8.0：少数股东调整。[decision: D003]\n"
        "价格MOS=(2.80−2.02)/2.80=27.9%。 [decision: D010]\n",
        encoding="utf-8",
    )
    old = {"entries": [
        {"entry_id": "D001", "value": 2.02}, {"entry_id": "D013", "value": 1.98},
    ]}
    new = {"entries": [
        {"entry_id": "D001", "value": 1.99}, {"entry_id": "D003", "value": 8.1},
        {"entry_id": "D010", "value": 28.9}, {"entry_id": "D013", "value": 1.6},
    ]}
    old["entries"].extend([
        {"entry_id": "D003", "value": 8.0}, {"entry_id": "D010", "value": 27.9},
    ])
    result = propagate_market_refresh_chapters(tmp_path, old, new, chapters=[13])
    text = (chapters / "_ch13.md").read_text()
    second = propagate_market_refresh_chapters(tmp_path, old, new, chapters=[13])
    assert result["changed_chapters"] == [13]
    assert "P_DDM=1.98" in text
    assert "不能作为canonical首次买入线" in text
    assert "P_buy=1.60 HKD" in text
    assert "当前价1.99 HKD" in text
    assert "Step 8.0" in text
    assert "价格MOS=(2.80−1.99)/2.80=28.9%" in text
    assert second["changed_chapters"] == []
    assert (chapters / "_ch13.md").read_text() == text


def test_market_promotion_rejects_wrong_approval_fingerprint_without_writes(tmp_path: Path):
    (tmp_path / "decision_ledger.json").write_text('{"sentinel":true}', encoding="utf-8")
    before = (tmp_path / "decision_ledger.json").read_bytes()
    result = promote_market_refresh(
        tmp_path, approval_fingerprint="wrong", approved_by="operator:user", rationale="test",
    )
    assert result["state"] == "BLOCKED"
    assert (tmp_path / "decision_ledger.json").read_bytes() == before
