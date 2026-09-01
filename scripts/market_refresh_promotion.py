#!/usr/bin/env python3
"""Promote an explicitly approved market refresh and propagate bounded prose changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.decision_compiler import approve_decision_diff, evaluate_output_decision_compiler
    from scripts.decision_ledger import ledger_fingerprint, persist_decision_ledger
    from scripts.market_refresh import validate_market_refresh_approval_preview
except ModuleNotFoundError:
    from decision_compiler import approve_decision_diff, evaluate_output_decision_compiler
    from decision_ledger import ledger_fingerprint, persist_decision_ledger
    from market_refresh import validate_market_refresh_approval_preview


SCHEMA_VERSION = "market-refresh-promotion.v1"
_REF_RE = re.compile(r"\[decision:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I)
_BLOCK_BEGIN = re.compile(r"TURTLE:DECISION_BLOCK:Ch\d+:BEGIN")
_BLOCK_END = re.compile(r"TURTLE:DECISION_BLOCK:Ch\d+:END")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _number_forms(value: Any) -> list[str]:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return [str(value)]
    number = float(value)
    forms = {f"{number:g}", f"{number:.1f}", f"{number:.2f}"}
    if number < 0:
        forms |= {item.replace("-", "−") for item in forms}
    return sorted(forms, key=len, reverse=True)


def _replace_number(line: str, old: Any, new: Any, *, decimals: int | None = None) -> str:
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
        return line.replace(str(old), str(new))
    rendered = f"{float(new):.{decimals}f}" if decimals is not None else f"{float(new):g}"
    for form in _number_forms(old):
        protected: dict[str, str] = {}
        for index, match in enumerate(re.finditer(rf"\bStep\s+{re.escape(form)}\b", line, re.I)):
            token = f"__TURTLE_STEP_{index}__"
            protected[token] = match.group(0)
            line = line.replace(match.group(0), token, 1)
        line = re.sub(rf"(?<![0-9.]){re.escape(form)}(?![0-9.])", rendered, line)
        for token, value in protected.items():
            line = line.replace(token, value)
    return line


def _entry_value(ledger: dict[str, Any], entry_id: str) -> Any:
    for item in ledger.get("entries") or []:
        if isinstance(item, dict) and item.get("entry_id") == entry_id:
            return item.get("value")
    return None


def _at(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _replace_contextual_market_values(
    line: str, *, old_ledger: dict[str, Any], new_ledger: dict[str, Any],
    old_bundle: dict[str, Any], new_bundle: dict[str, Any],
) -> str:
    """Replace a value only when its metric identity is visible on the same line."""
    ledger_rules = [
        (r"当前|现价|当前股价|当前价格|P_current|get_market_data|price_hkd|market\.price\.current|价格MOS|价格安全边际|margin\.price", "D001", 2),
        (r"\bGG\b|GG\(AA|GG=|gg_base|return\.gg\.base|穿透回报", "D002", None),
        (r"FCFE|return\.gg\.fcfe", "D003", None),
        (r"Normalized|normalized|return\.gg\.normalized", "D004", None),
        (r"价格MOS|价格安全边际|margin\.price", "D010", None),
        (r"回报safety|回报安全边际|return_margin|margin\.return", "D011", None),
        (r"trigger\.buy|首次买入条件|首次买入价|买入触发价", "D013", 2),
    ]
    for signal, entry_id, decimals in ledger_rules:
        if re.search(signal, line, re.I):
            line = _replace_number(
                line, _entry_value(old_ledger, entry_id), _entry_value(new_ledger, entry_id),
                decimals=decimals,
            )

    bundle_rules = [
        (r"股息率|股息\)|yield_pretax|R_total|总回报|综合回报", "factor4.dps_yield_pretax", None),
        (r"税后|yield_after_tax", "factor4.dps_yield_after_tax", None),
        (r"净现金/市值|净现金.*市值|净现金保护|net_cash_pct_mc", "factor3.net_cash_pct_mc", None),
        (r"gg_discounted|治理折价.*GG|折价后", "factor3.gg_discounted.base", None),
        (r"当前PE|current_pe|\bPE[=仅]?", "factor4.current_pe", None),
        (r"P_FCFE", "factor4.p_base.p_fcfe.price_native", 2),
        (r"止损|hard_native|hard_hkd", "factor4.stop_loss.hard_native", 2),
        (r"R\(NP\)_penetration|r_np_penetration", "factor2.r_np_penetration", None),
        (r"R\(NP\)_raw|r_np\b", "factor2.r_np", None),
        (r"R\(OE\)_penetration|R\(OE\).*M|r_oe_penetration", "factor2.r_oe_penetration", None),
        (r"R\(OE\)_raw|r_oe\b", "factor2.r_oe", None),
    ]
    for signal, path, decimals in bundle_rules:
        if re.search(signal, line, re.I):
            line = _replace_number(
                line, _at(old_bundle, path), _at(new_bundle, path), decimals=decimals,
            )

    old_total_parts = [_entry_value(old_ledger, key) for key in ("D008", "D009", "D011")]
    new_total_parts = [_entry_value(new_ledger, key) for key in ("D008", "D009", "D011")]
    if (
        all(isinstance(value, (int, float)) for value in old_total_parts + new_total_parts)
        and re.search(r"R_total|总回报|综合回报|回报safety|回报安全边际", line, re.I)
    ):
        old_total = sum(float(value) for value in old_total_parts)
        new_total = sum(float(value) for value in new_total_parts)
        line = _replace_number(line, old_total, new_total)
    old_excess_parts = [_entry_value(old_ledger, key) for key in ("D002", "D005")]
    new_excess_parts = [_entry_value(new_ledger, key) for key in ("D002", "D005")]
    if (
        all(isinstance(value, (int, float)) for value in old_excess_parts + new_excess_parts)
        and re.search(r"超额仅|超额|缓冲", line)
    ):
        old_excess = float(old_excess_parts[0]) - float(old_excess_parts[1])
        new_excess = float(new_excess_parts[0]) - float(new_excess_parts[1])
        line = _replace_number(line, old_excess, new_excess)

    old_mc, new_mc = _at(old_bundle, "market.mc_rmb"), _at(new_bundle, "market.mc_rmb")
    if re.search(r"\bMC\b|市值", line, re.I) or any(
        form in line for form in _number_forms(old_mc)
    ):
        line = _replace_number(line, old_mc, new_mc, decimals=2)
        if isinstance(old_mc, (int, float)) and isinstance(new_mc, (int, float)):
            line = re.sub(
                rf"(?<![0-9]){round(float(old_mc))}M(?![0-9])",
                f"{round(float(new_mc))}M", line,
            )
            line = line.replace(f"{float(old_mc):.1f}", f"{float(new_mc):.1f}")

    new_hh = _at(new_bundle, "factor3.hh_deviation.deviation")
    if re.search(r"HH偏离|\bHH=|hh=|hh_note", line, re.I) and isinstance(new_hh, (int, float)):
        line = re.sub(r"(?<![0-9.])10\.4(?=\s*(?:pp|,|，|\)|$))", f"{float(new_hh):g}", line)
        line = re.sub(r"(?<=hh=)10\.4\b", f"{float(new_hh):g}", line, flags=re.I)
        line = line.replace("R(NP)_raw", "R(NP)_penetration")
        line = _replace_number(
            line, _at(new_bundle, "factor2.r_np"),
            _at(new_bundle, "factor2.r_np_penetration"),
        )
        hypothetical_hh_rule = bool(re.search(r"Step.*HH.*若|若\|R\(NP\)", line, re.I))
        if float(new_hh) <= 3 and not hypothetical_hh_rule:
            line = re.sub(
                rf"{re.escape(f'{float(new_hh):g}')}pp\s*>\s*3pp",
                f"{float(new_hh):g}pp≤3pp", line,
            )
            line = re.sub(
                r"因子2不适用(?:，|,)?(?:以[^。；|]*?(?:为准|回报率))?",
                "因子2通过同口径一致性检查，可与因子3交叉验证", line,
            )
            line = line.replace("因子3为唯一有效穿透回报率", "因子2与因子3均可作为穿透回报交叉验证")
            if "差异来源：R(NP)_penetration不含M和(1-Q)调整" in line:
                line = re.sub(
                    r"差异来源：R\(NP\)_penetration不含M和\(1-Q\)调整[^。]*。",
                    "HH采用与GG相同的M和(1-Q)穿透口径；差异只来自NP与AA。",
                    line,
                )
            line = re.sub(
                r'hh_note="[^"]*"',
                'hh_note="HH≤3pp，因子2与因子3可交叉验证"', line,
                flags=re.I,
            )

    old_rf, new_rf = _at(old_bundle, "params.Rf"), _at(new_bundle, "params.Rf")
    old_yield, new_yield = _at(old_bundle, "factor4.dps_yield_pretax"), _at(new_bundle, "factor4.dps_yield_pretax")
    if re.search(r"股息率.*Rf|Rf.*股息率", line, re.I) and all(
        isinstance(value, (int, float)) for value in (old_rf, new_rf, old_yield, new_yield)
    ):
        line = _replace_number(line, float(old_yield) - float(old_rf), float(new_yield) - float(new_rf))
    return line


def _separate_buy_thresholds(line: str, *, old_buy: float, new_buy: float) -> str:
    old_text = f"{old_buy:g}"
    new_text = f"{new_buy:.2f}"
    if "P*" not in line and old_text not in line and f"{old_buy:.2f}" not in line:
        return line
    theoretical = "P_DDM" in line or bool(re.search(r"DPS|DDM|g\s*=|10%年化|满足10%|门槛价法|公式|~\s*[0-9.]+%", line, re.I))
    operational = "P_DDM" not in line and bool(re.search(r"首次买入|主买价|才买|等回落|越跌越加|加仓|触发买入|什么价格买|建议仓位", line))
    if theoretical and not operational:
        line = line.replace("P*", "P_DDM")
        if "不含decay" not in line and not line.lstrip().startswith("|"):
            line += " P_DDM仅检验10% DDM回报，不含decay，不能作为canonical首次买入线。"
        return line
    if operational:
        line = line.replace("P*", "P_buy")
        line = _replace_number(line, old_buy, new_buy, decimals=2)
        if "P_buy" in line and not re.search(
            rf"P_buy\s*(?:=|\()\s*{re.escape(new_text)}", line,
        ):
            line = line.replace("P_buy", f"P_buy={new_text}", 1)
        if "[decision: D013]" not in line:
            line += " [decision: D013]"
        line = re.sub(r"保守P_buy\s*=\s*([0-9.]+\s*HKD)（零增长）", r"零增长P_DDM=\1（理论参考）", line)
        line = line.replace("未达10%门槛", "未达综合回报门槛")
        line = line.replace("（g=2%口径）", "（r*+decay综合回报口径）")
    return line


def propagate_market_refresh_chapters(
    output: Path, old_ledger: dict[str, Any], new_ledger: dict[str, Any], *, chapters: list[int],
    old_bundle: dict[str, Any] | None = None, new_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    old_by_id = {str(item.get("entry_id")): item for item in old_ledger.get("entries") or [] if isinstance(item, dict)}
    new_by_id = {str(item.get("entry_id")): item for item in new_ledger.get("entries") or [] if isinstance(item, dict)}
    old_buy = float(old_by_id["D013"]["value"])
    new_buy = float(new_by_id["D013"]["value"])
    chapter_dir = output / "chapters" if (output / "chapters").is_dir() else output
    changes: list[dict[str, Any]] = []
    for chapter in chapters:
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        rewritten: list[str] = []
        inside_block = False
        inside_gg_scenarios = False
        for line_number, line in enumerate(original.splitlines(), 1):
            before = line
            if _BLOCK_BEGIN.search(line):
                inside_block = True
            if not inside_block:
                if re.search(r"三档情景|GG.*情景", line):
                    inside_gg_scenarios = True
                elif inside_gg_scenarios and line.startswith("### "):
                    inside_gg_scenarios = False
                # Separate the old DDM hurdle from the canonical action before
                # generic D-id value replacement erases the old threshold cue.
                line = _separate_buy_thresholds(line, old_buy=old_buy, new_buy=new_buy)
                line = _replace_contextual_market_values(
                    line, old_ledger=old_ledger, new_ledger=new_ledger,
                    old_bundle=old_bundle or {}, new_bundle=new_bundle or {},
                )
                if inside_gg_scenarios:
                    scenario_paths = {
                        "基准": "factor3.gg.base", "悲观": "factor3.gg.pessimistic",
                        "乐观": "factor3.gg.optimistic",
                    }
                    for label, metric_path in scenario_paths.items():
                        if label in line:
                            line = _replace_number(
                                line, _at(old_bundle or {}, metric_path), _at(new_bundle or {}, metric_path),
                            )
                if " / " in line and "694.66" in line and ("96.92" in line or "44.02" in line):
                    line = _replace_number(
                        line, _entry_value(old_ledger, "D002"), _entry_value(new_ledger, "D002"),
                    )
                if re.search(r"未持有者.*观察仓|未持有者.*1[–-]2%", line):
                    line = re.sub(
                        r"未持有者[^。；]*", 
                        f"未持有者在P_buy={new_buy:.2f} HKD以上保持0%，达到买点后再按新决策建仓",
                        line,
                    )
                if "仓位建议：观察仓1.5%" in line:
                    line = line.replace(
                        "仓位建议：观察仓1.5%",
                        f"仓位建议：既有持仓维持1.5%；未持有者在P_buy={new_buy:.2f} HKD以上保持0%",
                    )
                if "P_DDM" in line and "买入触发器" in line:
                    line = line.replace(
                        "它只有在基本面未恶化时才是买入触发器",
                        "它仅用于检验不含decay的理论回报，不是买入触发器",
                    )
                if "stop_loss" in line:
                    line = line.replace("零增长压力价", "市价联动重估线")
                    line = line.replace("零增长DDM压力价", "市价联动重估线")
                table_price = re.match(r"^\s*\|\s*\**([0-9]+(?:\.[0-9]+)?)\s*HKD", line, re.I)
                if table_price and "可买" in line and not math.isclose(
                    float(table_price.group(1)), new_buy, rel_tol=1e-6, abs_tol=0.011,
                ):
                    line = line.replace("可买", f"估值参考；未达P_buy={new_buy:.2f}不买")
                line = line.replace("get_market_data", "market_snapshot.json")
                if "P*" in line and re.search(r"观察仓|仓位", line):
                    line = line.replace("P*", "P_buy")
                    line = _replace_number(line, old_buy, new_buy, decimals=2)
                    line = re.sub(r"观察仓1[–-]2%", "既有持仓1.5%；未持有者0%", line)
            if _BLOCK_END.search(line):
                inside_block = False
            rewritten.append(line)
            if line != before:
                changes.append({"chapter": chapter, "line": line_number, "before": before, "after": line})
        new_text = "\n".join(rewritten) + ("\n" if original.endswith("\n") else "")
        if new_text != original:
            path.write_text(new_text, encoding="utf-8")
    return {"changed_lines": changes, "changed_chapters": sorted({item["chapter"] for item in changes})}


def promote_market_refresh(
    output_dir: str | os.PathLike[str], *, approval_fingerprint: str,
    approved_by: str, rationale: str,
) -> dict[str, Any]:
    output = Path(output_dir)
    validation = validate_market_refresh_approval_preview(output)
    if validation.get("state") != "READY_FOR_APPROVAL":
        return {"state": "BLOCKED", "error": "approval_preview_invalid", "validation": validation}
    if str(validation.get("approval_fingerprint")) != str(approval_fingerprint):
        return {"state": "BLOCKED", "error": "approval_fingerprint_mismatch"}
    old_ledger = _load(output / "decision_ledger.json")
    candidate = _load(output / "decision_ledger.market_candidate.json")
    candidate_bundle = _load(output / "compute_bundle.market_candidate.json")
    frontier = _load(output / "market_refresh_chapter_frontier.json")
    if not old_ledger or not candidate or not candidate_bundle:
        return {"state": "BLOCKED", "error": "promotion_artifact_missing"}
    # Search every chapter through semantic replacement rules.  A frontier
    # built only from canonical decision references can miss derived market
    # facts embedded in qualitative chapters (for example net-cash/market-cap).
    chapters = [chapter for chapter in range(15) if (
        (output / "chapters" / f"_ch{chapter:02d}.md").is_file()
        or (output / f"_ch{chapter:02d}.md").is_file()
    )]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = output / "history" / f"market_refresh_{stamp}_{approval_fingerprint[:12]}"
    archive.mkdir(parents=True, exist_ok=False)
    archive_names = [
        "decision_ledger.json", "decision_diff.json", "compute_bundle.json",
        "decision_compilation.json", "decision_compiler_validation.json",
        "completion_report.json", "market_refresh_validation.json",
    ]
    for name in archive_names:
        source = output / name
        if source.is_file():
            shutil.copy2(source, archive / name)
    archived_chapters = archive / "chapters"
    archived_chapters.mkdir()
    chapter_dir = output / "chapters" if (output / "chapters").is_dir() else output
    for chapter in chapters:
        source = chapter_dir / f"_ch{chapter:02d}.md"
        if source.is_file():
            shutil.copy2(source, archived_chapters / source.name)

    promoted = deepcopy(candidate)
    promoted["lifecycle"] = "decision_ready"
    promoted["freeze"] = {"frozen": True, "fingerprint": "", "frozen_at": _now()}
    promoted["freeze"]["fingerprint"] = ledger_fingerprint(promoted)
    ledger_result = persist_decision_ledger(
        output, promoted, report_text="", allow_frozen_update=True,
    )
    if not ledger_result.get("written"):
        return {"state": "BLOCKED", "error": "ledger_promotion_failed", "detail": ledger_result, "archive": str(archive)}
    bundle_tmp = output / "compute_bundle.json.market-refresh.tmp"
    bundle_tmp.write_text(json.dumps(candidate_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(bundle_tmp, output / "compute_bundle.json")
    approval = approve_decision_diff(
        output, approved_by=approved_by, rationale=rationale,
        evidence_ids=[
            "market_snapshot.json", "compute_bundle.market_candidate.json",
            "market_refresh_approval_preview.json:" + approval_fingerprint,
        ],
    )
    if not approval.get("written"):
        return {"state": "BLOCKED", "error": "decision_diff_approval_failed", "detail": approval, "archive": str(archive)}
    old_bundle = _load(archive / "compute_bundle.json")
    propagation = propagate_market_refresh_chapters(
        output, old_ledger, promoted, chapters=chapters,
        old_bundle=old_bundle, new_bundle=candidate_bundle,
    )
    record = {
        "schema_version": SCHEMA_VERSION, "state": "PROMOTED_PENDING_VALIDATION",
        "approved_by": approved_by, "approved_at": _now(), "rationale": rationale,
        "approval_fingerprint": approval_fingerprint,
        "baseline_ledger_sha256": _sha(archive / "decision_ledger.json"),
        "promoted_ledger_fingerprint": ledger_fingerprint(promoted),
        "archive_dir": str(archive), "affected_chapters": chapters,
        "propagation": propagation,
    }
    (output / "market_refresh_promotion.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "market_refresh_validation.json").write_text(json.dumps({
        "schema_version": "turtle-market-refresh.v1", "state": "REPAIR_REQUIRED",
        "promotion_allowed": False, "invalid_findings": [],
        "incomplete_findings": ["chapter_propagation_validation_pending"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def finalize_market_refresh(output_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Mark a promoted refresh current only after all deterministic identities agree."""
    output = Path(output_dir)
    promotion = _load(output / "market_refresh_promotion.json")
    snapshot = _load(output / "market_snapshot.json")
    bundle = _load(output / "compute_bundle.json")
    ledger = _load(output / "decision_ledger.json")
    diff = _load(output / "decision_diff.json")
    compiler = evaluate_output_decision_compiler(output, persist=True)
    findings: list[str] = []
    if promotion.get("state") not in {"PROMOTED_PENDING_VALIDATION", "PROMOTED_VALIDATED"}:
        findings.append("promotion_not_pending_validation")
    if compiler.get("state") != "DECISION_READY":
        findings.append("decision_compiler_not_ready")
    if diff.get("approval_status") != "APPROVED":
        findings.append("decision_diff_not_approved")
    structured = _load(output / "market_refresh_structured_validation.json")
    if (output / "decisive_question_policy.json").is_file() and structured.get("state") != "REFRESHED":
        findings.append("structured_dependencies_not_refreshed")
    validation_requirements = {
        "claim_evidence_validation.json": {"DECISION_READY", "REVIEWABLE", "MONITORING"},
        "decisive_question_findings_validation.json": {"DECISION_READY"},
        "valuation_model_validation.json": {"DECISION_READY", "REVIEWABLE", "MONITORING"},
        "thesis_test_validation.json": {"DECISION_READY", "REVIEWABLE", "MONITORING"},
        "insight_validation.json": {"DECISION_READY", "REVIEWABLE", "MONITORING"},
    }
    for name, ready_states in validation_requirements.items():
        path = output / name
        if path.is_file() and _load(path).get("state") not in ready_states:
            findings.append("structured_validation_not_ready:" + name)
    if _at(bundle, "market.market_snapshot_hash") != snapshot.get("snapshot_hash"):
        findings.append("compute_bundle_snapshot_hash_mismatch")
    market_price = _entry_value(ledger, "D001")
    if not isinstance(market_price, (int, float)) or not math.isclose(
        float(market_price), float(snapshot.get("price") or 0), rel_tol=1e-9, abs_tol=1e-9,
    ):
        findings.append("decision_ledger_market_price_mismatch")
    state = "CURRENT" if not findings else "INVALID"
    result = {
        "schema_version": "turtle-market-refresh.v1", "state": state,
        "status": "PASS" if state == "CURRENT" else "FAIL",
        "promotion_allowed": False, "invalid_findings": findings,
        "incomplete_findings": [], "approval_fingerprint": promotion.get("approval_fingerprint"),
        "market_snapshot_hash": snapshot.get("snapshot_hash"),
        "decision_ledger_fingerprint": ledger_fingerprint(ledger) if ledger else "",
        "finalized_at": _now(),
    }
    (output / "market_refresh_validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    if state == "CURRENT":
        promotion["state"] = "PROMOTED_VALIDATED"
        promotion["validated_at"] = result["finalized_at"]
        (output / "market_refresh_promotion.json").write_text(
            json.dumps(promotion, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote an approved market refresh")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--approval-fingerprint", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--rationale", required=True)
    args = parser.parse_args()
    result = promote_market_refresh(
        args.output_dir, approval_fingerprint=args.approval_fingerprint,
        approved_by=args.approved_by, rationale=args.rationale,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result.get("state")).startswith("PROMOTED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
