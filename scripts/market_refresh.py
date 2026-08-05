#!/usr/bin/env python3
"""Build a non-promoting market refresh candidate for a Turtle report.

The workflow captures Niangao's quote, recomputes the deterministic bundle in
a separate file, and emits an explicit dependency frontier.  Frozen decision
ledgers and report chapters are never changed here.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

try:
    from scripts.compute_bundle import compute_from_db, load_zone_j_params
    from scripts.decision_ledger import (
        decision_diff, ledger_fingerprint, validate_chapter_decision_references,
        validate_decision_ledger,
    )
    from scripts.decision_compiler import (
        _action_consistency, _scan_free_critical_values, select_canonical_entries,
    )
    from scripts.niangao_market_bridge import DEFAULT_DB_PATH, write_snapshot
except ModuleNotFoundError:
    from compute_bundle import compute_from_db, load_zone_j_params
    from decision_ledger import (
        decision_diff, ledger_fingerprint, validate_chapter_decision_references,
        validate_decision_ledger,
    )
    from decision_compiler import _action_consistency, _scan_free_critical_values, select_canonical_entries
    from niangao_market_bridge import DEFAULT_DB_PATH, write_snapshot


SCHEMA_VERSION = "turtle-market-refresh.v1"
DETERMINISTIC_METRICS = (
    "market.price.current", "return.gg.base", "return.gg.fcfe", "return.gg.normalized",
)
JUDGMENT_FRONTIER = (
    "margin.price", "margin.return", "decision.position.recommended",
    "trigger.buy",
)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _active_by_metric(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("metric_id")): item for item in ledger.get("entries") or []
        if isinstance(item, dict) and item.get("status", "active") == "active"
    }


def _recompute_params(output: Path, current: dict[str, Any]) -> dict[str, Any]:
    params = load_zone_j_params(str(output))
    allowed = ("II", "Rf", "Q", "O", "PORTFOLIO_CAP_PCT", "g_base", "b_penalty", "dps_latest")
    params.update({key: current.get("params", {}).get(key) for key in allowed if key in current.get("params", {})})
    return params


def _number(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"market_decision_input_missing:{label}") from exc
    if result <= 0:
        raise ValueError(f"market_decision_input_invalid:{label}")
    return result


def _update_entry(
    entries: dict[str, dict[str, Any]], metric_id: str, *, value: Any,
    as_of: str | None = None, basis: str | None = None,
    source_ids: list[str] | None = None, rationale: str | None = None,
) -> None:
    entry = entries.get(metric_id)
    if entry is None:
        raise ValueError(f"market_decision_entry_missing:{metric_id}")
    entry["value"] = value
    if as_of is not None:
        entry["as_of"] = as_of
    if basis is not None:
        entry["basis"] = basis
    if source_ids is not None:
        entry["source_ids"] = source_ids
    if rationale is not None:
        entry["rationale"] = rationale
    entry["version"] = int(entry.get("version") or 1) + 1


def build_market_decision_candidate(
    ledger: dict[str, Any], candidate_bundle: dict[str, Any], snapshot: dict[str, Any],
    *, manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recompute every canonical metric whose value or action depends on price."""
    candidate = deepcopy(ledger)
    candidate["lifecycle"] = "reviewable"
    candidate["change_reason"] = (
        "年糕行情快照刷新后重算市值、GG、双安全边际及综合回报买点；"
        "未改变财务期、V_final、r*或decay"
    )
    candidate["freeze"] = {"frozen": False, "fingerprint": "", "frozen_at": None}
    entries = {
        str(item.get("metric_id")): item for item in candidate.get("entries") or []
        if isinstance(item, dict) and item.get("status", "active") == "active"
    }
    market = candidate_bundle.get("market") or {}
    factor3 = candidate_bundle.get("factor3") or {}
    factor4 = candidate_bundle.get("factor4") or {}
    price = _number(snapshot.get("price"), "price")
    shares = _number(market.get("shares_m"), "shares_m")
    fx = _number(market.get("fx"), "fx")
    mc_rmb = _number(market.get("mc_rmb"), "mc_rmb")
    v_final = _number(entries.get("valuation.v_final", {}).get("value"), "valuation.v_final")
    required = _number(entries.get("return.required", {}).get("value"), "return.required")
    decay = _number(entries.get("moat.decay", {}).get("value"), "moat.decay")
    dps_native = _number((factor4.get("dividend_identity") or {}).get("dps_native"), "dps_native")
    dividend_yield = _number((factor4.get("dividend_identity") or {}).get("yield_pretax_pct"), "yield_pretax_pct")
    growth_pct = float((candidate_bundle.get("params") or {}).get("g_base") or factor3.get("g_adj") or 0)
    if growth_pct < 0:
        raise ValueError("market_decision_input_invalid:growth_pct")
    v_final_rmb = v_final * shares * fx
    growth_yield = growth_pct / 100.0 * v_final_rmb / mc_rmb * 100.0
    total_return = dividend_yield + growth_yield
    price_margin = (v_final - price) / v_final * 100.0
    return_margin = total_return - required - decay
    combined_hurdle = (required + decay) / 100.0
    if combined_hurdle <= 0:
        raise ValueError("market_decision_input_invalid:combined_hurdle")
    # D/P + g*V/P >= r*+decay; V is the canonical per-share value.
    combined_buy_price = (dps_native + (growth_pct / 100.0) * v_final) / combined_hurdle
    market_as_of = str(snapshot.get("as_of") or "")
    financial_as_of = str(entries.get("return.gg.base", {}).get("as_of") or "")
    return_as_of = f"{financial_as_of} / market {market_as_of}" if financial_as_of else market_as_of
    _update_entry(entries, "market.price.current", value=round(price, 4), as_of=market_as_of,
                  basis=f"Niangao read-only quote ({snapshot.get('source')})",
                  source_ids=["market_snapshot.json"],
                  rationale="当前动作与所有市值分母统一使用该年糕快照；不得复用年报期末价。")
    _update_entry(entries, "return.gg.base", value=(factor3.get("gg") or {}).get("base"), as_of=return_as_of,
                  basis="compute_bundle.market_candidate AA口径；分母使用年糕快照市值",
                  source_ids=["compute_bundle.market_candidate.json"],
                  rationale="AA口径保守穿透回报，随当前市值确定性重算。")
    _update_entry(entries, "return.gg.fcfe", value=(factor3.get("gg_fcfe") or {}).get("base"), as_of=return_as_of,
                  basis="compute_bundle.market_candidate FCFE口径；分母使用年糕快照市值",
                  source_ids=["compute_bundle.market_candidate.json"],
                  rationale="FCFE交叉口径，随当前市值确定性重算。")
    _update_entry(entries, "return.gg.normalized", value=(factor3.get("gg_normalized") or {}).get("base"), as_of=return_as_of,
                  basis="compute_bundle.market_candidate Normalized口径；分母使用年糕快照市值",
                  source_ids=["compute_bundle.market_candidate.json"],
                  rationale="正常化AA口径，随当前市值确定性重算。")
    _update_entry(entries, "margin.price", value=round(price_margin, 1), as_of=market_as_of,
                  basis="(V_final−Niangao current price)/V_final",
                  source_ids=["decision_ledger.json:D006", "market_snapshot.json"])
    _update_entry(entries, "margin.return", value=round(return_margin, 1), as_of=market_as_of,
                  basis=(f"R_total({total_return:.2f}%)−r*({required:g}%)−decay({decay:g}%); "
                         "R_total=dividend yield+g×V_final/market cap"),
                  source_ids=["compute_bundle.market_candidate.json", "decision_ledger.json:D006"])
    _update_entry(entries, "trigger.buy", value=round(combined_buy_price, 2), as_of=market_as_of,
                  basis="D/P + g×V_final/P ≥ r*+decay 的综合回报买点",
                  source_ids=["compute_bundle.market_candidate.json", "decision_ledger.json:D006", "decision_ledger.json:D008", "decision_ledger.json:D009"],
                  rationale="只有价格使回报安全边际非负、综合回报达到r*+decay时才允许首次买入。")
    position = entries.get("decision.position.recommended")
    if position is not None:
        _update_entry(entries, "decision.position.recommended", value=position.get("value"), as_of=market_as_of,
                      basis="仅限既有持仓的观察仓；未持有者在综合回报买点以上保持0%",
                      source_ids=["decision_manifest.json", "market_snapshot.json"],
                      rationale="Hold状态且当前价高于综合买点时，1.5%只描述已持有者上限，不授权新建仓。")
    candidate["entries"] = list(candidate.get("entries") or [])
    selected, selection_findings = select_canonical_entries(candidate)
    action_findings = selection_findings + _action_consistency(selected, manifest)
    validation = validate_decision_ledger(candidate, manifest=manifest, enforced=True)
    invalid = list(validation.get("invalid_findings") or []) + action_findings
    if invalid:
        raise ValueError("market_decision_candidate_invalid:" + "|".join(dict.fromkeys(invalid)))
    derivation = {
        "price": price, "market_cap_rmb_m": mc_rmb, "v_final_native": v_final,
        "dividend_yield_pct": dividend_yield, "growth_yield_pct": round(growth_yield, 4),
        "total_return_pct": round(total_return, 4), "required_return_pct": required,
        "decay_pct": decay, "price_margin_pct": round(price_margin, 4),
        "return_margin_pct": round(return_margin, 4),
        "combined_buy_price_native": round(combined_buy_price, 4),
        "combined_buy_formula": "(DPS_native + g×V_final_native) / (r* + decay)",
    }
    return candidate, derivation


def build_market_chapter_frontier(output: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    selected, selection_findings = select_canonical_entries(candidate)
    free_values = _scan_free_critical_values(output, selected, candidate) if not selection_findings else []
    chapter_dir = output / "chapters" if (output / "chapters").is_dir() else output
    reference_findings: dict[str, list[str]] = {}
    for chapter in range(15):
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        validation = validate_chapter_decision_references(
            candidate, chapter_text=path.read_text(encoding="utf-8"),
            chapter=chapter, enforced=True,
        )
        findings = list(validation.get("invalid_findings") or [])
        if findings:
            reference_findings[str(chapter)] = findings
    affected = sorted({int(key) for key in reference_findings} | {
        int(item.split(":", 2)[1][2:]) for item in free_values
        if item.startswith("free_critical_value:Ch")
    })
    return {
        "schema_version": "market-refresh-chapter-frontier.v1",
        "state": "REPAIR_REQUIRED" if free_values or reference_findings else "READY",
        "selection_findings": selection_findings,
        "affected_chapters": affected,
        "free_critical_values": free_values,
        "decision_reference_findings": reference_findings,
        "repair_scope": "changed_market_metrics_only",
        "structured_ledger_changes_forbidden_during_chapter_repair": True,
    }


def build_market_refresh(
    output_dir: str | os.PathLike[str], ts_code: str, *,
    db_path: str | os.PathLike[str] = DEFAULT_DB_PATH, max_age_minutes: int = 60,
    persist: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir)
    current_bundle_path = output / "compute_bundle.json"
    ledger_path = output / "decision_ledger.json"
    current = _load(current_bundle_path)
    ledger = _load(ledger_path)
    if not current:
        return {"schema_version": SCHEMA_VERSION, "state": "INVALID", "invalid_findings": ["compute_bundle_missing"]}
    if not ledger:
        return {"schema_version": SCHEMA_VERSION, "state": "INVALID", "invalid_findings": ["decision_ledger_missing"]}
    try:
        snapshot = write_snapshot(output, ts_code, db_path=db_path, max_age_minutes=max_age_minutes)
    except ValueError as exc:
        result = {"schema_version": SCHEMA_VERSION, "state": "INVALID", "invalid_findings": [str(exc)]}
        if persist:
            (output / "market_refresh_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    params = _recompute_params(output, current)
    contract = _load(output / "analysis_contract.json")
    shares = current.get("market", {}).get("shares_m")
    candidate = compute_from_db(
        ts_code, params, price_hkd=float(snapshot["price"]), force=True,
        contract=contract, zone_j_params=params,
        price_source_code=str(current.get("market", {}).get("pricing_code") or ""),
    )
    if candidate.get("error"):
        result = {"schema_version": SCHEMA_VERSION, "state": "INVALID", "invalid_findings": [f"compute_candidate:{candidate['error']}"]}
        if persist:
            (output / "market_refresh_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    candidate_market = candidate.setdefault("market", {})
    candidate_market.update({
        "price_source": f"niangao:{snapshot['source']}",
        "price_fetched_at": snapshot["fetched_at"],
        "price_as_of": snapshot["as_of"],
        "market_snapshot_hash": snapshot["snapshot_hash"],
    })
    selected = _active_by_metric(ledger)
    proposed_values = {
        "market.price.current": float(snapshot["price"]),
        "return.gg.base": candidate.get("factor3", {}).get("gg", {}).get("base"),
        "return.gg.fcfe": candidate.get("factor3", {}).get("gg_fcfe", {}).get("base"),
        "return.gg.normalized": candidate.get("factor3", {}).get("gg_normalized", {}).get("base"),
    }
    deterministic_changes = []
    for metric_id in DETERMINISTIC_METRICS:
        prior = selected.get(metric_id) or {}
        deterministic_changes.append({
            "metric_id": metric_id,
            "entry_id": prior.get("entry_id"),
            "old_value": prior.get("value"),
            "new_value": proposed_values.get(metric_id),
            "old_as_of": prior.get("as_of"),
            "new_as_of": snapshot["as_of"] if metric_id == "market.price.current" else prior.get("as_of"),
            "changed": prior.get("value") != proposed_values.get(metric_id) or (
                metric_id == "market.price.current" and prior.get("as_of") != snapshot["as_of"]
            ),
        })
    has_changes = any(item["changed"] for item in deterministic_changes)
    price_value_changed = next(
        (item["old_value"] != item["new_value"] for item in deterministic_changes
         if item["metric_id"] == "market.price.current"),
        False,
    )
    return_metric_changed = any(
        item["changed"] for item in deterministic_changes
        if item["metric_id"] != "market.price.current"
    )
    judgment_required = price_value_changed or return_metric_changed
    incomplete_frontier = list(JUDGMENT_FRONTIER) if judgment_required else (
        ["market.price.current"] if has_changes else []
    )
    decision_candidate = None
    decision_candidate_diff = None
    decision_derivation = None
    if judgment_required:
        try:
            decision_candidate, decision_derivation = build_market_decision_candidate(
                ledger, candidate, snapshot, manifest=_load(output / "decision_manifest.json"),
            )
            decision_candidate_diff = decision_diff(
                ledger, decision_candidate, change_reason=str(decision_candidate.get("change_reason") or ""),
            )
        except ValueError as exc:
            result = {"schema_version": SCHEMA_VERSION, "state": "INVALID", "invalid_findings": [str(exc)]}
            if persist:
                (output / "market_refresh_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
    result = {
        "schema_version": SCHEMA_VERSION,
        "state": "RECOMPUTE_REQUIRED" if has_changes else "CURRENT",
        "promotion_allowed": False,
        "report_id": ledger.get("report_id"),
        "snapshot_hash": snapshot["snapshot_hash"],
        "baseline": {
            "compute_bundle_sha256": _hash_file(current_bundle_path),
            "decision_ledger_sha256": _hash_file(ledger_path),
        },
        "deterministic_changes": deterministic_changes,
        "decision_derivation": decision_derivation,
        "decision_candidate_fingerprint": ledger_fingerprint(decision_candidate) if decision_candidate else None,
        "decision_diff_changes_action": bool((decision_candidate_diff or {}).get("changes_action")),
        "judgment_frontier": incomplete_frontier,
        "required_next_step": (
            "rebuild_decision_ledger_and_compiled_chapters_then_review_action_diff"
            if judgment_required else (
                "refresh_market_identity_and_recompile_protected_chapters" if has_changes else "none"
            )
        ),
        "invariants": [
            "canonical_ledger_not_mutated", "report_chapters_not_mutated",
            "current_quote_never_used_in_point_in_time_backtest",
        ],
    }
    approval_preview = None
    chapter_frontier = None
    if decision_candidate is not None and decision_candidate_diff is not None:
        chapter_frontier = build_market_chapter_frontier(output, decision_candidate)
        approval_basis = {
            "report_id": ledger.get("report_id"),
            "baseline_ledger_sha256": result["baseline"]["decision_ledger_sha256"],
            "candidate_ledger_fingerprint": result["decision_candidate_fingerprint"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "changed_entries": [
                {
                    "entry_id": item.get("entry_id"), "metric_id": item.get("metric_id"),
                    "before": (item.get("before") or {}).get("value"),
                    "after": (item.get("after") or {}).get("value"),
                }
                for item in decision_candidate_diff.get("changes") or []
            ],
        }
        approval_preview = {
            "schema_version": "market-refresh-approval-preview.v1",
            "status": "AWAITING_OPERATOR",
            "approval_fingerprint": _hash_payload(approval_basis),
            "approval_basis": approval_basis,
            "decision_effect": {
                "unified_decision": (decision_candidate.get("decision") or {}).get("unified_decision"),
                "current_price": float(snapshot["price"]),
                "combined_buy_price": round(float(decision_derivation["combined_buy_price_native"]), 2),
                "return_margin_pct": round(float(decision_derivation["return_margin_pct"]), 1),
                "position_scope": "existing_holders_only_above_combined_buy_price",
            },
            "automatic_approval_forbidden": True,
            "post_approval_requirements": [
                "promote_candidate_ledger_with_exact_fingerprint",
                "separate_P_DDM_from_canonical_combined_buy_price_in_prose",
                "recompile_protected_chapters",
                "pass_completion_and_generate_new_validation_only_variant",
            ],
        }
        result["approval_preview_fingerprint"] = approval_preview["approval_fingerprint"]
        result["chapter_frontier_state"] = chapter_frontier["state"]
        result["chapter_frontier_chapters"] = chapter_frontier["affected_chapters"]
    if persist:
        candidate_path = output / "compute_bundle.market_candidate.json"
        candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "market_refresh_plan.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if decision_candidate is not None:
            (output / "decision_ledger.market_candidate.json").write_text(
                json.dumps(decision_candidate, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        if decision_candidate_diff is not None:
            decision_candidate_diff["status"] = "CANDIDATE"
            decision_candidate_diff["approval_status"] = "PENDING" if decision_candidate_diff.get("changes_action") else "NOT_REQUIRED"
            (output / "decision_market_refresh_diff.json").write_text(
                json.dumps(decision_candidate_diff, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        if approval_preview is not None:
            (output / "market_refresh_approval_preview.json").write_text(
                json.dumps(approval_preview, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            approval_validation = validate_market_refresh_approval_preview(output)
            (output / "market_refresh_approval_validation.json").write_text(
                json.dumps(approval_validation, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        if chapter_frontier is not None:
            (output / "market_refresh_chapter_frontier.json").write_text(
                json.dumps(chapter_frontier, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        validation = {
            "schema_version": SCHEMA_VERSION,
            "state": result["state"],
            "promotion_allowed": False,
            "invalid_findings": [],
            "incomplete_findings": incomplete_frontier,
        }
        (output / "market_refresh_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def evaluate_output_market_refresh(output_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Expose the refresh frontier as a completion-contract gate when present."""
    output = Path(output_dir)
    validation = _load(output / "market_refresh_validation.json")
    if not validation:
        return {
            "schema_version": SCHEMA_VERSION, "state": "SKIP", "status": "SKIP",
            "invalid_findings": [], "incomplete_findings": [],
        }
    state = str(validation.get("state") or "INVALID")
    if state == "CURRENT":
        status = "PASS"
    elif state == "RECOMPUTE_REQUIRED":
        status = "INCOMPLETE"
    else:
        status = "FAIL"
        state = "INVALID"
    return {
        "schema_version": SCHEMA_VERSION,
        "state": state,
        "status": status,
        "invalid_findings": list(validation.get("invalid_findings") or []),
        "incomplete_findings": list(validation.get("incomplete_findings") or []),
        "promotion_allowed": bool(validation.get("promotion_allowed", False)),
    }


def validate_market_refresh_approval_preview(output_dir: str | os.PathLike[str]) -> dict[str, Any]:
    output = Path(output_dir)
    preview = _load(output / "market_refresh_approval_preview.json")
    candidate = _load(output / "decision_ledger.market_candidate.json")
    diff = _load(output / "decision_market_refresh_diff.json")
    snapshot = _load(output / "market_snapshot.json")
    invalid: list[str] = []
    if preview.get("schema_version") != "market-refresh-approval-preview.v1":
        invalid.append("approval_preview_schema_invalid")
    basis = preview.get("approval_basis") if isinstance(preview.get("approval_basis"), dict) else {}
    if basis.get("baseline_ledger_sha256") != _hash_file(output / "decision_ledger.json"):
        invalid.append("baseline_ledger_changed_since_preview")
    if basis.get("candidate_ledger_fingerprint") != ledger_fingerprint(candidate):
        invalid.append("candidate_ledger_fingerprint_mismatch")
    if basis.get("snapshot_hash") != snapshot.get("snapshot_hash"):
        invalid.append("market_snapshot_changed_since_preview")
    expected_changes = [
        {
            "entry_id": item.get("entry_id"), "metric_id": item.get("metric_id"),
            "before": (item.get("before") or {}).get("value"),
            "after": (item.get("after") or {}).get("value"),
        }
        for item in diff.get("changes") or []
    ]
    if basis.get("changed_entries") != expected_changes:
        invalid.append("approval_diff_changed_since_preview")
    if preview.get("approval_fingerprint") != _hash_payload(basis):
        invalid.append("approval_preview_fingerprint_mismatch")
    if not diff.get("changes_action") or diff.get("approval_status") != "PENDING":
        invalid.append("action_diff_not_pending")
    return {
        "schema_version": "market-refresh-approval-validation.v1",
        "state": "INVALID" if invalid else "READY_FOR_APPROVAL",
        "status": "FAIL" if invalid else "PASS",
        "invalid_findings": invalid,
        "approval_fingerprint": preview.get("approval_fingerprint"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Niangao-backed Turtle market refresh candidate")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--code", required=True)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--max-age-minutes", type=int, default=60)
    args = parser.parse_args()
    result = build_market_refresh(
        args.output_dir, args.code, db_path=args.db, max_age_minutes=args.max_age_minutes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("state") != "INVALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
