#!/usr/bin/env python3
"""Turtle V12 统一入口 — 一键全流程。

V12: 单 Agent + 工具循环，Dayu 定性 + Turtle 定量在同一个 Agent Loop 内完成。
V11 兼容模式: --template report_template_v10.md 恢复原有行为。

Usage::
    # V12 统一模式（Dayu 定性 + Turtle 定量 → 15章报告）
    python -m turtle_agent.run --code 06668.HK --unified

    # V11 兼容模式（仅定量）
    python -m turtle_agent.run --code 06668.HK

    # 仅定性分析
    python -m turtle_agent.run --code 06668.HK --qualitative-only

    # 干跑
    python -m turtle_agent.run --code 06668.HK --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

# 确保 scripts/ 可导入
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_FRAMEWORK_DIR = os.path.normpath(os.path.join(_scripts_dir, ".."))
if _FRAMEWORK_DIR not in sys.path:
    # Direct execution has ``scripts/turtle_agent`` as sys.path[0].  Add the
    # repository root as well so ``scripts.*`` imports used by bound PIT tools
    # resolve exactly as they do under ``python -m``.
    sys.path.insert(0, _FRAMEWORK_DIR)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
_OUTPUT_DIR = os.path.join(_FRAMEWORK_DIR, "output")
_PIT_FRAMEWORK_ROOT = Path(_FRAMEWORK_DIR) / "config" / "phase10_pit_framework"



try:
    from turtle_agent._version import REPORT_VERSION, REPORTS_SUBDIR
except ImportError:
    REPORT_VERSION = "v13"
    REPORTS_SUBDIR  = "reports"

_VALID_TRACKING_REPORT_TYPES = {"annual", "q1", "h1", "q3"}
_PREDECESSOR_READY_STATES = {"REVIEWABLE", "DECISION_READY", "MONITORING"}
_REPORT_TYPE_LABELS = {
    "annual": "年报",
    "q1": "一季报",
    "h1": "中报",
    "q3": "三季报",
}


def _load_json_file(path: str) -> dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _refresh_report_learning_admissions(output_dir: str) -> dict[str, Any]:
    """Project cutoff-safe control-plane learning into the report contract."""
    try:
        from scripts.judgment_learning_admission import (
            refresh_analysis_contract_learning_admissions,
        )
    except ModuleNotFoundError:
        from judgment_learning_admission import (
            refresh_analysis_contract_learning_admissions,
        )
    return refresh_analysis_contract_learning_admissions(output_dir)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _investment_predecessor_findings(
    predecessor: dict[str, Any], *, company_code: str, cutoff_at: str,
    analysis_contract: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic reasons a frozen CJO cannot precede investment."""
    findings: list[str] = []
    identity = predecessor.get("identity") if isinstance(predecessor.get("identity"), dict) else {}
    source = predecessor.get("source") if isinstance(predecessor.get("source"), dict) else {}
    contract = source.get("g1j_contract") if isinstance(source.get("g1j_contract"), dict) else {}
    selection = (
        predecessor.get("selection_admission")
        if isinstance(predecessor.get("selection_admission"), dict) else {}
    )
    bridge = (
        predecessor.get("financial_driver_bridge")
        if isinstance(predecessor.get("financial_driver_bridge"), dict) else {}
    )
    forward_judgments = [
        item for item in predecessor.get("forward_judgments") or []
        if isinstance(item, dict) and item.get("judgment_id")
    ]
    mechanism_chains = [
        item for item in predecessor.get("mechanism_chains") or []
        if isinstance(item, dict) and item.get("chain_id")
    ]
    rival_pairs = [
        item for item in predecessor.get("rival_hypothesis_pairs") or []
        if isinstance(item, dict) and item.get("pair_id")
    ]
    analogy_cards = [
        item for item in predecessor.get("analogy_transfer_cards") or []
        if isinstance(item, dict) and item.get("card_id")
    ]
    if predecessor.get("schema_version") != "company-judgment-predecessor.v2":
        findings.append("company_judgment_predecessor_schema_invalid")
    if identity.get("status") != "G1J_COMPLETE" or identity.get("missing_components"):
        findings.append("company_judgment_predecessor_not_g1j_complete")
    if str(source.get("report_id") or "") != str(company_code):
        findings.append("company_judgment_predecessor_company_mismatch")
    if str(source.get("data_as_of") or "")[:10] != str(cutoff_at or "")[:10]:
        findings.append("company_judgment_predecessor_cutoff_mismatch")
    expected_contract = {
        "thesis_policy_schema_version": "thesis-test-policy.v3",
        "financial_driver_bridge_policy_schema_version": "financial-driver-bridge-policy.v4",
        "thesis_validation_schema_version": "thesis-test-validation.v1",
        "financial_driver_bridge_validation_schema_version": "financial-driver-bridge.v1",
    }
    for field, expected in expected_contract.items():
        if contract.get(field) != expected:
            findings.append("company_judgment_predecessor_g1j_contract_invalid:" + field)
    if selection.get("status") != "SELECTION_ADMITTED":
        findings.append("company_judgment_predecessor_not_investment_ready_selection")
    if not isinstance(predecessor.get("central_path"), dict) or not predecessor.get("central_path"):
        findings.append("company_judgment_predecessor_investment_central_path_missing")
    if bridge.get("report_id") != company_code:
        findings.append("company_judgment_predecessor_financial_driver_bridge_company_mismatch")
    if str(bridge.get("as_of") or "")[:10] != str(cutoff_at or "")[:10]:
        findings.append("company_judgment_predecessor_financial_driver_bridge_cutoff_mismatch")
    if not forward_judgments:
        findings.append("company_judgment_predecessor_forward_judgments_missing")
    if not mechanism_chains:
        findings.append("company_judgment_predecessor_mechanism_chains_missing")
    if not rival_pairs:
        findings.append("company_judgment_predecessor_rival_hypothesis_pairs_missing")
    if not analogy_cards:
        findings.append("company_judgment_predecessor_analogy_transfer_cards_missing")
    if bridge.get("schema_version") != "financial-driver-bridge.v1":
        findings.append("company_judgment_predecessor_financial_driver_bridge_schema_invalid")
    if bridge.get("analysis_purpose") != "COMPANY_JUDGMENT_ONLY":
        findings.append("company_judgment_predecessor_financial_driver_bridge_purpose_invalid")
    bridge_validation = bridge.get("validation") if isinstance(bridge.get("validation"), dict) else {}
    if bridge_validation.get("state") not in _PREDECESSOR_READY_STATES:
        findings.append("company_judgment_predecessor_financial_driver_bridge_embedded_validation_invalid")
    for field in (
        "snapshot_fingerprint", "thesis_sha256", "thesis_freeze_fingerprint",
        "financial_driver_bridge_sha256",
    ):
        if not str(source.get(field) or ""):
            findings.append("company_judgment_predecessor_source_identity_missing:" + field)
    for field in (
        "thesis_validation_state", "financial_driver_bridge_validation_state",
        "financial_driver_bridge_embedded_validation_state",
    ):
        if source.get(field) not in _PREDECESSOR_READY_STATES:
            findings.append("company_judgment_predecessor_source_state_invalid:" + field)

    if analysis_contract is not None:
        marker = analysis_contract.get("company_judgment_predecessor")
        if not isinstance(marker, dict):
            findings.append("analysis_contract_company_judgment_predecessor_missing")
        else:
            expected_scalars = {
                "completeness_status": identity.get("status"),
                "missing_components": identity.get("missing_components") or [],
                "snapshot_fingerprint": source.get("snapshot_fingerprint"),
                "thesis_sha256": source.get("thesis_sha256"),
                "thesis_freeze_fingerprint": source.get("thesis_freeze_fingerprint"),
                "thesis_validation_state": source.get("thesis_validation_state"),
                "financial_driver_bridge_sha256": source.get("financial_driver_bridge_sha256"),
                "financial_driver_bridge_validation_state": source.get(
                    "financial_driver_bridge_validation_state"
                ),
                "financial_driver_bridge_embedded_validation_state": source.get(
                    "financial_driver_bridge_embedded_validation_state"
                ),
                "data_as_of": source.get("data_as_of"),
                "central_path_id": (predecessor.get("central_path") or {}).get("path_id"),
                "selection_admission_status": selection.get("status"),
                "forward_judgment_ids": [item["judgment_id"] for item in forward_judgments],
                "rival_hypothesis_pair_ids": sorted(str(item["pair_id"]) for item in rival_pairs),
                "analogy_transfer_card_ids": sorted(str(item["card_id"]) for item in analogy_cards),
            }
            for field, expected in expected_scalars.items():
                if marker.get(field) != expected:
                    findings.append(
                        "analysis_contract_company_judgment_predecessor_mismatch:" + field
                    )
    return list(dict.fromkeys(findings))


def _load_company_judgment_predecessor(
    snapshot_path: str, *, company_code: str, cutoff_at: str,
) -> dict[str, Any]:
    """Load one completed, same-cutoff CJO freeze for an investment PIT run.

    This is deliberately a predecessor rather than another evidence source:
    it establishes the operating path that valuation and price must build on.
    The predecessor itself was already frozen and reviewed by its own CJO
    production contract, so this boundary only verifies identity and exports
    the exact operating objects needed to prevent a parallel rewrite.
    """
    path = Path(snapshot_path).expanduser().resolve()
    snapshot = _load_json_file(str(path))
    if not snapshot:
        raise RuntimeError("投资 PIT 生产冻结需要可读取的 --company-judgment-snapshot")
    source_root = path.parent
    source_contract = _load_json_file(str(source_root / "analysis_contract.json"))
    thesis_path = source_root / "thesis_test.json"
    financial_driver_bridge_path = source_root / "financial_driver_bridge.json"
    thesis_policy = _load_json_file(str(source_root / "thesis_test_policy.json"))
    bridge_policy = _load_json_file(str(source_root / "financial_driver_bridge_policy.json"))
    thesis_validation = _load_json_file(str(source_root / "thesis_test_validation.json"))
    bridge_validation_artifact = _load_json_file(
        str(source_root / "financial_driver_bridge_validation.json")
    )
    thesis = _load_json_file(str(thesis_path))
    ledger_sha256 = snapshot.get("ledger_sha256") if isinstance(snapshot.get("ledger_sha256"), dict) else {}
    gate_states = snapshot.get("gate_states") if isinstance(snapshot.get("gate_states"), dict) else {}
    expected_thesis_hash = str(ledger_sha256.get("thesis_test") or "")
    expected_financial_driver_bridge_hash = str(ledger_sha256.get("financial_driver_bridge") or "")
    financial_driver_bridge = _load_json_file(str(financial_driver_bridge_path))
    findings: list[str] = []
    report_text = ""
    expected_report_hash = str(snapshot.get("report_sha256") or "")
    if expected_report_hash:
        for candidate in sorted((source_root / REPORTS_SUBDIR).glob("*.md")):
            if _sha256_file(candidate) == expected_report_hash:
                report_text = candidate.read_text(encoding="utf-8")
                break
    if not report_text:
        findings.append("predecessor_report_for_current_validation_missing")
    if snapshot.get("analysis_purpose") != "COMPANY_JUDGMENT_ONLY":
        findings.append("snapshot_not_company_judgment_only")
    if source_contract.get("analysis_purpose") != "COMPANY_JUDGMENT_ONLY":
        findings.append("predecessor_contract_not_company_judgment_only")
    if str(source_contract.get("ts_code") or source_contract.get("code") or "") != str(company_code):
        findings.append("predecessor_contract_company_code_mismatch")
    if str(source_contract.get("data_as_of") or source_contract.get("analysis_date") or "")[:10] != str(cutoff_at or "")[:10]:
        findings.append("predecessor_contract_cutoff_mismatch")
    if str(snapshot.get("report_id") or "") != str(company_code):
        findings.append("predecessor_company_code_mismatch")
    if str(snapshot.get("data_as_of") or "")[:10] != str(cutoff_at or "")[:10]:
        findings.append("predecessor_cutoff_mismatch")
    if snapshot.get("v3_enforced") is not True:
        findings.append("predecessor_snapshot_not_v3_enforced")
    if str(snapshot.get("completion_status") or "").upper() not in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
        findings.append("predecessor_completion_not_complete")
    if not str(snapshot.get("snapshot_fingerprint") or ""):
        findings.append("predecessor_snapshot_fingerprint_missing")
    if thesis.get("analysis_purpose") != "COMPANY_JUDGMENT_ONLY":
        findings.append("predecessor_thesis_not_company_judgment_only")
    if thesis.get("schema_version") != "thesis-test-ledger.v1":
        findings.append("predecessor_thesis_schema_invalid")
    if str(thesis.get("report_id") or "") != str(company_code):
        findings.append("predecessor_thesis_report_id_mismatch")
    if str(thesis.get("as_of") or "")[:10] != str(cutoff_at or "")[:10]:
        findings.append("predecessor_thesis_cutoff_mismatch")
    if not bool((thesis.get("freeze") or {}).get("frozen")):
        findings.append("predecessor_thesis_not_frozen")
    if not expected_thesis_hash or not thesis_path.is_file() or _sha256_file(thesis_path) != expected_thesis_hash:
        findings.append("predecessor_thesis_hash_mismatch")
    if expected_financial_driver_bridge_hash:
        if (
            not financial_driver_bridge_path.is_file()
            or _sha256_file(financial_driver_bridge_path) != expected_financial_driver_bridge_hash
        ):
            findings.append("predecessor_financial_driver_bridge_hash_mismatch")
        elif financial_driver_bridge.get("analysis_purpose") != "COMPANY_JUDGMENT_ONLY":
            findings.append("predecessor_financial_driver_bridge_not_company_judgment_only")
    if financial_driver_bridge:
        if financial_driver_bridge.get("schema_version") != "financial-driver-bridge.v1":
            findings.append("predecessor_financial_driver_bridge_schema_invalid")
        if str(financial_driver_bridge.get("report_id") or "") != str(company_code):
            findings.append("predecessor_financial_driver_bridge_report_id_mismatch")
        if str(financial_driver_bridge.get("as_of") or "")[:10] != str(cutoff_at or "")[:10]:
            findings.append("predecessor_financial_driver_bridge_cutoff_mismatch")
        bridge_company_id = str(
            financial_driver_bridge.get("company_id")
            or financial_driver_bridge.get("company_code") or ""
        )
        contract_company_id = str(source_contract.get("company_id") or company_code)
        if bridge_company_id and bridge_company_id not in {str(company_code), contract_company_id}:
            findings.append("predecessor_financial_driver_bridge_company_id_mismatch")
    current_thesis_policy = (
        thesis_policy.get("schema_version") == "thesis-test-policy.v3"
        and thesis_policy.get("enforced") is True
        and thesis_policy.get("monitoring_required") is True
        and thesis_policy.get("forward_judgment_required") is True
        and thesis_policy.get("rival_hypothesis_pair_required") is True
        and thesis_policy.get("company_judgment_lineage_required") is False
    )
    if not current_thesis_policy:
        findings.append("predecessor_thesis_policy_not_current_g1j")
    current_bridge_policy = (
        bridge_policy.get("schema_version") == "financial-driver-bridge-policy.v4"
        and bridge_policy.get("enforced") is True
        and bridge_policy.get("allocation_commitment_trace_required") is True
        and bridge_policy.get("cash_normalization_contract_required") is True
    )
    if not current_bridge_policy:
        findings.append("predecessor_financial_driver_bridge_policy_not_current_g1j")
    current_thesis_validation = (
        thesis_validation.get("schema_version") == "thesis-test-validation.v1"
        and thesis_validation.get("state") in {"DECISION_READY", "MONITORING"}
        and thesis_validation.get("analysis_purpose") == "COMPANY_JUDGMENT_ONLY"
        and thesis_validation.get("enforced") is True
        and thesis_validation.get("forward_judgment_required") is True
        and thesis_validation.get("forward_judgment_state") == "DECISION_READY"
        and thesis_validation.get("rival_hypothesis_pair_required") is True
        and thesis_validation.get("rival_hypothesis_pair_state") == "DECISION_READY"
        and thesis_validation.get("analogy_transfer_card_state") == "DECISION_READY"
    )
    if not current_thesis_validation:
        findings.append("predecessor_thesis_validation_not_current_g1j")
    current_bridge_validation = (
        bridge_validation_artifact.get("schema_version") == "financial-driver-bridge.v1"
        and bridge_validation_artifact.get("state") in {"REVIEWABLE", "DECISION_READY", "MONITORING"}
        and bridge_validation_artifact.get("analysis_purpose") == "COMPANY_JUDGMENT_ONLY"
        and bridge_validation_artifact.get("enforced") is True
    )
    if not current_bridge_validation:
        findings.append("predecessor_financial_driver_bridge_validation_not_current_g1j")
    try:
        from scripts.thesis_test_gate import evaluate_output_thesis_test
        from scripts.financial_driver_bridge import evaluate_output_financial_driver_bridge
    except ModuleNotFoundError:
        from thesis_test_gate import evaluate_output_thesis_test
        from financial_driver_bridge import evaluate_output_financial_driver_bridge
    fresh_thesis_validation = evaluate_output_thesis_test(
        source_root, report_text=report_text, persist=False,
    )
    fresh_bridge_validation = evaluate_output_financial_driver_bridge(source_root, persist=False)
    if fresh_thesis_validation.get("state") not in {"DECISION_READY", "MONITORING"}:
        findings.append(
            "predecessor_thesis_current_validation_failed:"
            + str(fresh_thesis_validation.get("state") or "MISSING")
        )
        findings.extend(
            "predecessor_thesis_current_validation:" + str(item)
            for item in [
                *(fresh_thesis_validation.get("invalid_findings") or []),
                *(fresh_thesis_validation.get("incomplete_findings") or []),
            ]
        )
    if fresh_bridge_validation.get("state") not in {"REVIEWABLE", "DECISION_READY", "MONITORING"}:
        findings.append(
            "predecessor_financial_driver_bridge_current_validation_failed:"
            + str(fresh_bridge_validation.get("state") or "MISSING")
        )
        findings.extend(
            "predecessor_financial_driver_bridge_current_validation:" + str(item)
            for item in [
                *(fresh_bridge_validation.get("invalid_findings") or []),
                *(fresh_bridge_validation.get("incomplete_findings") or []),
            ]
        )
    central_path = thesis.get("central_path") if isinstance(thesis.get("central_path"), dict) else {}
    forward_judgments = thesis.get("forward_judgments") if isinstance(thesis.get("forward_judgments"), list) else []
    mechanism_chains = thesis.get("mechanism_chains") if isinstance(thesis.get("mechanism_chains"), list) else []
    rival_hypothesis_pairs = (
        thesis.get("rival_hypothesis_pairs")
        if isinstance(thesis.get("rival_hypothesis_pairs"), list) else []
    )
    analogy_transfer_cards = (
        thesis.get("analogy_transfer_cards")
        if isinstance(thesis.get("analogy_transfer_cards"), list) else []
    )
    selection_admission = (
        thesis.get("selection_admission")
        if isinstance(thesis.get("selection_admission"), dict) else {}
    )
    selection_status = str(selection_admission.get("status") or "")
    if selection_status == "SELECTION_ADMITTED" and not str(central_path.get("path_id") or ""):
        findings.append("predecessor_central_path_missing")
    if selection_status == "NO_PRIMARY" and central_path:
        findings.append("predecessor_no_primary_cannot_carry_central_path")
    if not forward_judgments:
        findings.append("predecessor_forward_judgments_missing")
    if not mechanism_chains:
        findings.append("predecessor_mechanism_chains_missing")
    if findings:
        raise RuntimeError(
            "投资 PIT 生产冻结的公司判断前置物无效: " + ", ".join(findings)
        )
    thesis_freeze = thesis.get("freeze") if isinstance(thesis.get("freeze"), dict) else {}
    thesis_validation_state = str(fresh_thesis_validation.get("state") or "")
    bridge_validation = (
        financial_driver_bridge.get("validation")
        if isinstance(financial_driver_bridge.get("validation"), dict) else {}
    )
    financial_driver_bridge_embedded_validation_state = str(bridge_validation.get("state") or "")
    financial_driver_bridge_validation_state = str(fresh_bridge_validation.get("state") or "")
    missing_components: list[str] = []
    if not str(thesis_freeze.get("fingerprint") or ""):
        missing_components.append("thesis_freeze_fingerprint")
    if thesis_validation_state not in {"DECISION_READY", "MONITORING"}:
        missing_components.append("thesis_validation_state")
    if not rival_hypothesis_pairs:
        missing_components.append("rival_hypothesis_pairs")
    if not analogy_transfer_cards:
        missing_components.append("analogy_transfer_cards")
    if not str(selection_admission.get("status") or ""):
        missing_components.append("selection_admission")
    if not expected_financial_driver_bridge_hash:
        missing_components.append("financial_driver_bridge_sha256")
    if not financial_driver_bridge:
        missing_components.append("financial_driver_bridge")
    elif financial_driver_bridge.get("analysis_purpose") != "COMPANY_JUDGMENT_ONLY":
        missing_components.append("financial_driver_bridge_analysis_purpose")
    if financial_driver_bridge_validation_state not in {"REVIEWABLE", "DECISION_READY", "MONITORING"}:
        missing_components.append("financial_driver_bridge_validation_state")
    if financial_driver_bridge_embedded_validation_state not in {"REVIEWABLE", "DECISION_READY", "MONITORING"}:
        missing_components.append("financial_driver_bridge_embedded_validation_state")
    identity_status = "G1J_COMPLETE" if not missing_components else "LEGACY_PARTIAL"
    if identity_status != "G1J_COMPLETE":
        raise RuntimeError(
            "投资 PIT 生产冻结的公司判断前置物无效: predecessor_not_g1j_complete: "
            + ", ".join(missing_components)
        )
    return {
        "schema_version": "company-judgment-predecessor.v2",
        "identity": {
            "status": identity_status,
            "missing_components": missing_components,
        },
        "source": {
            "snapshot_path": str(path),
            "snapshot_fingerprint": str(snapshot["snapshot_fingerprint"]),
            "report_id": str(snapshot["report_id"]),
            "data_as_of": str(snapshot["data_as_of"]),
            "thesis_path": str(thesis_path),
            "thesis_sha256": expected_thesis_hash,
            "thesis_freeze_fingerprint": str(thesis_freeze.get("fingerprint") or ""),
            "thesis_validation_state": thesis_validation_state,
            "financial_driver_bridge_path": (
                str(financial_driver_bridge_path) if financial_driver_bridge else ""
            ),
            "financial_driver_bridge_sha256": expected_financial_driver_bridge_hash,
            "financial_driver_bridge_validation_state": financial_driver_bridge_validation_state,
            "financial_driver_bridge_embedded_validation_state": (
                financial_driver_bridge_embedded_validation_state
            ),
            "g1j_contract": {
                "thesis_policy_schema_version": thesis_policy.get("schema_version"),
                "financial_driver_bridge_policy_schema_version": bridge_policy.get("schema_version"),
                "thesis_validation_schema_version": thesis_validation.get("schema_version"),
                "financial_driver_bridge_validation_schema_version": bridge_validation_artifact.get("schema_version"),
            },
        },
        "central_path": central_path,
        "forward_judgments": forward_judgments,
        "mechanism_chains": mechanism_chains,
        "rival_hypothesis_pairs": rival_hypothesis_pairs,
        "analogy_transfer_cards": analogy_transfer_cards,
        "selection_admission": selection_admission,
        "financial_driver_bridge": financial_driver_bridge,
    }


def _load_episode_bound_current_company_judgment(
    frozen_cjo_path: str,
    admission_path: str,
    *,
    company_code: str,
    cutoff_at: str,
) -> dict[str, Any]:
    """Load the current Episode-first predecessor for investment production.

    The Frozen CJO and its current-company admission are existing canonical
    objects.  This loader only verifies their identity and authority, then
    binds their paths into the report contract.  It does not translate the
    Episode back into the legacy Comparative predecessor shape.
    """
    if not str(frozen_cjo_path or "").strip() or not str(admission_path or "").strip():
        raise RuntimeError(
            "Episode-bound investment production requires both --frozen-cjo "
            "and --current-company-cjo-admission"
        )
    frozen_path = Path(frozen_cjo_path).expanduser().resolve()
    receipt_path = Path(admission_path).expanduser().resolve()
    frozen = _load_json_file(str(frozen_path))
    receipt = _load_json_file(str(receipt_path))
    if not frozen or not receipt:
        raise RuntimeError("Episode-bound Frozen CJO or current-company admission is unreadable")
    try:
        from scripts.enterprise_judgment_core import validate_frozen_cjo
        from scripts.current_company_cjo_admission import (
            validate_frozen_current_company_cjo_admission,
        )
    except ModuleNotFoundError:  # pragma: no cover - direct script fallback
        from enterprise_judgment_core import validate_frozen_cjo
        from current_company_cjo_admission import (
            validate_frozen_current_company_cjo_admission,
        )
    frozen_validation = validate_frozen_cjo(frozen)
    if frozen_validation.get("state") != "VALID":
        raise RuntimeError(
            "Episode-bound Frozen CJO is invalid: "
            + ", ".join(str(item) for item in frozen_validation.get("findings") or [])
        )
    admission_validation = validate_frozen_current_company_cjo_admission(
        frozen_cjo=frozen,
        admission_receipt=receipt,
        require_overlay=True,
    )
    if admission_validation.get("state") != "VALID":
        raise RuntimeError(
            "Episode-bound current-company admission is invalid: "
            + ", ".join(str(item) for item in admission_validation.get("findings") or [])
        )
    projection = (
        frozen.get("underwriting_thesis_projection")
        if isinstance(frozen.get("underwriting_thesis_projection"), dict) else {}
    )
    if not projection:
        raise RuntimeError("Frozen CJO does not contain an EnterpriseUnderwritingEpisode projection")
    if projection.get("sample_identity") not in {"BLIND_REPLAY", "PROSPECTIVE_EPISODE"}:
        raise RuntimeError("Worked-case underwriting cannot enter current investment production")
    if not _company_identity_matches(frozen.get("company_id"), company_code):
        raise RuntimeError("Episode-bound Frozen CJO company does not match the production company")
    if str(frozen.get("cutoff_at") or "")[:10] != str(cutoff_at or "")[:10]:
        raise RuntimeError("Episode-bound Frozen CJO cutoff does not match the production cutoff")
    binding = (
        receipt.get("candidate_binding", {}).get("primary_binding", {})
        if isinstance(receipt.get("candidate_binding"), dict) else {}
    )
    if (
        binding.get("binding_kind") != "ENTERPRISE_UNDERWRITING_EPISODE"
        or binding.get("episode_id") != projection.get("episode_id")
        or binding.get("underwriting_thesis_id") != projection.get("underwriting_thesis_id")
    ):
        raise RuntimeError("Current-company admission is not bound to this underwriting Episode")
    return {
        "frozen_cjo_path": str(frozen_path),
        "current_company_cjo_admission_path": str(receipt_path),
        "company_id": str(frozen.get("company_id") or ""),
        "cutoff_at": str(frozen.get("cutoff_at") or ""),
        "episode_id": str(projection.get("episode_id") or ""),
        "underwriting_thesis_id": str(projection.get("underwriting_thesis_id") or ""),
        "sample_identity": str(projection.get("sample_identity") or ""),
    }


def _company_identity_matches(company_id: Any, production_code: Any) -> bool:
    """Match the canonical CN/HK identity forms used by training to runtime codes."""
    canonical = str(company_id or "").strip().upper()
    runtime = str(production_code or "").strip().upper()
    if canonical == runtime:
        return True
    if ":" not in canonical or "." not in runtime:
        return False
    market, security = canonical.split(":", 1)
    runtime_security, exchange = runtime.split(".", 1)
    runtime_market = {
        "SH": "CN", "SZ": "CN", "BJ": "CN", "HK": "HK",
    }.get(exchange)
    return bool(
        runtime_market == market
        and security
        and runtime_security
        and security == runtime_security
    )


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _normalize_tracking_report_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in _VALID_TRACKING_REPORT_TYPES else "annual"


def _tracking_period_end_default(report_type: str, fiscal_year: int | None) -> str:
    if not fiscal_year:
        return ""
    mapping = {
        "annual": f"{fiscal_year}-12-31",
        "q1": f"{fiscal_year}-03-31",
        "h1": f"{fiscal_year}-06-30",
        "q3": f"{fiscal_year}-09-30",
    }
    return mapping.get(report_type, "")


def _tracking_meta_from_contract(contract_path: str) -> dict[str, Any]:
    contract = _load_json_file(contract_path)
    tracking = contract.get('tracking') if isinstance(contract.get('tracking'), dict) else {}
    report_type = _normalize_tracking_report_type(
        tracking.get('report_type') or contract.get('report_type')
    )
    fiscal_year = _safe_int(tracking.get('fiscal_year') or contract.get('fiscal_year'))
    period_end = str(tracking.get('period_end') or contract.get('period_end') or '').strip()[:10]
    if fiscal_year is None:
        years = contract.get('effective_years') or []
        numeric_years = [int(y) for y in years if str(y).isdigit()]
        if numeric_years:
            fiscal_year = max(numeric_years)
    if fiscal_year is None and len(period_end) >= 4 and period_end[:4].isdigit():
        fiscal_year = int(period_end[:4])
    if not period_end:
        period_end = _tracking_period_end_default(report_type, fiscal_year)
    return {
        'report_type': report_type,
        'fiscal_year': fiscal_year,
        'period_end': period_end or None,
        'report_type_label': _REPORT_TYPE_LABELS.get(report_type, '年报'),
        'metric_comparison_basis': str(
            tracking.get('metric_comparison_basis')
            or contract.get('metric_comparison_basis')
            or ('unavailable' if report_type == 'annual' else 'yoy')
        ),
        'change_classification': str(tracking.get('change_classification') or contract.get('change_classification') or ''),
        'comparison_summary': str(tracking.get('comparison_summary') or contract.get('comparison_summary') or ''),
    }


def _tracking_node_key(meta: dict[str, Any]) -> str:
    report_type = _normalize_tracking_report_type(meta.get('report_type'))
    fiscal_year = _safe_int(meta.get('fiscal_year'))
    if report_type == 'annual':
        return f"{fiscal_year}_annual" if fiscal_year else 'annual'
    suffix = {'q1': 'Q1', 'h1': 'H1', 'q3': 'Q3'}.get(report_type, report_type.upper())
    return f"{fiscal_year}{suffix}" if fiscal_year else suffix


def _tracking_report_stem(meta: dict[str, Any]) -> str:
    report_type = _normalize_tracking_report_type(meta.get('report_type'))
    fiscal_year = _safe_int(meta.get('fiscal_year'))
    if report_type == 'annual':
        return str(fiscal_year) if fiscal_year else 'annual'
    suffix = {'q1': 'Q1', 'h1': 'H1', 'q3': 'Q3'}.get(report_type, report_type.upper())
    return f"{fiscal_year}{suffix}" if fiscal_year else suffix


def _copy_if_exists(src: str, dst: str) -> bool:
    if not src or not os.path.exists(src):
        return False
    if os.path.abspath(src) == os.path.abspath(dst):
        return True  # same file, nothing to do
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def _archive_existing_tracking_outputs(output_dir: str, node_key: str, targets: list[str]) -> str | None:
    existing = [path for path in targets if path and os.path.exists(path)]
    if not existing:
        return None
    archive_dir = os.path.join(output_dir, 'history', f"{node_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(archive_dir, exist_ok=True)
    for path in existing:
        shutil.copyfile(path, os.path.join(archive_dir, os.path.basename(path)))
    return archive_dir


def _read_bundle_summary(bundle_path: str) -> dict[str, Any]:
    bundle = _load_json_file(bundle_path)
    if not bundle:
        return {}
    return {
        'gg': bundle.get('gg') or {},
        'ddm': bundle.get('ddm') or {},
        'gg_discounted': bundle.get('gg_discounted') or {},
    }


def _seed_tracking_bundle_from_annual(output_dir: str) -> str:
    preferred = [
        os.path.join(output_dir, 'compute_bundle.latest_annual.json'),
        os.path.join(output_dir, 'compute_bundle_annual.json'),
    ]
    for candidate in preferred:
        if os.path.exists(candidate):
            shutil.copyfile(candidate, os.path.join(output_dir, 'compute_bundle.json'))
            return candidate
    candidates = sorted(
        Path(output_dir).glob('compute_bundle_*_annual.json'),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        src = str(candidates[0])
        shutil.copyfile(src, os.path.join(output_dir, 'compute_bundle.json'))
        return src
    return ''


def _write_json_file(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _surface_live_forward_due_inbox() -> dict[str, Any]:
    """Reconcile the persistent forward-result inbox before a CJO run.

    Registration reads only frozen contracts, never issuer result bodies.  It
    is therefore safe on every CJO entry.  The resulting task is persistent in
    the project database rather than a one-off scan that an Agent can forget.
    """
    try:
        from scripts.judgment_feedback_control import (
            ControlPlaneError, connect, execute_due_claim, initialize, reconcile, reconcile_candidate_conditions,
            sync_candidate_condition_contracts, sync_live_forward_contracts,
        )
        from scripts.config import get_db_path
    except ModuleNotFoundError:
        from judgment_feedback_control import (
            ControlPlaneError, connect, execute_due_claim, initialize, reconcile, reconcile_candidate_conditions,
            sync_candidate_condition_contracts, sync_live_forward_contracts,
        )
        from config import get_db_path
    contract_root = Path(_FRAMEWORK_DIR) / "docs" / "development" / "research" / "experiments"
    as_of = datetime.now().astimezone().replace(microsecond=0).isoformat()
    db_path = Path(get_db_path())
    if not db_path.is_file():
        result = {
            "status": "BLOCKED", "code": "judgment_feedback_database_missing", "db_path": str(db_path),
            "remediation": "initialize the configured production database explicitly; CJO entry will not create a worktree-local database",
        }
        print(f"[Judgment feedback inbox] BLOCKED: configured database is missing: {db_path}")
        return result
    conn = connect(db_path)
    executions: list[dict[str, Any]] = []
    try:
        initialize(conn)
        sync = sync_live_forward_contracts(conn, contract_root=contract_root, registered_at=as_of)
        candidate_condition_sync = sync_candidate_condition_contracts(
            conn, contract_root=contract_root, registered_at=as_of,
        )
        inbox = reconcile(conn, as_of=as_of)
        candidate_condition_inbox = reconcile_candidate_conditions(conn, as_of=as_of)
        due_ids = {
            str(item.get("feedback_item_id") or "")
            for item in inbox.get("items") or []
            if item.get("time_state") in {"DUE", "OVERDUE"}
        }
        # A CJO run may execute only an explicit, locally prepared outcome
        # request.  Absent that file it remains an inbox task; the agent never
        # manufactures an issuer query, source inventory or extraction from a
        # report it was not asked to read.
        for request_path in sorted(contract_root.rglob("09_outcome_execution.json")):
            request = _load_json_file(str(request_path))
            feedback_item_id = str(request.get("feedback_item_id") or "")
            if feedback_item_id not in due_ids:
                continue
            try:
                result = execute_due_claim(conn, execution_request_ref=request_path, actor_id="turtle_agent_due_runner")
                executions.append({"request_ref": str(request_path), "feedback_item_id": feedback_item_id, "result": result})
            except ControlPlaneError as exc:
                executions.append({
                    "request_ref": str(request_path), "feedback_item_id": feedback_item_id,
                    "status": "BLOCKED", "code": exc.code, "detail": exc.detail,
                })
        if executions:
            inbox = reconcile(conn, as_of=as_of)
    finally:
        conn.close()
    sync_rows = [
        row
        for item in sync.get("registered", [])
        for row in (item.get("result", {}).get("registered", []) or [])
    ]
    actionable = [item for item in inbox.get("items") or [] if item.get("time_state") in {"DUE", "OVERDUE"}]
    print(
        "[Judgment feedback inbox] "
        f"new={sum(1 for row in sync_rows if row.get('registered'))}, tracked={len(sync_rows)}, "
        f"actionable={len(actionable)}, executed={len(executions)}, contract_issues={len(sync.get('issues', []))}"
    )
    for issue in sync.get("issues", []):
        print(f"  ⚠ contract: {issue.get('contract_path')} / {issue.get('code')}")
    for item in actionable:
        print(
            "  ↪ "
            f"{item.get('time_state')}: {item.get('episode_id')} / {item.get('claim_id')} / {item.get('stage_id')} "
            "→ add an explicit 09_outcome_execution.json, or execute-due with a bounded frozen outcome-source manifest"
        )
    for execution in executions:
        print(
            "  ↪ execution: "
            f"{execution.get('feedback_item_id')} → {execution.get('result', {}).get('status') or execution.get('status')}"
        )
    candidate_rows = [
        row
        for item in candidate_condition_sync.get("registered", [])
        for row in (item.get("result", {}).get("registered", []) or [])
    ]
    candidate_actionable = [
        item for item in candidate_condition_inbox.get("items") or [] if item.get("time_state") == "DUE"
    ]
    print(
        "[Candidate condition inbox] "
        f"new={sum(1 for row in candidate_rows if row.get('registered'))}, tracked={len(candidate_rows)}, "
        f"actionable={len(candidate_actionable)}, contract_issues={len(candidate_condition_sync.get('issues', []))}"
    )
    for issue in candidate_condition_sync.get("issues", []):
        print(f"  ⚠ candidate condition contract: {issue.get('contract_path')} / {issue.get('code')}")
    for item in candidate_actionable:
        print(
            "  ↪ "
            f"DUE: {item.get('candidate_id')} / {item.get('condition_id')} "
            "-> enumerate the declared official source; do not read an outcome or execute a settlement"
        )
    return {
        "sync": sync,
        "inbox": inbox,
        "executions": executions,
        "candidate_conditions": {"sync": candidate_condition_sync, "inbox": candidate_condition_inbox},
    }


def _load_tracking_comparison(output_dir: str) -> dict[str, Any]:
    path = os.path.join(output_dir, '_comparison.json')
    data = _load_json_file(path)
    comparison = data.get('comparison') if isinstance(data.get('comparison'), dict) else {}
    if not comparison:
        return {}
    normalized = dict(comparison)
    key_changes = normalized.get('key_changes')
    if isinstance(key_changes, str):
        try:
            parsed = json.loads(key_changes)
            if isinstance(parsed, list):
                normalized['key_changes'] = parsed
        except Exception:
            pass
    return normalized


def _build_comparison_summary(comparison: dict[str, Any]) -> str:
    if not comparison:
        return ''
    parts: list[str] = []
    metric_parts: list[str] = []
    revenue_yoy = str(comparison.get('revenue_yoy') or '').strip()
    gross_margin_delta = str(comparison.get('gross_margin_delta') or '').strip()
    np_yoy = str(comparison.get('np_yoy') or '').strip()
    ocf_yoy = str(comparison.get('ocf_yoy') or '').strip()
    if revenue_yoy:
        metric_parts.append(f'营收{revenue_yoy}')
    if gross_margin_delta:
        metric_parts.append(f'毛利率{gross_margin_delta}')
    if np_yoy:
        metric_parts.append(f'归母净利{np_yoy}')
    if ocf_yoy:
        metric_parts.append(f'OCF{ocf_yoy}')
    if metric_parts:
        parts.append('，'.join(metric_parts))
    change_classification = str(comparison.get('change_classification') or '').strip()
    thesis_impact = str(comparison.get('thesis_impact') or '').strip()
    if change_classification:
        parts.append(f'归因={change_classification}')
    if thesis_impact:
        parts.append(f'thesis={thesis_impact}')
    key_changes = comparison.get('key_changes')
    if isinstance(key_changes, list):
        highlights = [str(item).strip() for item in key_changes if str(item).strip()]
        if highlights:
            parts.append('；'.join(highlights[:2]))
    elif isinstance(key_changes, str) and key_changes.strip():
        parts.append(key_changes.strip())
    return '；'.join(parts)[:200]


def _ensure_contract_tracking_metadata(
    contract_path: str,
    *,
    report_type: str = 'annual',
    fiscal_year: int | None = None,
    period_end: str = '',
) -> dict[str, Any]:
    contract = _load_json_file(contract_path)
    if not contract:
        return {}
    normalized_report_type = _normalize_tracking_report_type(report_type or contract.get('report_type'))
    resolved_fiscal_year = _safe_int(fiscal_year)
    existing = _tracking_meta_from_contract(contract_path)
    if resolved_fiscal_year is None:
        resolved_fiscal_year = _safe_int(existing.get('fiscal_year'))
    resolved_period_end = str(period_end or existing.get('period_end') or '').strip()[:10]
    if not resolved_period_end:
        resolved_period_end = _tracking_period_end_default(normalized_report_type, resolved_fiscal_year)
    # V12.19: 非 annual 节点的 change_classification 不能留空
    existing_change = str(contract.get('change_classification') or '')
    existing_summary = str(contract.get('comparison_summary') or '')
    if normalized_report_type != 'annual':
        if not existing_change or existing_change.strip() == '':
            existing_change = 'pending'
        if not existing_summary or existing_summary.strip() == '':
            existing_summary = '(待 Agent 填写)'
    tracking = {
        'report_type': normalized_report_type,
        'fiscal_year': resolved_fiscal_year,
        'period_end': resolved_period_end or None,
        'metric_comparison_basis': 'unavailable' if normalized_report_type == 'annual' else 'yoy',
        'change_classification': existing_change,
        'comparison_summary': existing_summary,
    }
    for key, value in tracking.items():
        contract[key] = value
    contract['tracking'] = dict(tracking)
    run_meta = contract.get('run_meta')
    if not isinstance(run_meta, dict):
        run_meta = {}
        contract['run_meta'] = run_meta
    run_meta.update(tracking)
    _write_json_file(contract_path, contract)
    return tracking


def _resolve_data_source_code(output_dir: str) -> str | None:
    """从 contract 或 DB 解析卫星标的的母标代码。"""
    # 1) 查 contract
    for f in os.listdir(output_dir):
        if 'analysis_contract' in f and f.endswith('.json'):
            c = _load_json_file(os.path.join(output_dir, f))
            ds = c.get('data_source_code')
            if not ds and isinstance(c.get('tracking'), dict):
                ds = c['tracking'].get('data_source_code')
            if ds:
                return ds
    # 2) 查 stocks DB
    import sqlite3
    dirname = os.path.basename(output_dir)
    code_part = dirname.split('_')[0]
    if len(code_part) == 6 and code_part.isdigit():
        ts = code_part + ('.SH' if code_part.startswith(('6','9')) else '.SZ')
    elif len(code_part) == 5 and code_part.isdigit() and code_part[0] == '0':
        ts = code_part + '.HK'
    elif re.search(r'[A-Z]', code_part, re.IGNORECASE):
        ts = code_part + '.DE' if 'D' in code_part.upper() else code_part.upper()
    else:
        ts = code_part
    db_candidates = [
        os.path.join(os.path.dirname(output_dir), '..', 'stock_analysis.db'),
        'stock_analysis.db',
    ]
    for db_path in db_candidates:
        if os.path.exists(db_path):
            try:
                db = sqlite3.connect(db_path)
                row = db.execute("SELECT data_source_code FROM stocks WHERE ts_code=?", (ts,)).fetchone()
                db.close()
                if row and row[0]:
                    return row[0]
            except Exception:
                pass
    return None


def _find_latest_annual_file(output_dir: str, pattern: str, is_satellite: bool = False) -> str | None:
    """在 output_dir 中找最新的 annual 节点文件。

    卫星标的不从自己目录找 annual（自己没有年报分析），直接从母标拿。
    普通标的优先找含 'annual' 的 versioned 文件，回退到原始文件。
    """
    candidates = []
    if not is_satellite:
        for f in os.listdir(output_dir):
            if pattern in f and 'annual' in f:
                path = os.path.join(output_dir, f)
                candidates.append((os.path.getmtime(path), path))
        if not candidates:
            # Fallback: 找不含 tracking marker 的原始文件
            for f in os.listdir(output_dir):
                if pattern in f and 'q1' not in f and 'h1' not in f and 'q3' not in f and 'Q' not in f:
                    path = os.path.join(output_dir, f)
                    if os.path.isfile(path) and not os.path.islink(path):
                        candidates.append((os.path.getmtime(path), path))
    if not candidates:
        # 卫星标的回退：从母标目录找
        ds = _resolve_data_source_code(output_dir)
        if ds:
            ds_short = ds.split('.')[0]
            parent_base = os.path.dirname(output_dir)
            for entry in os.listdir(parent_base):
                parent_dir = os.path.join(parent_base, entry)
                if entry.startswith(ds_short) and os.path.isdir(parent_dir):
                    if pattern in ('analysis_contract', 'compute_bundle'):
                        plain = os.path.join(parent_dir, pattern + '.json')
                        if os.path.exists(plain):
                            candidates.append((os.path.getmtime(plain), plain))
                    else:
                        # 报告文件可能有 '最新_' / code_ 前缀
                        for prefix in ['最新_', '最新年报_', ds_short + '_', '']:
                            plain = os.path.join(parent_dir, prefix + pattern)
                            if os.path.exists(plain):
                                candidates.append((os.path.getmtime(plain), plain))
                                break
                    for f in os.listdir(parent_dir):
                        if pattern in f and 'annual' in f:
                            candidates.append((os.path.getmtime(os.path.join(parent_dir, f)),
                                               os.path.join(parent_dir, f)))
                    break
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return None


def _extract_tracking_meta_from_report(output_dir: str, report_path: str) -> None:
    """V12.19: 从 Agent 生成的报告提取 tracking 元数据并写回 contract。

    解析报告中「变化归因」和「变化摘要」部分，
    更新 analysis_contract.json 和 _tracking_snapshot.json。
    """
    if not report_path or not os.path.exists(report_path):
        return
    with open(report_path, encoding='utf-8') as f:
        text = f.read()
    contract_path = os.path.join(output_dir, 'analysis_contract.json')
    contract = _load_json_file(contract_path)
    if not contract:
        return
    tracking = contract.get('tracking') if isinstance(contract.get('tracking'), dict) else {}
    run_meta = contract.get('run_meta') if isinstance(contract.get('run_meta'), dict) else {}
    report_type = _normalize_tracking_report_type(tracking.get('report_type') or contract.get('report_type'))
    if report_type == 'annual':
        return  # annual 节点不需要 tracking overlay 元数据

    comparison = _load_tracking_comparison(output_dir)
    comparison_classification = str(comparison.get('change_classification') or '').strip()
    comparison_summary = _build_comparison_summary(comparison)
    if comparison_classification:
        contract['change_classification'] = comparison_classification
        tracking['change_classification'] = comparison_classification
        run_meta['change_classification'] = comparison_classification
    if comparison_summary:
        contract['comparison_summary'] = comparison_summary
        tracking['comparison_summary'] = comparison_summary
        run_meta['comparison_summary'] = comparison_summary

    # 提取 change_classification
    classification = _extract_field(text, [
        r'变化归因[：:]\s*(seasonal|cyclical|structural|one_off|accounting|pending)',
        r'change_classification[：:]\s*(seasonal|cyclical|structural|one_off|accounting|pending)',
        r'\*\*归因\*\*[：:]\s*(seasonal|cyclical|structural|one_off|accounting|pending)',
    ])
    if classification and not comparison_classification:
        contract['change_classification'] = classification
        tracking['change_classification'] = classification
        run_meta['change_classification'] = classification

    # 提取 comparison_summary（变化摘要后的第一段，≤200字）
    summary = _extract_field(text, [
        r'相对上次(?:分析|年报|正式分析)的?变化[：:]\s*(.{10,200})',
        r'变化摘要[：:]\s*(.{10,200})',
        r'comparison_summary[：:]\s*(.{10,200})',
    ])
    if summary and not comparison_summary:
        contract['comparison_summary'] = summary[:200]
        tracking['comparison_summary'] = summary[:200]
        run_meta['comparison_summary'] = summary[:200]

    if comparison_classification or comparison_summary or classification or summary:
        contract['tracking'] = tracking
        contract['run_meta'] = run_meta
        _write_json_file(contract_path, contract)


def _extract_field(text: str, patterns: list[str]) -> str | None:
    """从文本中按正则提取字段值。"""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def _materialize_tracking_outputs(
    output_dir: str, report_path: str, diagnostics: dict[str, Any],
    *, validation_only: bool = False,
) -> str:
    if validation_only:
        diagnostics['tracking'] = {
            'validation_only': True,
            'candidate_report_path': report_path,
            'formal_outputs_unchanged': True,
        }
        return report_path
    contract_path = os.path.join(output_dir, 'analysis_contract.json')
    contract = _load_json_file(contract_path)
    meta = _tracking_meta_from_contract(contract_path)
    node_key = _tracking_node_key(meta)
    report_stem = _tracking_report_stem(meta)
    report_label = meta.get('report_type_label') or '年报'

    versioned_contract = os.path.join(output_dir, f'analysis_contract_{node_key}.json')
    versioned_bundle = os.path.join(output_dir, f'compute_bundle_{node_key}.json')
    reports_d = os.path.join(output_dir, REPORTS_SUBDIR)
    os.makedirs(reports_d, exist_ok=True)
    versioned_report = os.path.join(reports_d, f'{report_stem}_{report_label}_分析报告_{REPORT_VERSION}.md') if report_path and report_path.endswith('.md') else report_path
    latest_contract = os.path.join(output_dir, 'analysis_contract.latest.json')
    latest_bundle = os.path.join(output_dir, 'compute_bundle.latest.json')
    latest_report = os.path.join(reports_d, f'最新_分析报告_{REPORT_VERSION}.md') if report_path and report_path.endswith('.md') else report_path
    latest_annual_contract = os.path.join(output_dir, 'analysis_contract.latest_annual.json')
    latest_annual_bundle = os.path.join(output_dir, 'compute_bundle.latest_annual.json')
    latest_annual_report = os.path.join(reports_d, f'最新年报_分析报告_{REPORT_VERSION}.md')

    archive_dir = _archive_existing_tracking_outputs(
        output_dir,
        node_key,
        [versioned_contract, versioned_bundle, versioned_report],
    )

    copied_contract = _copy_if_exists(contract_path, versioned_contract)
    copied_bundle = _copy_if_exists(os.path.join(output_dir, 'compute_bundle.json'), versioned_bundle)
    copied_report = _copy_if_exists(report_path, versioned_report) if report_path and report_path.endswith('.md') else False

    if copied_contract:
        _copy_if_exists(versioned_contract, latest_contract)
    if copied_bundle:
        _copy_if_exists(versioned_bundle, latest_bundle)
    if copied_report:
        _copy_if_exists(versioned_report, latest_report)
        report_path = latest_report

    if meta.get('report_type') == 'annual':
        if copied_contract:
            _copy_if_exists(versioned_contract, latest_annual_contract)
        if copied_bundle:
            _copy_if_exists(versioned_bundle, latest_annual_bundle)
        if copied_report:
            _copy_if_exists(versioned_report, latest_annual_report)

    # V12.19: non-annual 节点也需要 latest_annual 指针（从目录现有的 annual 文件找）
    annual_contract = latest_annual_contract if meta.get('report_type') == 'annual' else None
    annual_bundle = latest_annual_bundle if meta.get('report_type') == 'annual' else None
    annual_report = latest_annual_report if meta.get('report_type') == 'annual' else None
    if meta.get('report_type') != 'annual':
        is_sat = bool(_resolve_data_source_code(output_dir))
        annual_contract = _find_latest_annual_file(output_dir, 'analysis_contract', is_satellite=is_sat)
        annual_bundle = _find_latest_annual_file(output_dir, 'compute_bundle', is_satellite=is_sat)
        annual_report = _find_latest_annual_file(output_dir, '分析报告_v12.md', is_satellite=is_sat)
        # fallback: 从 versioned 文件名找
        if not annual_contract:
            for f in sorted(os.listdir(output_dir), reverse=True):
                if 'analysis_contract' in f and f.endswith('.json') and 'annual' in f:
                    annual_contract = os.path.join(output_dir, f)
                    break
        if not annual_bundle:
            for f in sorted(os.listdir(output_dir), reverse=True):
                if 'compute_bundle' in f and 'annual' in f and f.endswith('.json'):
                    annual_bundle = os.path.join(output_dir, f)
                    break
        if not annual_report:
            for f in sorted(os.listdir(output_dir), reverse=True):
                if '年报' in f and f.endswith('.md'):
                    annual_report = os.path.join(output_dir, f)
                    break
        if annual_contract and os.path.exists(annual_contract):
            if os.path.abspath(annual_contract) != os.path.abspath(latest_annual_contract):
                _copy_if_exists(annual_contract, latest_annual_contract)
            annual_contract = latest_annual_contract
        if annual_bundle and os.path.exists(annual_bundle):
            if os.path.abspath(annual_bundle) != os.path.abspath(latest_annual_bundle):
                _copy_if_exists(annual_bundle, latest_annual_bundle)
            annual_bundle = latest_annual_bundle
        if annual_report and os.path.exists(annual_report):
            if os.path.abspath(annual_report) != os.path.abspath(latest_annual_report):
                _copy_if_exists(annual_report, latest_annual_report)
            annual_report = latest_annual_report

    tracking_snapshot = {
        'node_key': node_key,
        'report_type': meta.get('report_type'),
        'report_type_label': report_label,
        'fiscal_year': meta.get('fiscal_year'),
        'period_end': meta.get('period_end'),
        'metric_comparison_basis': meta.get('metric_comparison_basis'),
        'change_classification': meta.get('change_classification'),
        'comparison_summary': meta.get('comparison_summary'),
        'archive_dir': archive_dir,
        'versioned_contract_path': versioned_contract if copied_contract else None,
        'versioned_bundle_path': versioned_bundle if copied_bundle else None,
        'versioned_report_path': versioned_report if copied_report else None,
        'latest_contract_path': latest_contract if copied_contract else None,
        'latest_bundle_path': latest_bundle if copied_bundle else None,
        'latest_report_path': latest_report if copied_report else None,
        'latest_annual_contract_path': annual_contract,
        'latest_annual_bundle_path': annual_bundle,
        'latest_annual_report_path': annual_report,
    }
    tracking_snapshot_path = os.path.join(output_dir, '_tracking_snapshot.json')
    with open(tracking_snapshot_path, 'w', encoding='utf-8') as f:
        json.dump(tracking_snapshot, f, ensure_ascii=False, indent=2)
    diagnostics['tracking'] = tracking_snapshot
    return report_path


def _find_or_create_output_dir(code: str, code_short: str) -> str:
    """自动检测已有目录或从 DB 查中文名创建新目录。"""
    # 1. 找已有目录
    for d in os.listdir(_OUTPUT_DIR) if os.path.isdir(_OUTPUT_DIR) else []:
        if d.startswith(code_short + "_") and any('一' <= c <= '鿿' for c in d):
            return os.path.join(_OUTPUT_DIR, d)
    # 2. 从 DB 查中文名
    try:
        import sqlite3
        db_path = os.path.join(_FRAMEWORK_DIR, "stock_analysis.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            name = conn.execute("SELECT name_cn FROM stocks WHERE ts_code=?", (code,)).fetchone()
            conn.close()
            if name and name[0]:
                return os.path.join(_OUTPUT_DIR, f"{code_short}_{name[0]}")
    except Exception:
        pass
    # 3. 兜底
    return os.path.join(_OUTPUT_DIR, f"{code_short}_分析")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summarize_phase_result(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in (
        'ok', 'complete', 'skipped', 'downloaded', 'failed', 'error',
        'years_processed', 'years_skipped', 'files_written', 'effective_years',
    ):
        if key in result:
            summary[key] = result.get(key)
    return summary



def _read_contract(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _get_asset_profile(contract_path: str) -> dict[str, Any]:
    contract = _read_contract(contract_path)
    return contract.get('asset_profile', {}) if isinstance(contract, dict) else {}


def _should_build_technical_snapshot(asset_profile: dict[str, Any]) -> bool:
    mode = str((asset_profile or {}).get('analysis_mode') or 'stock')
    return mode == 'stock'

def _write_diagnostics(output_dir: str, diagnostics: dict[str, Any]) -> str:
    try:
        from scripts.runtime_governance import redact_sensitive
    except ModuleNotFoundError:
        from runtime_governance import redact_sensitive
    path = os.path.join(output_dir, '_diagnostics.json')
    os.makedirs(output_dir, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(redact_sensitive(diagnostics), f, ensure_ascii=False, indent=2, default=str)
    return path


def _load_completion_report(output_dir: str) -> dict[str, Any]:
    path = os.path.join(output_dir, "completion_report.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_golden_report_review_return(path: str) -> dict[str, Any]:
    """Load and validate one candidate-bound Golden Report review return."""
    review_path = Path(path).expanduser().resolve()
    if not review_path.is_file():
        raise RuntimeError(f"Golden Report review return 不存在: {review_path}")
    review = _load_json_file(str(review_path))
    try:
        from scripts.golden_report_feedback import validate_golden_report_review_return
    except ModuleNotFoundError:
        from golden_report_feedback import validate_golden_report_review_return
    validation = validate_golden_report_review_return(review)
    if validation.get("state") != "REVIEWABLE":
        raise RuntimeError(
            "Golden Report review return 无效: "
            + ", ".join(str(item) for item in validation.get("findings") or [])
        )
    return review


def _completion_with_review_return(
    completion: dict[str, Any], review: dict[str, Any],
) -> dict[str, Any]:
    """Attach the control-plane review for routing, without mutating completion."""
    if not review:
        return completion
    return {**completion, "golden_report_review_return": review}


def _requires_zero_pass_revalidation(
    *, repair_only: bool, requested_repairs: int,
    explicit_repairs: tuple[int, ...],
) -> bool:
    """A zero-pass repair run is a validation run, never a stale-report read."""
    return bool(repair_only and requested_repairs == 0 and not explicit_repairs)


def _refresh_completion_after_incomplete_source_pass(output_dir: str) -> dict[str, Any]:
    """Re-evaluate current chapters without publishing after a repair pass exhausts.

    A source-deepening pass may legitimately use its bounded write budget before
    every target passes.  That is a routing result for the next fresh context,
    not a reason to abort all remaining repair passes.
    """
    chapter_dir = Path(output_dir) / "chapters"
    if not chapter_dir.is_dir():
        chapter_dir = Path(output_dir)
    report_text = "\n\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(chapter_dir.glob("_ch*.md"))
    )
    try:
        from scripts.report_completion import evaluate_report_completion
    except ModuleNotFoundError:
        from report_completion import evaluate_report_completion
    return evaluate_report_completion(report_text, output_dir).to_dict()


def _repair_iteration_budget(repair_targets: tuple[int, ...], configured_cap: int) -> int:
    """Allocate a bounded fresh-context budget based on actual repair scope."""
    cap = max(1, int(configured_cap))
    if not repair_targets:
        return cap
    # Startup/list/read/audit/assemble overhead plus roughly five turns per
    # chapter.  Synthesis passes also have five staged structured ledgers;
    # without a separate allowance the agent reaches assemble immediately
    # after Ch0/Ch14 and silently skips the investment-quality gates.
    structured_overhead = 30 if {0, 14}.intersection(repair_targets) else 0
    return min(cap, max(10, 6 + 5 * len(repair_targets) + structured_overhead))


def _structured_context_stop_reason(agent: Any) -> str:
    """Return a non-retryable tool-level stop raised inside a fresh context."""
    return str(getattr(agent, "_structured_no_progress_error", "") or "").strip()


def _is_binding_only_repair(completion: dict[str, Any]) -> bool:
    """Return whether every remaining blocker is canonical-reference clerical work.

    Decision binding failures must not reopen annual-report/web research or change
    an already frozen investment conclusion.  The quality-hard-contract finding is
    allowed only as the downstream reflection of the same compiler failure.
    """
    findings = [
        str(item).strip()
        for item in completion.get("blocking_findings", [])
        if str(item).strip()
    ]
    if not findings or not any(
        item.startswith(("Decision ledger:", "Decision compiler:"))
        for item in findings
    ):
        return False
    allowed = ("Decision ledger:", "Decision compiler:", "Quality hard contract:")
    return all(item.startswith(allowed) for item in findings)


def _repair_stale_decision_bindings_before_model(
    output_dir: str, *, code: str, validation_only: bool,
) -> dict[str, Any] | None:
    """Clerically repair stale D-id anchors before selecting an LLM frontier."""
    validation = _load_json_file(
        os.path.join(output_dir, "decision_ledger_validation.json")
    )
    findings = [
        str(item) for item in (
            list(validation.get("invalid_findings") or [])
            + list(validation.get("incomplete_findings") or [])
        )
    ]
    binding_prefixes = (
        "decision_value_mismatch:",
        "decision_reference_missing:",
        "unknown_decision_reference:",
    )
    if not any(item.startswith(binding_prefixes) for item in findings):
        return None
    ledger = _load_json_file(os.path.join(output_dir, "decision_ledger.json"))
    if not ledger:
        return None
    claim_ledger = _load_json_file(os.path.join(output_dir, "claim_evidence.json"))
    if claim_ledger:
        from scripts.claim_evidence import bind_claim_references
        bind_claim_references(output_dir, claim_ledger)
    valuation_ledger = _load_json_file(os.path.join(output_dir, "valuation_model.json"))
    if valuation_ledger:
        from scripts.valuation_model_gate import bind_valuation_references
        bind_valuation_references(output_dir, valuation_ledger)
    from scripts.decision_ledger import repair_chapter_decision_references
    from turtle_agent.tools.write_tools import assemble_report as _assemble_after_binding
    existing = tuple(
        idx for idx in range(15)
        if Path(output_dir, "chapters", f"_ch{idx:02d}.md").is_file()
    )
    repaired = repair_chapter_decision_references(
        output_dir, ledger, chapters=existing,
    )
    assembled = _assemble_after_binding(
        output_dir=output_dir, company_name="", ts_code=code,
        validation_only=validation_only,
    )
    completion = (
        assembled.get("completion")
        if isinstance(assembled.get("completion"), dict)
        else _load_completion_report(output_dir)
    )
    print(
        "  🧷 模型前确定性D-id清理: removed="
        f"{repaired.get('removed_invalid_anchors', 0)}, inserted="
        f"{repaired.get('anchors_inserted', 0)}"
    )
    return completion


_STRUCTURED_FRONTIER_VALIDATIONS = (
    "claim_evidence_validation.json",
    "valuation_model_validation.json",
    "decision_reliability_validation.json",
    "thesis_test_validation.json",
    "decisive_question_findings_validation.json",
    "insight_validation.json",
)


def _structured_frontier_pending(output_dir: str) -> bool:
    """Return whether the dependency-ordered structured synthesis is unfinished."""
    try:
        from scripts.report_completion import has_valid_internal_valuation_hypothesis
    except ModuleNotFoundError:
        from report_completion import has_valid_internal_valuation_hypothesis
    internal_valuation_ready = has_valid_internal_valuation_hypothesis(output_dir)
    for filename in _STRUCTURED_FRONTIER_VALIDATIONS:
        validation = _load_json_file(os.path.join(output_dir, filename))
        state = str(
            validation.get("state") or validation.get("status") or "MISSING"
        ).upper()
        if (
            internal_valuation_ready
            and filename in {
                "valuation_model_validation.json",
                "decision_reliability_validation.json",
            }
        ):
            continue
        if filename == "claim_evidence_validation.json" and state == "INCOMPLETE":
            missing_derived = {
                chapter for chapter in (0, 14)
                if not Path(output_dir, "chapters", f"_ch{chapter:02d}.md").is_file()
            }
            prefixes = tuple(
                f"claim_reference_missing:Ch{chapter}:" for chapter in missing_derived
            )
            findings = set(validation.get("incomplete_findings") or [])
            required = set(validation.get("required_chapters") or [])
            covered = set(validation.get("covered_chapters") or [])
            if (
                missing_derived
                and not validation.get("invalid_findings")
                and findings
                and prefixes
                and all(str(item).startswith(prefixes) for item in findings)
                and required
                and required.issubset(covered)
            ):
                continue
        if state not in {"DECISION_READY", "MONITORING"}:
            return True
    return False


def _should_use_synthesis_only(
    output_dir: str,
    repair_targets: tuple[int, ...],
    *,
    binding_only: bool,
    completion: dict[str, Any],
) -> bool:
    """Keep Ch0/Ch14 immutable while a structured ledger is the real frontier.

    Completion can report ``Quality hard contract: failure in Ch0,Ch14`` as a
    downstream consequence of an invalid valuation/thesis/insight ledger.  That
    derived message must not reopen prose writing and let a model evade the
    candidate-first structured repair boundary.
    """
    if not repair_targets or binding_only:
        return False
    findings_text = " ".join(
        str(item) for item in completion.get("blocking_findings", [])
    )
    report_owned_reliability_targets = {
        7: "report_dps_identity_conflict",
        8: "maximum_balance_cannot_be_used_as_average_yield_denominator",
        11: "report_uses_double_counting_np_minus_w_aa_formula",
        12: "report_lambda_ratio_arithmetic_mismatch",
    }
    if "report_overstates_noncomparable_model:report" in findings_text and any(
        idx in repair_targets for idx in (11, 12, 13)
    ):
        return False
    if any(
        chapter in repair_targets and marker in findings_text
        for chapter, marker in report_owned_reliability_targets.items()
    ):
        # These reliability failures live in prose, not the valuation ledger.
        # Repair the owning ordinary chapter before resuming the structured
        # frontier; otherwise synthesis-only would make the defect impossible
        # to fix and loop forever.
        return False
    if _structured_frontier_pending(output_dir):
        # During a fresh build, missing/short ordinary chapters are real
        # upstream work: claim and valuation ledgers need their finished text.
        # Only freeze prose when ordinary targets have no genuine chapter
        # blocker and merely appear as downstream consequences of a structured
        # failure in an already complete report.
        chapter_blockers = {
            int(item.get("index")): list(item.get("blocking_rules") or [])
            for item in completion.get("chapter_results") or []
            if isinstance(item, dict) and str(item.get("index", "")).isdigit()
        }
        if any(
            idx not in {0, 14} and chapter_blockers.get(idx)
            for idx in repair_targets
        ):
            return False
        # Structured artifacts are upstream of every chapter-level decision
        # surface.  Completion may also list Ch12/Ch14/Ch0 because those
        # chapters consume an invalid ledger; those are derived blockers, not
        # permission to bypass the first unmet structured writer.  Keep every
        # chapter frozen until the dependency-ordered frontier is ready.
        return True
    if not set(repair_targets).issubset({0, 14}):
        return False
    return not any(
        re.search(r"\bCh(?:apter)?\s*(?:0|14)\b", str(item), re.IGNORECASE)
        for item in completion.get("blocking_findings", [])
    )


def _feedback_route_from_completion(completion: dict[str, Any]) -> dict[str, Any]:
    """Keep review work orders separate from the reader repair payload."""
    try:
        from scripts.golden_report_feedback import route_golden_report_feedback
    except ModuleNotFoundError:
        from golden_report_feedback import route_golden_report_feedback
    route = route_golden_report_feedback(completion)
    if not isinstance(route, dict):
        raise RuntimeError("golden report feedback router returned a non-object")
    return route


def _repair_targets_from_completion(completion: dict[str, Any]) -> tuple[int, ...]:
    """Extract blocked chapter indices in dependency order, summary last."""
    feedback_route = _feedback_route_from_completion(completion)
    routed_targets = feedback_route.get("repair_targets")
    if routed_targets is not None:
        selected = {
            int(idx) for idx in routed_targets
            if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx <= 14
        }
        return tuple(idx for idx in (*range(1, 14), 14, 0) if idx in selected)

    targets: list[int] = []
    for item in completion.get("chapter_results", []):
        if not isinstance(item, dict) or not item.get("blocking_rules"):
            continue
        try:
            idx = int(item["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if idx not in targets:
            targets.append(idx)
    # Backward-compatible fallback for older completion reports.
    for finding in completion.get("blocking_findings", []):
        match = re.match(r"Ch(\d+)\s*:", str(finding))
        if match:
            idx = int(match.group(1))
            if idx not in targets:
                targets.append(idx)
    findings_text = " ".join(str(item) for item in completion.get("blocking_findings", []))
    for marker, chapter in (
        ("report_dps_identity_conflict", 7),
        ("maximum_balance_cannot_be_used_as_average_yield_denominator", 8),
        ("report_uses_double_counting_np_minus_w_aa_formula", 11),
        ("report_lambda_ratio_arithmetic_mismatch", 12),
    ):
        if marker in findings_text:
            targets.append(chapter)
    if "report_overstates_noncomparable_model:report" in findings_text:
        targets.extend((11, 12, 13))
    if "Decision:" in findings_text:
        targets.extend((14, 0))
    structured_labels = (
        "Decision ledger:", "Claim evidence:", "Valuation model:",
        "Decision reliability:",
        "Thesis test:", "Insight ledger:", "Decisive questions:",
        "Decision compiler:",
    )
    if any(label in findings_text for label in structured_labels):
        # A missing structured ledger is a synthesis task, not evidence that
        # every chapter it may reference needs another rewrite. Explicit ChN
        # conflicts still route their owner chapter alongside Ch14/Ch0.
        structured_chapters = {
            int(match) for finding in completion.get("blocking_findings", [])
            if any(label in str(finding) for label in structured_labels)
            for match in re.findall(r"Ch(\d+)", str(finding))
        }
        targets.extend(structured_chapters)
        targets.extend((14, 0))
    if "Quality hard contract:" in findings_text:
        targets.extend(int(match) for match in re.findall(r"Ch(\d+)", findings_text))
    if "Quality:" in findings_text:
        if "dividend_identity" in findings_text:
            dividend_chapters = {
                int(match) for match in re.findall(r"Ch(\d+)", findings_text)
            }
            targets.extend(dividend_chapters or (6, 7, 8, 11, 12, 13, 14, 0))
        elif "data_point_audit" in findings_text:
            targets.extend((10, 11, 12, 13, 14, 0))
        elif "risk_disclosure" in findings_text:
            targets.extend((9, 14, 0))
        elif "conclusion_consistency" in findings_text:
            targets.extend((14, 0))
        elif not targets:
            targets.extend((10, 11, 12, 13, 14, 0))
    targets = list(dict.fromkeys(targets))
    return tuple(idx for idx in (*range(1, 14), 14, 0) if idx in targets)


def _repair_targets_for_pass(
    completion: dict[str, Any],
    pass_index: int,
    repair_passes: int,
) -> tuple[int, ...]:
    """Route automatic repair passes so late quantitative chapters get a fresh context."""
    targets = _repair_targets_from_completion(completion)
    if not targets or repair_passes <= 1:
        return targets

    findings_text = " ".join(
        str(item) for item in completion.get("blocking_findings", [])
    )
    report_owned = tuple(
        chapter for marker, chapter in (
            ("report_dps_identity_conflict", 7),
            ("maximum_balance_cannot_be_used_as_average_yield_denominator", 8),
            ("report_uses_double_counting_np_minus_w_aa_formula", 11),
            ("report_lambda_ratio_arithmetic_mismatch", 12),
        )
        if marker in findings_text and chapter in targets
    )
    if "report_overstates_noncomparable_model" in findings_text:
        report_owned += tuple(idx for idx in (11, 12, 13) if idx in targets)
    if report_owned and pass_index < repair_passes:
        return tuple(dict.fromkeys(report_owned))

    if repair_passes >= 4:
        ordinary = tuple(idx for idx in targets if idx not in {0, 14})
        synthesis = tuple(idx for idx in (14, 0) if idx in targets)
        missing_chapters = {
            int(item.get("index"))
            for item in completion.get("chapter_results") or []
            if isinstance(item, dict)
            and "missing_file" in (item.get("blocking_rules") or [])
        }
        # Coverage debt is more severe than a residual density miss. Prioritize
        # never-written chapters so one stubborn early chapter cannot occupy
        # every fresh-context batch and starve Ch11-Ch13 indefinitely.
        missing = tuple(idx for idx in ordinary if idx in missing_chapters)
        residual = tuple(idx for idx in ordinary if idx not in missing_chapters)
        batch = (missing + residual)[:4]
        if pass_index < repair_passes:
            return batch or synthesis
        # Reserve the last fresh context for Ch14/Ch0 and structured ledgers.
        # Mixing residual chapters into it repeatedly starved the synthesis
        # tools even when all earlier research was already on disk.
        return synthesis or batch

    if pass_index == 1:
        qualitative = tuple(idx for idx in targets if 1 <= idx <= 9)
        return qualitative or targets

    if pass_index == 2:
        quantitative = tuple(idx for idx in targets if 10 <= idx <= 13)
        synthesis = tuple(idx for idx in (14, 0) if idx in targets)
        routed = quantitative + synthesis
        return routed or targets

    return targets


def _scheduled_repair_passes(
    completion: dict[str, Any], *, requested: int, resumed_existing_work: bool = False
) -> int:
    """Return the paid repair budget from the latest deterministic completion.

    A prior COMPLETE is only a hint.  Policy initialization and local assembly
    may expose new contract blockers, so callers must pass the freshly reloaded
    completion rather than retaining the pre-closeout state.
    """
    if resumed_existing_work:
        return 0
    is_complete = bool(
        not completion.get("blocking_findings")
        and completion.get("status") in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}
    )
    return 0 if is_complete else max(0, int(requested))


def _explicit_repair_targets_for_pass(
    targets: tuple[int, ...],
    pass_index: int,
    repair_passes: int,
) -> tuple[int, ...]:
    """Route user-requested deepening targets without requiring a BLOCKED report."""
    ordered = tuple(idx for idx in (*range(1, 14), 14, 0) if idx in set(targets))
    if not ordered or repair_passes <= 1:
        return ordered
    if repair_passes >= 4:
        ordinary = tuple(idx for idx in ordered if idx not in {0, 14})
        synthesis = tuple(idx for idx in (14, 0) if idx in ordered)
        start = (pass_index - 1) * 4
        batch = ordinary[start:start + 4]
        if pass_index < repair_passes:
            return batch or synthesis
        return synthesis or batch
    if pass_index == 1:
        qualitative = tuple(idx for idx in ordered if 1 <= idx <= 9)
        return qualitative or ordered
    if pass_index == 2:
        quantitative = tuple(idx for idx in ordered if 10 <= idx <= 13)
        synthesis = tuple(idx for idx in (14, 0) if idx in ordered)
        routed = quantitative + synthesis
        return routed or ordered
    return ordered


# ===================================================================
# 主入口
# ===================================================================


def _run_pit_writer(
    *,
    code: str,
    output_dir: str,
    model: str,
    max_iterations: int,
    pit_runner: Any,
    pit_case_id: str,
    pit_experiment_id: str,
    diagnostics: dict[str, Any],
) -> str:
    """Run the isolated P10-B writer without entering the normal pipeline."""
    try:
        from turtle_agent.agent_loop import AgentConfig, TurtleAgent
        from turtle_agent.llm_client import LlmClient
        from turtle_agent.tool_registry import ToolRegistry
        from turtle_agent.tools.pit_read_tools import configure_pit_runner, clear_pit_runner
        from turtle_agent.tools.pit_write_tools import (
            clear_pit_writer,
            configure_pit_writer,
            pit_writer_attestation,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"PIT writer 导入失败: {exc}") from exc

    deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if deepseek_api_key:
        llm = LlmClient(provider="deepseek_oa", model="deepseek-v4-pro")
    elif anthropic_api_key:
        llm = LlmClient(provider="anthropic", model=model)
    else:
        raise RuntimeError("PIT writer 需要已配置的 DEEPSEEK_API_KEY 或 ANTHROPIC_API_KEY")

    tools = ToolRegistry()
    configure_pit_runner(pit_runner)
    configure_pit_writer(
        pit_runner,
        output_dir=output_dir,
        case_id=pit_case_id,
        experiment_id=pit_experiment_id,
    )
    tools.auto_discover("turtle_agent.tools.pit_read_tools")
    tools.auto_discover("turtle_agent.tools.pit_write_tools")
    diagnostics.update({
        "status": "pit_writer_running",
        "mode": "pit_writer",
        "tools": tools.list_tools(),
        "tool_count": len(tools),
        "pit_writer_budget": {"max_llm_calls": min(max(1, int(max_iterations)), 12)},
    })
    attestation_path = Path(output_dir) / "pit_runner_attestation.json"
    try:
        agent = TurtleAgent(
            llm=llm,
            tools=tools,
            config=AgentConfig(
                code=code,
                output_dir=output_dir,
                max_iterations=min(max(1, int(max_iterations)), 12),
                max_tokens_per_call=16384,
                publish_downstream=False,
                pit_mode=True,
                pit_case_id=pit_case_id,
                pit_experiment_id=pit_experiment_id,
                pit_cutoff_at=str(pit_runner.cutoff_at),
            ),
        )
        report_path = agent.analyze()
        writer = pit_writer_attestation()
        if writer.get("status") != "PASS":
            raise RuntimeError("PIT writer 未生成受限草案")
        diagnostics.update({
            "status": "completed",
            "report_path": report_path,
            "pit_attestation_path": str(attestation_path),
        })
        _write_diagnostics(output_dir, diagnostics)
        return report_path
    finally:
        attestation = pit_runner.attestation()
        attestation["writer"] = pit_writer_attestation()
        attestation["execution_mode"] = "PIT_WRITER"
        _write_json_file(str(attestation_path), attestation)
        clear_pit_writer()
        clear_pit_runner()


def _initialize_pit_production_output(
    *, output_dir: str, code: str, run_id: str, cutoff_at: str,
    analysis_purpose: str = "INVESTMENT_DECISION",
    company_judgment_predecessor: dict[str, Any] | None = None,
    canonical_judgment_binding: dict[str, Any] | None = None,
) -> None:
    """Seed only the local contracts a PIT production writer may complete."""
    if analysis_purpose not in {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}:
        raise RuntimeError("PIT production analysis_purpose invalid")
    cutoff_date = str(cutoff_at or "")[:10]
    has_legacy_predecessor = isinstance(company_judgment_predecessor, dict)
    has_episode_binding = isinstance(canonical_judgment_binding, dict)
    if analysis_purpose == "INVESTMENT_DECISION" and not (
        has_legacy_predecessor or has_episode_binding
    ):
        raise RuntimeError("投资 PIT 生产冻结需要同 cutoff 的冻结公司判断")
    if analysis_purpose == "INVESTMENT_DECISION" and has_legacy_predecessor and has_episode_binding:
        raise RuntimeError("Legacy predecessor and Episode-bound Frozen CJO are mutually exclusive")
    if analysis_purpose == "INVESTMENT_DECISION" and has_legacy_predecessor:
        predecessor_findings = _investment_predecessor_findings(
            company_judgment_predecessor or {}, company_code=code, cutoff_at=cutoff_at,
        )
        if predecessor_findings:
            raise RuntimeError(
                "投资 PIT 生产冻结的公司判断前置物未通过运行时硬门: "
                + ", ".join(predecessor_findings)
            )
    contract = {
        "schema_version": "analysis-contract.v1",
        "ts_code": code,
        "code": code,
        "run_id": run_id,
        "analysis_date": cutoff_date,
        "data_as_of": cutoff_date,
        "report_type": "annual",
        "analysis_purpose": analysis_purpose,
        "tracking": {"report_type": "annual", "period_end": cutoff_date},
        "pit_production": {"cutoff_at": cutoff_at, "source_access": "PIT_ALLOWLIST_ONLY"},
    }
    if has_episode_binding:
        binding = canonical_judgment_binding or {}
        contract["company_id"] = binding.get("company_id")
        contract["canonical_judgment_refs"] = {
            "frozen_cjo_ref": binding.get("frozen_cjo_path"),
            "current_company_cjo_admission_ref": binding.get(
                "current_company_cjo_admission_path"
            ),
        }
    elif analysis_purpose == "INVESTMENT_DECISION":
        predecessor_path = Path(output_dir) / "company_judgment_predecessor.json"
        _write_json_file(str(predecessor_path), company_judgment_predecessor or {})
        source = (company_judgment_predecessor or {}).get("source") or {}
        identity = (company_judgment_predecessor or {}).get("identity") or {}
        contract["company_judgment_predecessor"] = {
            "completeness_status": identity.get("status"),
            "missing_components": identity.get("missing_components") or [],
            "snapshot_fingerprint": source.get("snapshot_fingerprint"),
            "thesis_sha256": source.get("thesis_sha256"),
            "thesis_freeze_fingerprint": source.get("thesis_freeze_fingerprint"),
            "thesis_validation_state": source.get("thesis_validation_state"),
            "financial_driver_bridge_sha256": source.get("financial_driver_bridge_sha256"),
            "financial_driver_bridge_validation_state": source.get("financial_driver_bridge_validation_state"),
            "financial_driver_bridge_embedded_validation_state": source.get(
                "financial_driver_bridge_embedded_validation_state"
            ),
            "data_as_of": source.get("data_as_of"),
            "central_path_id": ((company_judgment_predecessor or {}).get("central_path") or {}).get("path_id"),
            "forward_judgment_ids": [
                item.get("judgment_id")
                for item in (company_judgment_predecessor or {}).get("forward_judgments") or []
                if isinstance(item, dict) and item.get("judgment_id")
            ],
            "rival_hypothesis_pair_ids": sorted(
                str(item.get("pair_id"))
                for item in (company_judgment_predecessor or {}).get("rival_hypothesis_pairs") or []
                if isinstance(item, dict) and item.get("pair_id")
            ),
            "analogy_transfer_card_ids": sorted(
                str(item.get("card_id"))
                for item in (company_judgment_predecessor or {}).get("analogy_transfer_cards") or []
                if isinstance(item, dict) and item.get("card_id")
            ),
            "selection_admission_status": (
                ((company_judgment_predecessor or {}).get("selection_admission") or {}).get("status")
            ),
        }
    _write_json_file(str(Path(output_dir) / "analysis_contract.json"), contract)
    _refresh_report_learning_admissions(output_dir)
    from scripts.evidence_documents import initialize_official_evidence_policy
    from scripts.claim_evidence import initialize_claim_evidence_policy
    from scripts.insight_ledger import initialize_insight_policy
    initialize_official_evidence_policy(output_dir, run_id=run_id, enforced=True)
    initialize_claim_evidence_policy(output_dir, run_id=run_id, enforced=True)
    if not has_episode_binding:
        # The legacy predecessor owns a financial-driver bridge and the
        # thesis/FJ/pair ledger.  A complete EnterpriseUnderwritingEpisode
        # already owns that price-free company story, so recreating those
        # artifacts would introduce a second, potentially contradictory
        # judgment path.
        from scripts.financial_driver_bridge import initialize_financial_driver_bridge_policy
        from scripts.thesis_test_gate import initialize_thesis_test_policy
        initialize_financial_driver_bridge_policy(output_dir, run_id=run_id, enforced=True)
        initialize_thesis_test_policy(
            output_dir, run_id=run_id, enforced=True, monitoring_required=True,
            forward_judgment_required=True, rival_hypothesis_pair_required=True,
            company_judgment_lineage_required=(
                analysis_purpose == "INVESTMENT_DECISION"
            ),
        )
    initialize_insight_policy(output_dir, run_id=run_id, enforced=True)
    if analysis_purpose == "INVESTMENT_DECISION":
        from scripts.decision_ledger import initialize_decision_ledger_policy
        from scripts.decision_compiler import initialize_decision_compiler_policy
        from scripts.valuation_model_gate import initialize_valuation_model_policy
        from scripts.decision_reliability import initialize_decision_reliability_policy
        from scripts.valuation_routing import initialize_valuation_route_policy
        from scripts.decisive_question import initialize_decisive_question_policy
        from scripts.base_rate_case_library import initialize_base_rate_policy
        initialize_valuation_route_policy(output_dir, run_id=run_id, enforced=True)
        initialize_decisive_question_policy(output_dir, run_id=run_id, enforced=True)
        initialize_base_rate_policy(output_dir, run_id=run_id, enforced=True)
        initialize_decision_ledger_policy(output_dir, run_id=run_id, enforced=True)
        initialize_decision_compiler_policy(output_dir, run_id=run_id, enforced=True)
        initialize_valuation_model_policy(
            output_dir,
            run_id=run_id,
            enforced=True,
            require_normalization_bridge=True,
            require_owner_earnings_normalization=True,
            require_value_bridge_models=True,
            require_value_bridge_fact_bindings=True,
        )
        initialize_decision_reliability_policy(output_dir, run_id=run_id, enforced=True)


def _validate_pit_production_completion(
    *, output_dir: str, report_path: str, run_id: str,
    analysis_purpose: str = "INVESTMENT_DECISION",
) -> dict[str, Any]:
    """Confirm the normal report exit completed before a PIT freeze is published."""
    output = Path(output_dir).expanduser().resolve()
    report = Path(report_path).expanduser().resolve()
    if output not in report.parents or not report.is_file():
        raise RuntimeError("PIT production report must be a materialized file under its fresh output directory")
    if "drafts" in report.parts:
        raise RuntimeError("PIT production report remained a draft; publication is prohibited")

    completion = _load_completion_report(str(output))
    status = str(completion.get("status") or "").upper()
    if status not in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
        raise RuntimeError("PIT production report did not pass completion contract: " + (status or "MISSING"))
    validators = completion.get("validators") if isinstance(completion.get("validators"), dict) else {}
    snapshot_result = validators.get("publication_snapshot") if isinstance(validators, dict) else {}
    if not isinstance(snapshot_result, dict) or snapshot_result.get("written") is not True:
        raise RuntimeError("PIT production report lacks a successful publication snapshot")

    snapshot = _load_json_file(str(output / "publication_snapshot.json"))
    if not snapshot:
        raise RuntimeError("PIT production publication snapshot is missing")
    if str(snapshot.get("run_id") or "") != str(run_id):
        raise RuntimeError("PIT production publication snapshot run_id does not match the active run")
    snapshot_purpose = str(snapshot.get("analysis_purpose") or "")
    if (
        (snapshot_purpose and snapshot_purpose != str(analysis_purpose))
        or (analysis_purpose == "COMPANY_JUDGMENT_ONLY" and not snapshot_purpose)
    ):
        raise RuntimeError("PIT production publication snapshot analysis_purpose does not match the active run")
    if str(snapshot.get("completion_status") or "").upper() not in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
        raise RuntimeError("PIT production publication snapshot does not record a completed report")
    if snapshot.get("v3_enforced") is not True:
        raise RuntimeError("PIT production publication snapshot is not V3-enforced")
    contract = _load_json_file(str(output / "analysis_contract.json"))
    if analysis_purpose == "INVESTMENT_DECISION":
        refs = (
            contract.get("canonical_judgment_refs")
            if isinstance(contract.get("canonical_judgment_refs"), dict) else {}
        )
        if refs.get("frozen_cjo_ref") or refs.get("current_company_cjo_admission_ref"):
            _load_episode_bound_current_company_judgment(
                str(refs.get("frozen_cjo_ref") or ""),
                str(refs.get("current_company_cjo_admission_ref") or ""),
                company_code=str(contract.get("ts_code") or contract.get("code") or ""),
                cutoff_at=str(contract.get("data_as_of") or contract.get("analysis_date") or ""),
            )
        else:
            predecessor = _load_json_file(str(output / "company_judgment_predecessor.json"))
            predecessor_findings = _investment_predecessor_findings(
                predecessor,
                company_code=str(contract.get("ts_code") or contract.get("code") or ""),
                cutoff_at=str(contract.get("data_as_of") or contract.get("analysis_date") or ""),
                analysis_contract=contract,
            )
            if predecessor_findings:
                raise RuntimeError(
                    "PIT production completion company-judgment predecessor invalid: "
                    + ", ".join(predecessor_findings)
                )
    from turtle_agent.tools.pit_production_write_tools import validate_pit_handoff_receipts
    handoff_receipts = validate_pit_handoff_receipts(
        output_dir=output, analysis_purpose=analysis_purpose, run_id=run_id,
    )
    if handoff_receipts.get("state") != "READY":
        raise RuntimeError(
            "PIT production completion judgment handoff receipts invalid: "
            + ", ".join(str(item) for item in handoff_receipts.get("findings") or [])
        )
    attestation_path = output / "pit_runner_attestation.json"
    attestation = _load_json_file(str(attestation_path))
    writer = attestation.get("writer") if isinstance(attestation.get("writer"), dict) else {}
    if attestation.get("execution_mode") != "PIT_PRODUCTION_FREEZE":
        raise RuntimeError("PIT production attestation does not record the production execution mode")
    if str(attestation.get("run_id") or "") != str(run_id) or str(writer.get("run_id") or "") != str(run_id):
        raise RuntimeError("PIT production attestation run_id does not match the active run")
    if str(writer.get("final_report_path") or "") != str(report):
        raise RuntimeError("PIT production attestation final report path does not match the published report")
    source_anchors = {str(value) for value in writer.get("source_anchor_ids", []) if str(value)}
    read_sources = {str(value) for value in writer.get("read_source_ids", []) if str(value)}
    if not source_anchors.issubset(read_sources):
        raise RuntimeError("PIT production attestation contains source anchors outside actual reads")
    return {
        "completion_status": status,
        "report_path": str(report),
        "publication_snapshot_path": str(output / "publication_snapshot.json"),
        "pit_attestation_path": str(attestation_path),
    }


def _run_pit_production_freeze(
    *, code: str, output_dir: str, model: str, max_iterations: int, pit_runner: Any,
    pit_case_id: str, pit_experiment_id: str, runtime: Any, diagnostics: dict[str, Any],
    analysis_purpose: str = "INVESTMENT_DECISION",
    company_judgment_predecessor: dict[str, Any] | None = None,
    canonical_judgment_binding: dict[str, Any] | None = None,
) -> str:
    """Run one full PIT report with the normal V3 exits but no normal inputs."""
    from scripts.phase10_pit_production import PITProductionWorkspace
    from turtle_agent.agent_loop import AgentConfig, TurtleAgent
    from turtle_agent.llm_client import LlmClient
    from turtle_agent.tool_registry import ToolRegistry
    from turtle_agent.tools.pit_read_tools import configure_pit_runner, clear_pit_runner
    from turtle_agent.tools import pit_production_write_tools as production_tools
    deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if deepseek_api_key:
        llm = LlmClient(provider="deepseek_oa", model="deepseek-v4-pro", runtime_controller=runtime)
    elif anthropic_api_key:
        llm = LlmClient(provider="anthropic", model=model, runtime_controller=runtime)
    else:
        raise RuntimeError("PIT production writer 需要已配置的 DEEPSEEK_API_KEY 或 ANTHROPIC_API_KEY")
    _initialize_pit_production_output(
        output_dir=output_dir, code=code, run_id=pit_runner.run_id, cutoff_at=str(pit_runner.cutoff_at),
        analysis_purpose=analysis_purpose, company_judgment_predecessor=company_judgment_predecessor,
        canonical_judgment_binding=canonical_judgment_binding,
    )
    workspace = PITProductionWorkspace(
        pit_runner, output_dir, company_code=code, run_id=str(pit_runner.run_id),
    )
    tools = ToolRegistry()
    configure_pit_runner(pit_runner, production_workspace=workspace)
    production_tools.configure_pit_production_writer(
        output_dir=output_dir, code=code, run_id=str(pit_runner.run_id), pit_runner=pit_runner,
        analysis_purpose=analysis_purpose,
    )
    tools.auto_discover("turtle_agent.tools.pit_read_tools")
    writer_tool_names = {
        "pit_verify_official_fact", "pit_write_chapter", "pit_read_chapter",
        "pit_read_report_contract_pack", "pit_read_judgment_generation_handoff",
        "pit_read_structured_ledger_contract",
        "pit_audit_chapter", "pit_write_claim_evidence_ledger",
        "pit_write_financial_driver_bridge", "pit_write_thesis_test_ledger",
        "pit_write_insight_ledger", "pit_write_judgment_review", "pit_assemble_report",
    }
    if analysis_purpose == "INVESTMENT_DECISION":
        writer_tool_names.update({
            "pit_write_decision_manifest", "pit_write_decision_ledger",
            "pit_write_valuation_model_ledger", "pit_write_decisive_question_findings",
        })
    for name in sorted(writer_tool_names):
        tool = getattr(production_tools, name)
        meta = getattr(tool, "_tool_meta")
        tools.register(name, tool, description=meta.get("description", ""), parameters=meta.get("parameters", {}))
    attestation_path = Path(output_dir) / "pit_runner_attestation.json"
    diagnostics.update({"status": "pit_production_running", "mode": "pit_production_freeze",
                        "tools": tools.list_tools(), "tool_count": len(tools)})
    report_path = ""
    try:
        report_path = TurtleAgent(
            llm=llm, tools=tools,
            config=AgentConfig(code=code, output_dir=output_dir, max_iterations=max(1, int(max_iterations)),
                max_tokens_per_call=32768, publish_downstream=False, pit_production_mode=True,
                pit_case_id=pit_case_id, pit_experiment_id=pit_experiment_id,
                pit_cutoff_at=str(pit_runner.cutoff_at), run_id=str(pit_runner.run_id),
                analysis_purpose=analysis_purpose),
        ).analyze()
        diagnostics.update({"status": "completed", "report_path": report_path,
                            "pit_attestation_path": str(attestation_path)})
        return report_path
    finally:
        attestation = pit_runner.attestation()
        read_source_ids = sorted({
            str(event.get("source_id") or "")
            for event in attestation.get("read_audit", [])
            if event.get("allowed") is True and event.get("kind") == "SOURCE" and event.get("source_id")
        })
        attestation.update({"execution_mode": "PIT_PRODUCTION_FREEZE", "writer": {
            "provider": getattr(llm, "_provider", ""), "model": getattr(llm, "model", ""),
            "run_id": pit_runner.run_id, "case_id": pit_case_id, "experiment_id": pit_experiment_id,
            "final_report_path": str(Path(report_path).expanduser().resolve()) if report_path else "",
            "source_anchor_ids": production_tools.production_source_anchor_ids(),
            "read_source_ids": read_source_ids,
        }})
        _write_json_file(str(attestation_path), attestation)
        runtime.manifest.add_artifact(attestation_path, "pit_runner_attestation")
        production_tools.clear_pit_production_writer()
        clear_pit_runner()


def run_full_pipeline(
    code: str,
    *,
    output_dir: str = "",
    skip_prepare: bool = False,
    dry_run: bool = False,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-20250514",
    max_iterations: int = 80,
    repair_passes: int = 6,
    repair_max_iterations: int = 40,
    judgment_task_retries: int = 2,
    judgment_task_max_iterations: int = 14,
    chapter_attempts_per_pass: int = 2,
    repair_only: bool = False,
    repair_chapters: tuple[int, ...] = (),
    source_deepening: bool | None = None,
    template_path: str = "templates/report_template_v10.md",
    unified: bool = False,
    qualitative_only: bool = False,
    data_source: str = "",  # V12.19: 卫星标的母标代码
    price_source: str = "",  # 交易价格/市值来源代码
    report_type: str = "annual",
    fiscal_year: int | None = None,
    period_end: str = "",
    validation_only: bool = False,
    approve_expensive_run: bool = False,
    pit_source_manifest: str = "",
    pit_package_root: str = "",
    pit_framework_root: str = "",
    pit_case_id: str = "",
    pit_experiment_id: str = "",
    pit_preflight: bool = False,
    pit_writer: bool = False,
    pit_production_freeze: bool = False,
    analysis_purpose: str = "INVESTMENT_DECISION",
    company_judgment_snapshot: str = "",
    review_return: str = "",
    frozen_cjo: str = "",
    current_company_cjo_admission: str = "",
) -> str:
    """运行完整分析管线。

    V11: Phase 0 → 0.5 → 1 → 2 → Agent Loop (定量报告)
    V12: Phase 0 → 0.5 → 1 → 2 → Agent Loop (定性+定量统一报告)

    Agent Loop 内全自动：定性写作 Ch1-9 → 摘要提取 → Zone J → 定量估值 Ch10-13 → 统一决策。
    所有 LLM 调用走 Claude Code 内置 API（不受子进程安全策略限制）。
    """
    analysis_purpose = str(analysis_purpose or "INVESTMENT_DECISION").upper()
    if analysis_purpose not in {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}:
        raise RuntimeError("analysis_purpose 只允许 INVESTMENT_DECISION 或 COMPANY_JUDGMENT_ONLY")
    pit_values = (pit_source_manifest, pit_package_root, pit_case_id, pit_experiment_id)
    if any(str(value or "").strip() for value in pit_values) and not all(str(value or "").strip() for value in pit_values):
        raise RuntimeError("PIT参数必须完整提供 manifest/package/case/experiment")
    pit_mode = bool(str(pit_source_manifest or "").strip())
    if analysis_purpose == "COMPANY_JUDGMENT_ONLY" and not (
        pit_mode and (pit_preflight or pit_production_freeze)
    ):
        raise RuntimeError("COMPANY_JUDGMENT_ONLY 只支持 PIT 预检或受限生产入口")
    if pit_mode:
        static_framework_root = _PIT_FRAMEWORK_ROOT.resolve()
        if pit_framework_root and Path(pit_framework_root).expanduser().resolve() != static_framework_root:
            raise RuntimeError("PIT framework root 必须使用仓库内受控静态目录")
        if sum(bool(value) for value in (pit_preflight, pit_writer, pit_production_freeze)) != 1:
            raise RuntimeError("PIT运行必须三选一指定 --pit-preflight、--pit-writer 或 --pit-production-freeze")
        if not output_dir:
            raise RuntimeError("PIT运行必须显式提供新的 --output 目录")
        ordinary_mode = (
            data_source or price_source or repair_only or dry_run or unified or qualitative_only
            or repair_chapters or source_deepening is not None or review_return
        )
        if ordinary_mode or (pit_production_freeze and validation_only) or (
            not pit_production_freeze and not validation_only
        ):
            raise RuntimeError(
                "PIT运行禁止普通报告、数据源、当前价格、repair-only、dry-run、unified、"
                "qualitative-only、章节修复和来源深化；草案/预检必须 --validation-only，"
                "production-freeze 禁止 --validation-only"
            )
        existing = Path(output_dir)
        if existing.exists() and any(existing.iterdir()):
            raise RuntimeError("PIT运行要求 --output 是新建或空目录，禁止复用现有输出")
        if not pit_package_root:
            raise RuntimeError("PIT运行缺少 --pit-package-root")
        if not pit_case_id or not pit_experiment_id:
            raise RuntimeError("PIT运行缺少 --pit-case-id/--pit-experiment-id")
        output_root = existing.expanduser().resolve()
        input_roots = [
            Path(pit_package_root).expanduser().resolve(),
            static_framework_root,
        ]
        if any(
            output_root == root or output_root in root.parents or root in output_root.parents
            for root in input_roots
        ):
            raise RuntimeError("PIT运行要求 --output 与 source/framework 输入根目录隔离")
        skip_prepare = True
    if not output_dir:
        # 自动检测或创建带中文名的目录
        code_short = code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
        output_dir = _find_or_create_output_dir(code, code_short)
    os.makedirs(output_dir, exist_ok=True)
    if review_return and not repair_only:
        raise RuntimeError("--review-return 必须与 --repair-only 一起使用")
    if review_return and not validation_only:
        raise RuntimeError("--review-return 只生成待复核候选，必须使用 --validation-only")
    if review_return and repair_chapters:
        raise RuntimeError("--review-return 禁止 --repair-chapters 绕过责任分流")
    review_return_payload = (
        _load_golden_report_review_return(review_return) if review_return else {}
    )
    if review_return_payload:
        try:
            initial_route = _feedback_route_from_completion(
                _completion_with_review_return({}, review_return_payload)
            )
        except ValueError as exc:
            raise RuntimeError(f"Golden Report review return 无法路由: {exc}") from exc
        _write_json_file(
            os.path.join(output_dir, "golden_report_feedback_routing.json"),
            initial_route,
        )

    if analysis_purpose == "COMPANY_JUDGMENT_ONLY":
        # This happens before the CJO Agent loop and intentionally has no
        # access to outcome bodies.  It surfaces a due frozen result without
        # letting an unrelated company report silently consume it.
        _surface_live_forward_due_inbox()

    # Auto-detect full ts_code (with market suffix) from existing contract or heuristics
    contract_path = os.path.join(output_dir, "analysis_contract.json")
    if "." not in code and os.path.exists(contract_path):
        try:
            with open(contract_path, encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("ts_code") and "." in str(existing["ts_code"]):
                code = existing["ts_code"]
        except Exception:
            pass
    # Fallback: apply market suffix heuristics (same as analyze.sh)
    if "." not in code:
        if len(code) <= 5 and code.startswith("0"):
            code = code + ".HK"
        elif code.startswith("6"):
            code = code + ".SH"
        elif code.startswith("0") or code.startswith("3"):
            code = code + ".SZ"

    if os.path.exists(contract_path):
        ensured_tracking = _ensure_contract_tracking_metadata(
            contract_path,
            report_type=report_type,
            fiscal_year=fiscal_year,
            period_end=period_end,
        )
        if ensured_tracking:
            report_type = ensured_tracking.get('report_type') or report_type
            fiscal_year = ensured_tracking.get('fiscal_year') if ensured_tracking.get('fiscal_year') is not None else fiscal_year
            period_end = ensured_tracking.get('period_end') or period_end

    # V12: 统一模式自动切换模板
    is_v12 = unified or qualitative_only
    if is_v12 and template_path == "templates/report_template_v10.md":
        template_path = "templates/report_template_v12.md"

    start_time = time.time()
    run_id = f"{code}_{int(start_time * 1000)}_{os.getpid()}"
    source_deepening = bool(unified) if source_deepening is None else bool(source_deepening)
    diagnostics: dict[str, Any] = {
        "run_id": run_id,
        "code": code,
        "output_dir": output_dir,
        "template_path": template_path,
        "mode": "pit_production_freeze" if pit_production_freeze else "qualitative_only" if qualitative_only else "unified" if unified else "classic",
        "analysis_purpose": analysis_purpose,
        "skip_prepare": skip_prepare,
        "dry_run": dry_run,
        "provider": provider,
        "model": model,
        "data_source": data_source or None,
        "price_source": price_source or None,
        "report_type": _normalize_tracking_report_type(report_type),
        "fiscal_year": _safe_int(fiscal_year),
        "period_end": str(period_end or "").strip()[:10] or None,
        "validation_only": bool(validation_only),
        "approve_expensive_run": bool(approve_expensive_run),
        "repair_passes_requested": max(0, int(repair_passes)),
        "repair_max_iterations": max(1, int(repair_max_iterations)),
        "chapter_attempts_per_pass": max(1, int(chapter_attempts_per_pass)),
        "repair_chapters": list(repair_chapters),
        "review_return": str(Path(review_return).expanduser().resolve()) if review_return else None,
        "source_deepening": bool(source_deepening),
        "started_at": _utc_now_iso(),
        "status": "running",
        "phases": [],
    }
    pit_runner = None
    company_judgment_predecessor: dict[str, Any] | None = None
    canonical_judgment_binding: dict[str, Any] | None = None
    pit_attestation_path = ""
    if pit_mode:
        try:
            try:
                from scripts.phase10_pit_runner import PITSourcePackage
            except ModuleNotFoundError:
                # ``python scripts/turtle_agent/run.py`` puts scripts/ (not
                # the repository root) on sys.path.  PIT preflight is a
                # supported CLI path, so retain the package import for module
                # callers and the sibling import for direct CLI callers.
                from phase10_pit_runner import PITSourcePackage
            manifest_path = Path(pit_source_manifest).expanduser().resolve()
            manifest = _load_json_file(str(manifest_path))
            if manifest.get("company_code") != code:
                raise RuntimeError(
                    f"PIT source manifest company_code={manifest.get('company_code')!r} 与 code={code!r} 不一致"
                )
            pit_runner = PITSourcePackage(
                manifest,
                pit_package_root,
                case_id=pit_case_id or None,
                experiment_id=pit_experiment_id or None,
                run_id=run_id,
                manifest_path=str(manifest_path),
            )
        except (OSError, ValueError, ImportError) as exc:
            raise RuntimeError(f"PIT source-package 初始化失败: {exc}") from exc
        if pit_runner.state != "REVIEWABLE":
            raise RuntimeError(
                "PIT source-package 未通过准入: "
                + json.dumps({"state": pit_runner.state, "invalid": pit_runner.invalid_findings, "incomplete": pit_runner.incomplete_findings}, ensure_ascii=False)
            )
        diagnostics["pit_mode"] = True
        diagnostics["pit_source_manifest"] = str(manifest_path)
        diagnostics["pit_package_root"] = str(Path(pit_package_root).expanduser().resolve())
        diagnostics["pit_framework_root"] = str(_PIT_FRAMEWORK_ROOT.resolve())
        diagnostics["pit_framework_root_class"] = "REPOSITORY_STATIC"
        if pit_production_freeze and analysis_purpose == "INVESTMENT_DECISION":
            if str(frozen_cjo or "").strip() or str(current_company_cjo_admission or "").strip():
                canonical_judgment_binding = _load_episode_bound_current_company_judgment(
                    frozen_cjo,
                    current_company_cjo_admission,
                    company_code=code,
                    cutoff_at=str(pit_runner.cutoff_at),
                )
                diagnostics["enterprise_underwriting_binding"] = {
                    key: value
                    for key, value in canonical_judgment_binding.items()
                    if not key.endswith("_path")
                }
            else:
                company_judgment_predecessor = _load_company_judgment_predecessor(
                    company_judgment_snapshot, company_code=code, cutoff_at=str(pit_runner.cutoff_at),
                )
                predecessor_findings = _investment_predecessor_findings(
                    company_judgment_predecessor,
                    company_code=code,
                    cutoff_at=str(pit_runner.cutoff_at),
                )
                if predecessor_findings:
                    raise RuntimeError(
                        "投资 PIT 生产冻结的公司判断前置物未达到 INVESTMENT_READY: "
                        + ", ".join(predecessor_findings)
                    )
                diagnostics["company_judgment_predecessor"] = {
                    key: value for key, value in (company_judgment_predecessor.get("source") or {}).items()
                    if key != "snapshot_path"
                }
        if pit_writer:
            return _run_pit_writer(
                code=code,
                output_dir=output_dir,
                model=model,
                max_iterations=max_iterations,
                pit_runner=pit_runner,
                pit_case_id=pit_case_id,
                pit_experiment_id=pit_experiment_id,
                diagnostics=diagnostics,
            )
    try:
        from scripts.runtime_governance import RuntimeController
    except ModuleNotFoundError:
        from runtime_governance import RuntimeController
    runtime = RuntimeController(
        output_dir=output_dir,
        run_id=run_id,
        company_code=code,
        period=str(period_end or (f"FY{fiscal_year}" if fiscal_year else "UNSPECIFIED")),
        mode=diagnostics["mode"],
        template_path=template_path,
    )
    diagnostics["run_manifest_path"] = str(runtime.manifest.path)
    if pit_mode and pit_production_freeze:
        try:
            report_path = _run_pit_production_freeze(
                code=code, output_dir=output_dir, model=model, max_iterations=max_iterations,
                pit_runner=pit_runner, pit_case_id=pit_case_id, pit_experiment_id=pit_experiment_id,
                runtime=runtime, diagnostics=diagnostics, analysis_purpose=analysis_purpose,
                company_judgment_predecessor=company_judgment_predecessor,
                canonical_judgment_binding=canonical_judgment_binding,
            )
            production_completion = _validate_pit_production_completion(
                output_dir=output_dir, report_path=report_path, run_id=run_id,
                analysis_purpose=analysis_purpose,
            )
            runtime.manifest.add_artifact(report_path, "pit_production_report")
            runtime.manifest.add_artifact(production_completion["publication_snapshot_path"], "publication_snapshot")
            runtime.manifest.record_step(
                "pit_production_freeze", "COMPLETED", **production_completion,
            )
            diagnostics.update({"status": "completed", "report_path": report_path, **production_completion})
            diagnostics_path = _write_diagnostics(output_dir, diagnostics)
            runtime.manifest.add_artifact(diagnostics_path, "diagnostics")

            from scripts.real_report_acceptance import evaluate_phase10_production_freeze_acceptance
            acceptance_root = Path(output_dir) / "phase10_acceptance"
            acceptance = evaluate_phase10_production_freeze_acceptance(
                sample_id=pit_case_id,
                company_code=code,
                output_dir=output_dir,
                report_period="PIT-" + str(pit_runner.cutoff_at)[:10],
                acceptance_root=acceptance_root,
            )
            acceptance_sample = (acceptance.get("samples") or [{}])[0]
            acceptance_status = str(acceptance_sample.get("machine_status") or "")
            diagnostics["phase10_acceptance"] = {
                "root": str(acceptance_root),
                "machine_status": acceptance_status,
            }
            acceptance_baseline = acceptance_root / "acceptance_baseline.json"
            runtime.manifest.add_artifact(acceptance_baseline, "phase10_production_acceptance")
            if acceptance_status not in {
                "READY_FOR_BLIND_REVIEW", "BENCHMARK_CANDIDATE", "BENCHMARK_APPROVED",
            }:
                raise RuntimeError(
                    "PIT production report was not ready at the independent Phase 10 acceptance gate: "
                    + (acceptance_status or "MISSING")
                )
            _write_diagnostics(output_dir, diagnostics)
            runtime.manifest.finalize("COMPLETED", publication={"status": "PUBLISHED", "validation_only": False})
            return report_path
        except Exception as exc:
            diagnostics["status"] = "blocked"
            diagnostics["error"] = str(exc)
            diagnostics_path = _write_diagnostics(output_dir, diagnostics)
            try:
                runtime.manifest.add_error("pit_production_freeze", str(exc))
                runtime.manifest.add_artifact(diagnostics_path, "diagnostics")
                runtime.manifest.finalize("BLOCKED", publication={"status": "NOT_PUBLISHED", "validation_only": False})
            except Exception:
                pass
            raise
    report_path = ""

    def _run_phase_tracked(phase_name: str, phase_code: str, phase_target_code: str, **phase_kwargs: Any) -> dict[str, Any]:
        phase_started = time.time()
        try:
            result = _run_phase(phase_code, phase_target_code, output_dir, **phase_kwargs)
        except Exception as exc:
            diagnostics["phases"].append({
                "phase": phase_name,
                "phase_code": phase_code,
                "started_at": _utc_now_iso(),
                "duration_sec": round(time.time() - phase_started, 3),
                "ok": False,
                "error": str(exc),
            })
            runtime.manifest.record_step(
                phase_name, "FAILED", phase_code=phase_code, duration_sec=round(time.time() - phase_started, 3),
                error=str(exc),
            )
            raise
        diagnostics["phases"].append({
            "phase": phase_name,
            "phase_code": phase_code,
            "started_at": _utc_now_iso(),
            "duration_sec": round(time.time() - phase_started, 3),
            "ok": bool(result.get("ok", True)) if isinstance(result, dict) else True,
            "summary": _summarize_phase_result(result if isinstance(result, dict) else {}),
        })
        phase_ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
        runtime.manifest.record_step(
            phase_name,
            "COMPLETED" if phase_ok else "WARN",
            phase_code=phase_code,
            duration_sec=round(time.time() - phase_started, 3),
            summary=_summarize_phase_result(result if isinstance(result, dict) else {}),
        )
        return result

    print(f"\n{'='*60}")
    print(f"🐢 Turtle {'V12' if is_v12 else 'V11'} 全流程分析: {code}")
    print(f"   输出: {output_dir}")
    print(f"   模板: {template_path}")
    if unified:
        print(f"   模式: Dayu定性 + Turtle定量 → 15章统一报告")
    elif qualitative_only:
        print(f"   模式: Dayu定性(Ch1-9) + 摘要提取")
    if dry_run:
        print(f"   ⚠️ 干跑模式 (仅 Python 计算)")
    if data_source:
        print(f"   财务来源: {data_source}")
    if price_source:
        print(f"   交易价格来源: {price_source}")
    print(f"   报告口径: {_REPORT_TYPE_LABELS.get(_normalize_tracking_report_type(report_type), '年报')}")
    if fiscal_year:
        print(f"   财年: {fiscal_year}")
    if period_end:
        print(f"   截止日: {str(period_end)[:10]}")
    print(f"{'='*60}\n")

    try:
        # V12.19: 卫星标的 — 提前写入 DB，让所有 Phase 自动生效
        if data_source:
            _ensure_data_source_code(code, data_source)

        # ---- Phase 0-2: 数据准备 ----
        contract_path = os.path.join(output_dir, "analysis_contract.json")
    
        # LlmClient 提前初始化（Phase 2.3-2.4 + Agent Loop 共用）
        # analyze.sh 会注入 DEEPSEEK_API_KEY；这里优先用它，避免被失效的 ANTHROPIC_API_KEY 抢占。
        deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        llm = None
        if deepseek_api_key or anthropic_api_key:
            from turtle_agent.llm_client import LlmClient as _LlmClient
            if deepseek_api_key:
                llm = _LlmClient(
                    provider="deepseek_oa", model="deepseek-v4-pro",
                    timeout_seconds=int(runtime.config["timeout_seconds"]), runtime_controller=runtime,
                )
            else:
                llm = _LlmClient(
                    provider="anthropic", model=model,
                    timeout_seconds=int(runtime.config["timeout_seconds"]), runtime_controller=runtime,
                )

        if llm and not dry_run:
            try:
                from scripts.run_budget_guard import build_run_preflight
            except ModuleNotFoundError:
                from run_budget_guard import build_run_preflight
            preflight = build_run_preflight(
                output_dir=output_dir,
                max_iterations=max_iterations,
                repair_passes=repair_passes if unified else 0,
                repair_max_iterations=repair_max_iterations,
                repair_only=repair_only,
                dry_run=dry_run,
                approved=approve_expensive_run,
                policy=runtime.config.get("execution_guard") or {},
            )
            preflight_path = os.path.join(output_dir, "run_budget_preflight.json")
            _write_json_file(preflight_path, preflight)
            diagnostics["budget_preflight"] = preflight
            runtime.manifest.add_artifact(preflight_path, "budget_preflight")
            if preflight["status"] == "APPROVAL_REQUIRED":
                estimate = preflight["estimate"]
                raise RuntimeError(
                    "真实运行预算预检需要显式批准："
                    f"上限约 {estimate['max_llm_calls']} 次 LLM 调用 / "
                    f"{estimate['estimated_wall_minutes']} 分钟；"
                    "确认后添加 --approve-expensive-run"
                )

        if not skip_prepare:
            print("━" * 40)
            print("📊 Phase 0-2: 数据准备")
            print("━" * 40)
    
            # Phase 0
            print("\n[Phase 0] 前置诊断...")
            pa = _run_phase_tracked(
                "Phase 0 前置诊断",
                "pre_analysis",
                code,
                report_type=report_type,
                fiscal_year=fiscal_year,
                period_end=period_end,
            )
            if not pa.get("ok"):
                raise RuntimeError(f"Phase 0 失败: {pa.get('error')}")
            asset_profile = _get_asset_profile(contract_path)
            diagnostics["asset_profile"] = asset_profile
            print(f"  ✅ 有效窗口: {pa.get('effective_years')} ({pa.get('cycle_type')})")
    
            # Phase 0.5 — 年报PDF
            print("\n[Phase 0.5] 年报下载...")
            # V12.19: 卫星标的用母标代码下载年报（同一公司，只是用母标代码搜cninfo）
            download_code = data_source if data_source else code
            code_short = download_code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
            if data_source:
                print(f"  🔗 卫星标的，用母标 {data_source} 下载年报")
            chk = _run_phase_tracked("Phase 0.5 完整性检查", "check", code_short)
            if chk.get("complete"):
                print("  ✅ 年报完整")
            else:
                missing_str = chk.get("missing", "")
                print(f"  ⚠️ 缺失: {missing_str}, 仅下载缺失年份...")
                dl = _run_phase_tracked("Phase 0.5 年报下载", "download", code_short, missing_years=missing_str)
                downloaded = dl.get("downloaded", 0)
                failed = dl.get("failed", 0)
                errors = dl.get("errors")
                pre_ipo = dl.get("pre_ipo_skipped", [])
                if pre_ipo:
                    print(f"  ℹ️ 跳过IPO前年份: {pre_ipo}")
                if dl.get("ok") and not errors:
                    print(f"  ✅ 年报完整 ({downloaded} 份新下载)")
                elif errors:
                    print(f"  ⚠️ 部分成功: {downloaded} ok, {failed} failed")
                    for e in (errors if isinstance(errors, list) else list(errors.items())[:3]):
                        print(f"     {e}")

            # Phase 1
            print("\n[Phase 1] 定量计算...")
            cb = _run_phase_tracked(
                "Phase 1 定量计算",
                "compute",
                code,
                data_source=data_source,
                price_source=price_source,
            )
            if not cb.get("ok"):
                raise RuntimeError(f"Phase 1 失败: {cb.get('error')}")
            gg = cb.get("gg", {})
            if cb.get("quantitative_status") == "UNRESOLVED_CURRENT_MARKET":
                print("  ⚠️ 当前报价不可用：继续企业研究，估值与价格动作暂不承保")
            else:
                print(f"  ✅ GG(base)={gg.get('base', '?')}%, DDM={cb.get('ddm', {}).get('fair_value', '?')}")
    
            # Phase 1.5: 财务趋势 + 行业上下文
            print("\n[Phase 1.5] 财务趋势 & 行业上下文...")
            ft = _run_phase_tracked("Phase 1.5 财务趋势", "financial_trends", code)
            if ft.get("ok"):
                print(f"  ✅ financial_trends.json")
            else:
                print(f"  ⚠️ financial_trends: {ft.get('error', 'unknown')}")
    
            ic = _run_phase_tracked("Phase 1.5 行业上下文", "industry_context", code)
            if ic.get("ok"):
                cpeers = ic.get("comparable_peers", [])
                peers = len(cpeers) if isinstance(cpeers, list) else cpeers
                print(f"  ✅ industry_context.json ({peers} 同行)")
            else:
                print(f"  ⚠️ industry_context: {ic.get('error', 'unknown')}")
    
            # Phase 2: 数据打包 + 定性提取（5 步流水线）
            pdfs = [f for f in os.listdir(output_dir) if f.endswith(".pdf") and "年报" in f]
            pdf_years = []
            for pdf_file in pdfs:
                try:
                    parts = pdf_file.replace(".pdf", "").split("_")
                    yr = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                    if yr:
                        pdf_years.append((yr, pdf_file))
                except (ValueError, IndexError):
                    pass
            pdf_years.sort()
    
            # Phase 2.1: PDF → 结构化文本 + 全量 Markdown（纯 Python）
            print("\n[Phase 2.1] PDF 内容提取 + Markdown 转换...")
            md_ok_count = 0
            for year, pdf_file in pdf_years:
                pdf_path = os.path.join(output_dir, pdf_file)
                # 2.1a: pdf_sections (财务数字 regex 提取)
                r = _run_phase_tracked(f"Phase 2.1 PDF预处理 FY{year}", "pdf_preprocessor", "", pdf_path=pdf_path, year=year)
                sec_info = f"{r.get('sections_found', 0)}/{r.get('sections_total', 10)} sections" if r.get("ok") else "skip"
                # 2.1b: 全量 markdown
                md = _run_phase_tracked(f"Phase 2.1 PDF转Markdown FY{year}", "pdf_to_markdown", "", pdf_path=pdf_path, year=year)
                if md.get("skipped"):
                    print(f"  ⏭ {pdf_file} ({sec_info}, md 已有)")
                    md_ok_count += 1
                elif md.get("ok"):
                    kb = md.get("size", 0) // 1024
                    print(f"  ✅ {pdf_file} ({sec_info} + {year}_年报.md {kb}K, {md.get('pages', 0)} 页)")
                    md_ok_count += 1
                else:
                    print(f"  ⚠️ {pdf_file}: {md.get('error', 'unknown')}")
    
            # Phase 2.2 (build_full_text) + 2.5 (page_map) 已跳过 — markdown 替代两者
    
            # Phase 2.3-2.4: Zone B LLM 提取（从 markdown，需要 API key）
            if llm and md_ok_count > 0:
                print("\n[Phase 2.3] Zone B 年度 LLM 提取 (从 markdown)...")
                zy = _run_phase_tracked("Phase 2.3 Zone B 年度提取", "zone_b_years", code, llm_client=llm)
                if zy.get("ok"):
                    if zy.get("degraded"):
                        print(
                            f"  ⚠️ Zone B 局部完成：成功 {zy.get('years_succeeded', [])}，"
                            f"失败 {zy.get('failed_years', [])}；缺失年份只降低对应比较置信度"
                        )
                    else:
                        print(f"  ✅ {zy.get('years_processed')} 年处理完成 (跳过 {zy.get('years_skipped', 0)}, 并行 LLM)")
                else:
                    print(f"  ⚠️ zone_b years: {zy.get('error', 'unknown')}")
                    if zy.get("errors"):
                        for e in zy["errors"][:3]:
                            print(f"     - FY{e.get('year', '?')}: {e.get('error', '?')[:80]}")
    
                if zy.get("ok"):
                    print("\n[Phase 2.4] Zone B Master 汇总 (zone_b_v8 master)...")
                    zm = _run_phase_tracked("Phase 2.4 Zone B 汇总", "zone_b_master", code, llm_client=llm)
                    if zm.get("skipped"):
                        print(f"  ⏭ 所有 Zone B 文件已存在")
                    elif zm.get("ok"):
                        print(f"  ✅ Zone B JSON: {zm.get('files_written')}")
                    else:
                        print(f"  ⚠️ zone_b master: {zm.get('error', 'unknown')}")
            elif not llm:
                print("\n[Phase 2.3-2.4] ⏭ Zone B LLM 提取跳过 (无 API key)")

            # Phase 3: Zone J 判断参数提取（4 LLM agents, 并行）
            if llm:
                print("\n[Phase 3] Zone J 判断参数提取 (4 agents 并行)...")
                zj = _run_phase_tracked("Phase 3 Zone J", "zone_j", code, llm_client=llm)
                if zj.get("ok"):
                    print(f"  ✅ Zone J 参数提取完成")
                else:
                    print(f"  ⚠️ Zone J: {zj.get('error', 'unknown')}")
    
                # Phase 3.5: 用 Zone J 参数重新计算 compute_bundle
                print("\n[Phase 3.5] 用 Zone J 参数重算 compute_bundle...")
                cb2 = _run_phase_tracked(
                    "Phase 3.5 Zone J 重算",
                    "compute",
                    code,
                    data_source=data_source,
                    price_source=price_source,
                )
                if cb2.get("ok"):
                    gg2 = cb2.get("gg", {})
                    ddm2 = cb2.get("ddm", {})
                    gg_disc = cb2.get("gg_discounted", {})
                    if gg_disc and gg_disc.get("base"):
                        print(f"  ✅ GG(Zone J)={gg2.get('base', '?')}%, 折价后GG={gg_disc.get('base')}%, DDM={ddm2.get('fair_value', '?')}")
                    else:
                        print(f"  ✅ GG(Zone J)={gg2.get('base', '?')}%, DDM={ddm2.get('fair_value', '?')}")
                else:
                    print(f"  ⚠️ compute re-run: {cb2.get('error', 'unknown')}")
            elif not llm:
                print("\n[Phase 3] ⏭ Zone J 跳过 (无 API key)")
    
        # ---- Agent Loop ----
        if dry_run:
            print(f"\n⏭ 干跑模式: 跳过 Agent Loop")
            report_path = os.path.join(output_dir, f"{code}_V12_DRY_RUN.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"# {code} {'V12' if is_v12 else 'V11'} 干跑报告\n\nPhase 0-2 数据准备已完成。\n跳过 LLM 分析。\n")
            report_path = _materialize_tracking_outputs(
                output_dir, report_path, diagnostics, validation_only=validation_only
            )
            diagnostics['status'] = 'completed'
            diagnostics['report_path'] = report_path
            return report_path
    
        if unified:
            try:
                from scripts.build_report_context import build_official_evidence_bundle
            except ModuleNotFoundError:
                from build_report_context import build_official_evidence_bundle
            evidence_bundle = build_official_evidence_bundle(
                output_dir,
                code,
                persist=True,
                run_id=run_id,
                enforced=True,
            )
            evidence_state = evidence_bundle["context"]["validation"]["state"]
            evidence_coverage = evidence_bundle["context"]["coverage"]
            print(
                "\n[Phase 3.8] 官方证据平台: "
                f"{evidence_state}, VERIFIED="
                f"{evidence_coverage.get('observation_counts', {}).get('VERIFIED', 0)}, "
                f"domains={len(evidence_coverage.get('verified_domains', []))}"
            )
            if os.path.isfile(os.path.join(output_dir, "publication_snapshot.json")):
                try:
                    from scripts.research_monitoring import auto_monitor_latest_disclosure
                except ModuleNotFoundError:
                    from research_monitoring import auto_monitor_latest_disclosure
                monitoring_update = auto_monitor_latest_disclosure(output_dir)
                print(
                    "[Phase 3.81] 发布后监控: "
                    f"{monitoring_update.get('state') or ('RECORDED' if monitoring_update.get('written') else 'INCOMPLETE')}"
                )
            try:
                from scripts.valuation_routing import (
                    build_company_archetype, build_valuation_route,
                    initialize_valuation_route_policy,
                )
            except ModuleNotFoundError:
                from valuation_routing import (
                    build_company_archetype, build_valuation_route,
                    initialize_valuation_route_policy,
                )
            company_archetype = build_company_archetype(output_dir, persist=True)
            valuation_route = build_valuation_route(
                output_dir, company_archetype, persist=True
            )
            initialize_valuation_route_policy(
                output_dir, run_id=run_id, enforced=True
            )
            print(
                "[Phase 3.85] 行业原型与估值路由: "
                f"{valuation_route['validation']['state']}, "
                f"archetype={valuation_route.get('archetype_id')}, "
                f"primary={len([m for m in valuation_route.get('models', []) if m.get('role') == 'primary'])}"
            )
            try:
                from scripts.decisive_question import refresh_decisive_question_plan
            except ModuleNotFoundError:
                from decisive_question import refresh_decisive_question_plan
            decisive_refresh = refresh_decisive_question_plan(
                output_dir,
                run_id=run_id,
                enforced=True,
            )
            # The calculation registry also contains decisive-plan identities.
            # Refreshing the plan changes their input fingerprint, so rebuild
            # CALC identities afterwards (and deterministically rebind any
            # reviewable claim ledger) rather than leaving it stale until the
            # next run.
            try:
                from scripts.computation_evidence import build_calculation_observations
            except ModuleNotFoundError:
                from computation_evidence import build_calculation_observations
            calculation_refresh = build_calculation_observations(
                output_dir, persist=True
            )
            if (calculation_refresh.get("claim_rebinding") or {}).get("updated"):
                print("  ↪ 已随决定性问题指纹更新确定性重绑 reviewable CALC 引用")
            decisive_plan = decisive_refresh["plan"]
            decisive_rebind = decisive_refresh.get("findings_rebind") or {}
            if decisive_rebind.get("rebound"):
                print("  ↪ 已确定性重绑兼容的决定性问题 findings 指纹")
            if not decisive_refresh.get("refreshed"):
                print("  ⛔ 决定性问题语义已变；保留旧plan并落盘candidate，等待重新研究")
            try:
                from scripts.base_rate_case_library import initialize_base_rate_policy
            except ModuleNotFoundError:
                from base_rate_case_library import initialize_base_rate_policy
            initialize_base_rate_policy(output_dir, run_id=run_id, enforced=True)
            print(
                "[Phase 3.9] 决定性问题引擎: "
                f"{decisive_plan['validation']['state']}, selected="
                f"{len(decisive_plan.get('selected_questions') or [])}"
            )
            industry_knowledge = decisive_plan.get("industry_knowledge_context") or {}
            matched_mechanisms = industry_knowledge.get("matched_mechanisms") or []
            ready_mechanisms = [
                item for item in matched_mechanisms
                if isinstance(item, dict) and item.get("status") == "MECHANISM_READY"
            ]
            print(
                "[Phase 3.87] 行业知识取证路由: "
                f"{industry_knowledge.get('validation_status') or 'UNAVAILABLE'}, "
                f"matched={len(matched_mechanisms)}, ready_questions={len(ready_mechanisms)} "
                "(仅生成本公司验证问题，不作为估值或行动输入)"
            )
            try:
                from scripts.decision_ledger import initialize_decision_ledger_policy
            except ModuleNotFoundError:
                from decision_ledger import initialize_decision_ledger_policy
            initialize_decision_ledger_policy(
                output_dir,
                run_id=run_id,
                enforced=True,
            )
            try:
                from scripts.decision_compiler import initialize_decision_compiler_policy
            except ModuleNotFoundError:
                from decision_compiler import initialize_decision_compiler_policy
            initialize_decision_compiler_policy(
                output_dir,
                run_id=run_id,
                enforced=True,
            )
            try:
                from scripts.claim_evidence import initialize_claim_evidence_policy
            except ModuleNotFoundError:
                from claim_evidence import initialize_claim_evidence_policy
            initialize_claim_evidence_policy(
                output_dir,
                run_id=run_id,
                enforced=True,
            )
            try:
                from scripts.valuation_model_gate import initialize_valuation_model_policy
            except ModuleNotFoundError:
                from valuation_model_gate import initialize_valuation_model_policy
            prior_valuation_policy = _load_json_file(
                os.path.join(output_dir, "valuation_model_policy.json")
            )
            initialize_valuation_model_policy(
                output_dir,
                run_id=run_id,
                enforced=True,
                require_normalization_bridge=bool(
                    prior_valuation_policy.get("require_normalization_bridge")
                ),
                require_decay_treatment=bool(
                    prior_valuation_policy.get("require_decay_treatment")
                ),
                require_owner_earnings_normalization=bool(
                    prior_valuation_policy.get("require_owner_earnings_normalization")
                ),
                require_holding_period_return_bridge=bool(
                    prior_valuation_policy.get("require_holding_period_return_bridge")
                ),
                require_value_bridge_models=bool(
                    prior_valuation_policy.get("require_value_bridge_models", True)
                ),
                require_value_bridge_fact_bindings=bool(
                    prior_valuation_policy.get(
                        "require_value_bridge_fact_bindings", True
                    )
                ),
            )
            try:
                from scripts.decision_reliability import initialize_decision_reliability_policy
            except ModuleNotFoundError:
                from decision_reliability import initialize_decision_reliability_policy
            initialize_decision_reliability_policy(output_dir, run_id=run_id, enforced=True)
            try:
                from scripts.financial_driver_bridge import initialize_financial_driver_bridge_policy
            except ModuleNotFoundError:
                from financial_driver_bridge import initialize_financial_driver_bridge_policy
            initialize_financial_driver_bridge_policy(output_dir, run_id=run_id, enforced=True)
            if os.path.isfile(os.path.join(output_dir, "valuation_model.json")):
                try:
                    from scripts.valuation_model_migration import (
                        migrate_valuation_model, promote_valuation_model_migration,
                    )
                except ModuleNotFoundError:
                    from valuation_model_migration import (
                        migrate_valuation_model, promote_valuation_model_migration,
                    )
                valuation_migration = migrate_valuation_model(output_dir, persist=True)
                valuation_migration_report = valuation_migration.get("report") or {}
                if (
                    not valuation_migration_report.get("semantic_frontier")
                    and valuation_migration_report.get("migration_required")
                ):
                    valuation_promotion = promote_valuation_model_migration(output_dir)
                    if valuation_promotion.get("promoted"):
                        print("  ↪ 已确定性迁移兼容的估值路由身份；估值与动作未变")
                elif valuation_migration_report.get("semantic_frontier"):
                    print(
                        "  ⛔ 估值路由存在语义变更；保留旧账本并落盘candidate，"
                        "等待定向估值研究"
                    )
            try:
                from scripts.thesis_test_gate import initialize_thesis_test_policy
            except ModuleNotFoundError:
                from thesis_test_gate import initialize_thesis_test_policy
            initialize_thesis_test_policy(
                output_dir, run_id=run_id, enforced=True, monitoring_required=True,
                forward_judgment_required=True,
                rival_hypothesis_pair_required=not os.path.isfile(
                    os.path.join(output_dir, "thesis_test.json")
                ),
            )
            if os.path.isfile(os.path.join(output_dir, "thesis_test.json")):
                try:
                    from scripts.thesis_test_migration import (
                        migrate_thesis_test, promote_thesis_test_migration,
                    )
                except ModuleNotFoundError:
                    from thesis_test_migration import (
                        migrate_thesis_test, promote_thesis_test_migration,
                    )
                valuation_state = str(
                    (_load_json_file(os.path.join(output_dir, "valuation_model_validation.json")) or {}).get("state")
                    or ""
                ).upper()
                if valuation_state in {"DECISION_READY", "MONITORING"}:
                    thesis_migration = migrate_thesis_test(output_dir, persist=True)
                    thesis_migration_report = thesis_migration.get("report") or {}
                    if thesis_migration_report.get("semantic_frontier"):
                        print(
                            "  ⛔ thesis迁移存在语义或非截止日缺口；保留旧账本与candidate，"
                            "等待定向研究"
                        )
                    elif thesis_migration_report.get("migration_required"):
                        thesis_promotion = promote_thesis_test_migration(output_dir)
                        if thesis_promotion.get("promoted"):
                            print("  ↪ 已确定性补齐thesis监测截止日；概率、阈值与动作未变")
            try:
                from scripts.insight_ledger import initialize_insight_policy
            except ModuleNotFoundError:
                from insight_ledger import initialize_insight_policy
            initialize_insight_policy(output_dir, run_id=run_id, enforced=True)

            learning_admission = _refresh_report_learning_admissions(output_dir)
            print(
                "[Phase 3.97] 判断学习准入: "
                f"{learning_admission.get('state') or 'UNAVAILABLE'}, "
                f"selected={int(learning_admission.get('selected_count') or 0)}"
            )

        from turtle_agent.tool_registry import ToolRegistry
        from turtle_agent.agent_loop import TurtleAgent, AgentConfig
    
        # 自动发现工具（每次 run 重新注册，~0.1秒，可接受）
        tools = ToolRegistry()
        modules = ["turtle_agent.tools.pit_read_tools"] if pit_runner else [
            "turtle_agent.tools.read_tools",
            "turtle_agent.tools.calc_tools",
            "turtle_agent.tools.technical_tools",
            "turtle_agent.tools.write_tools",
            "turtle_agent.tools.phase_tools",
            "turtle_agent.tools.search_tools",
            "turtle_agent.tools.browser_tools",
        ]
        if pit_runner:
            from turtle_agent.tools.pit_read_tools import configure_pit_runner
            configure_pit_runner(pit_runner)
        for mod in modules:
            n = tools.auto_discover(mod)
    
        diagnostics['tools'] = tools.list_tools()
        diagnostics['tool_count'] = len(tools)
        if not pit_runner:
            runtime.refresh_input_fingerprints(template_path)
        if pit_runner:
            pit_attestation_path = str(Path(output_dir) / "pit_runner_attestation.json")
            _write_json_file(pit_attestation_path, pit_runner.attestation())
            diagnostics["pit_attestation_path"] = pit_attestation_path
            _write_diagnostics(output_dir, diagnostics)
            print("PIT preflight 通过；已注册工具: " + ", ".join(diagnostics["tools"]))
            from turtle_agent.tools.pit_read_tools import clear_pit_runner
            clear_pit_runner()
            return pit_attestation_path
        if review_return_payload and not llm:
            route_path = os.path.join(output_dir, "golden_report_feedback_routing.json")
            if max(0, int(repair_passes)) == 0:
                diagnostics["status"] = "completed"
                diagnostics["report_path"] = route_path
                diagnostics["agent_mode"] = "review_route_only"
                return route_path
            if initial_route.get("status") == "UPSTREAM_REPAIR_REQUIRED":
                diagnostics["status"] = "blocked"
                diagnostics["feedback_route"] = initial_route
                raise RuntimeError(
                    "Golden Report 存在未验收的上游问题；已生成责任路由，"
                    "reader writer 未启动"
                )
            raise RuntimeError(
                "Golden Report 读者修订需要已配置的模型；"
                "可用 --repair-passes 0 只生成责任路由"
            )
        if llm:
            # 复用 Phase 2 创建的 LlmClient → 运行完整 Agent Loop
            print(f"\n{'━'*40}")
            print(f"🤖 {'V12' if is_v12 else 'V11'} Agent Loop — 全自动模式")
            print(f"   Provider: {llm._provider} / {llm.model}")
            print(f"━'*40")
    
            start_time = time.time()
            try:
                completion: dict[str, Any] = (
                    _completion_with_review_return(
                        _load_completion_report(output_dir), review_return_payload,
                    )
                    if repair_only else {}
                )
                agent_passes: list[dict[str, Any]] = []
                try:
                    from scripts.run_budget_guard import NoProgressCircuitBreaker
                except ModuleNotFoundError:
                    from run_budget_guard import NoProgressCircuitBreaker
                progress_guard = NoProgressCircuitBreaker(
                    max_no_progress_passes=int(
                        (runtime.config.get("execution_guard") or {}).get("max_no_progress_passes", 2)
                    )
                )
                if completion:
                    progress_guard.observe(completion.get("blocking_findings", []))

                def _drain_judgment_research() -> bool:
                    """Run each queued task in its own TurtleAgent context.

                    ACTIVE state survives exceptions.  A later process invocation
                    selects it before any full-report pass, so quota recovery never
                    replays company analysis or completed research tasks.
                    """
                    try:
                        from scripts.judgment_research_resume import (
                            judgment_task_iteration_budget,
                            next_judgment_research_pass,
                        )
                    except ModuleNotFoundError:
                        from judgment_research_resume import (
                            judgment_task_iteration_budget,
                            next_judgment_research_pass,
                        )
                    ran_any = False
                    while True:
                        task_context = next_judgment_research_pass(output_dir)
                        if not task_context:
                            return ran_any
                        ran_any = True
                        task_id = str(task_context["task_id"])
                        scope = task_context.get("task", {}).get("mutation_scope") or {}
                        targets = tuple(int(idx) for idx in scope.get("chapters") or [])
                        attempts = max(1, int(judgment_task_retries) + 1)
                        last_error = ""
                        for attempt in range(1, attempts + 1):
                            # Re-read on every attempt: the first attempt may have
                            # consumed tools before an API/quota interruption.
                            task_context = next_judgment_research_pass(output_dir)
                            if not task_context or str(task_context.get("task_id")) != task_id:
                                break
                            resume = bool(task_context.get("resume"))
                            label = f"judgment-{task_id.lower()}-attempt-{attempt}"
                            print(f"\n{'━'*40}")
                            print(
                                f"🔎 定向研究 {task_id} — fresh context "
                                f"({'断点续跑' if resume else '新任务'})"
                            )
                            print(
                                "   剩余工具预算: "
                                f"{task_context.get('remaining_tool_calls', 0)}；"
                                "剩余必需工具: "
                                + ", ".join(task_context.get("remaining_required_tools") or ["无"])
                            )
                            print(f"{'━'*40}")
                            config = AgentConfig(
                                code=code,
                                contract_path=contract_path,
                                output_dir=output_dir,
                                max_iterations=judgment_task_iteration_budget(
                                    task_context, judgment_task_max_iterations
                                ),
                                max_chapter_attempts_per_pass=max(1, int(chapter_attempts_per_pass)),
                                template_path=template_path,
                                pass_name=label,
                                repair_targets=targets,
                                source_deepening=False,
                                publish_downstream=False,
                                run_id=run_id,
                                judgment_task_id=task_id,
                                judgment_task_resume=resume,
                            )
                            task_agent = TurtleAgent(llm=llm, tools=tools, config=config)
                            pass_started = time.time()
                            try:
                                task_path = task_agent.analyze()
                                last_error = ""
                            except RuntimeError as exc:
                                last_error = str(exc)
                                task_path = str(Path(output_dir) / "judgment_research_execution.json")
                            task_state = _load_json_file(
                                os.path.join(output_dir, "judgment_research_execution.json")
                            )
                            entry = ((task_state.get("tasks") or {}).get(task_id) or {})
                            task_status = str(entry.get("status") or "PENDING")
                            agent_passes.append({
                                "pass": label,
                                "judgment_task_id": task_id,
                                "resume": resume,
                                "max_iterations": config.max_iterations,
                                "iterations_used": task_agent._iterations,
                                "run_metrics": task_agent.run_metrics(),
                                "duration_sec": round(time.time() - pass_started, 3),
                                "status": task_status,
                                "report_path": task_path,
                                "pass_error": last_error,
                            })
                            if task_status == "COMPLETE":
                                break
                            if task_status == "VIOLATION":
                                raise RuntimeError(last_error or f"定向研究任务 {task_id} 违反执行契约")
                            structured_stop = _structured_context_stop_reason(task_agent)
                            if structured_stop:
                                # A tool-level circuit breaker is a framework
                                # stop, not a transient context interruption.
                                # Propagate it to the real-run boundary instead
                                # of silently opening another paid context.
                                raise RuntimeError(structured_stop)
                            if attempt < attempts:
                                print("  ↪ 调用中断；断点已落盘，改用另一 fresh context 续跑。")
                        else:
                            pass
                        refreshed = next_judgment_research_pass(output_dir)
                        if refreshed and str(refreshed.get("task_id")) == task_id:
                            raise RuntimeError(
                                last_error or f"定向研究任务 {task_id} 重试预算耗尽；ACTIVE断点已保留"
                            )

                def _ensure_judgment_synthesis_review() -> bool:
                    """Run a separate challenger context after all task contexts."""
                    plan = _load_json_file(os.path.join(output_dir, "judgment_research_plan.json"))
                    policy = plan.get("execution_policy") or {}
                    execution = _load_json_file(
                        os.path.join(output_dir, "judgment_research_execution.json")
                    )
                    has_structured_findings = any(
                        isinstance(entry, dict) and bool(entry.get("finding"))
                        for entry in (execution.get("tasks") or {}).values()
                    )
                    if not policy.get("independent_synthesis_context") and not has_structured_findings:
                        return False
                    if execution.get("state") != "COMPLETE":
                        return False
                    try:
                        from scripts.judgment_research_synthesis import build_judgment_research_synthesis
                    except ModuleNotFoundError:
                        from judgment_research_synthesis import build_judgment_research_synthesis
                    synthesis = _load_json_file(
                        os.path.join(output_dir, "judgment_research_synthesis.json")
                    ) or build_judgment_research_synthesis(output_dir, persist=True)
                    state = str(synthesis.get("state") or "INVALID")
                    if state == "REVIEWED":
                        return False
                    if state != "AWAITING_INDEPENDENT_REVIEW":
                        raise RuntimeError(f"定向研究综合账本不可复核: {state}")
                    last_error = ""
                    for attempt in range(1, max(1, int(judgment_task_retries) + 1) + 1):
                        label = f"judgment-synthesis-attempt-{attempt}"
                        print(f"\n{'━'*40}")
                        print("🧭 定向研究独立综合 — fresh challenger context")
                        print(f"{'━'*40}")
                        config = AgentConfig(
                            code=code,
                            contract_path=contract_path,
                            output_dir=output_dir,
                            max_iterations=max(2, min(3, int(judgment_task_max_iterations))),
                            max_tokens_per_call=12000,
                            template_path=template_path,
                            pass_name=label,
                            source_deepening=False,
                            publish_downstream=False,
                            run_id=run_id,
                            judgment_synthesis=True,
                        )
                        review_agent = TurtleAgent(llm=llm, tools=tools, config=config)
                        pass_started = time.time()
                        try:
                            synthesis_path = review_agent.analyze()
                            last_error = ""
                        except RuntimeError as exc:
                            last_error = str(exc)
                            synthesis_path = str(Path(output_dir) / "judgment_research_synthesis.json")
                        refreshed = _load_json_file(synthesis_path)
                        review_state = str(refreshed.get("state") or "AWAITING_INDEPENDENT_REVIEW")
                        agent_passes.append({
                            "pass": label,
                            "judgment_synthesis": True,
                            "max_iterations": config.max_iterations,
                            "iterations_used": review_agent._iterations,
                            "run_metrics": review_agent.run_metrics(),
                            "duration_sec": round(time.time() - pass_started, 3),
                            "status": review_state,
                            "report_path": synthesis_path,
                            "pass_error": last_error,
                        })
                        if review_state == "REVIEWED":
                            return True
                        if attempt <= int(judgment_task_retries):
                            print("  ↪ 独立综合调用中断；保留finding账本并用新上下文续跑。")
                    raise RuntimeError(last_error or "定向研究独立综合重试预算耗尽")

                # A restarted process must resume the compact task ledger before
                # opening any full-company build/repair context.
                existing_execution = _load_json_file(
                    os.path.join(output_dir, "judgment_research_execution.json")
                )
                if existing_execution.get("state") == "VIOLATION":
                    raise RuntimeError(
                        "定向研究执行账本存在VIOLATION；必须修复执行契约，禁止回退到全文重跑"
                    )
                resumed_existing_queue = _drain_judgment_research()
                resumed_existing_synthesis = _ensure_judgment_synthesis_review()
                resumed_existing_work = resumed_existing_queue or resumed_existing_synthesis
                if resumed_existing_work:
                    from turtle_agent.tools.write_tools import assemble_report as _assemble_after_judgment
                    assembled = _assemble_after_judgment(
                        output_dir=output_dir,
                        company_name="",
                        ts_code=code,
                        validation_only=validation_only,
                    )
                    report_path = str(assembled.get("path") or "")
                    completion = _load_completion_report(output_dir)
                requested_repairs = (
                    max(0, int(repair_passes))
                    if unified or review_return_payload else 0
                )
                explicit_repairs = tuple(dict.fromkeys(
                    int(idx) for idx in repair_chapters if 0 <= int(idx) <= 14
                ))
                zero_pass_revalidated = False
                if _requires_zero_pass_revalidation(
                    repair_only=repair_only,
                    requested_repairs=requested_repairs,
                    explicit_repairs=explicit_repairs,
                ):
                    # Phase initializers may have refreshed policies, evidence
                    # identities, or structured fingerprints after the previous
                    # completion report was written.  With no model passes
                    # requested, the only truthful operation is a fresh local
                    # assembly/evaluation; reading the stale completion file can
                    # incorrectly fail (or incorrectly pass) the run.
                    from turtle_agent.tools.write_tools import assemble_report as _assemble_zero_pass
                    assembled = _assemble_zero_pass(
                        output_dir=output_dir,
                        company_name="",
                        ts_code=code,
                        validation_only=validation_only,
                    )
                    report_path = str(assembled.get("path") or report_path)
                    completion = (
                        assembled.get("completion")
                        if isinstance(assembled.get("completion"), dict)
                        else _load_completion_report(output_dir)
                    )
                    zero_pass_revalidated = True
                already_validated_repair = bool(
                    repair_only
                    and not completion.get("blocking_findings")
                    and not explicit_repairs
                    and completion.get("status") in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}
                )
                if (
                    repair_only
                    and not completion.get("blocking_findings")
                    and not explicit_repairs
                    and not zero_pass_revalidated
                ):
                    if not already_validated_repair:
                        raise RuntimeError("--repair-only 需要现有 BLOCKED 或已通过的 completion_report.json")
                    # Idempotent zero-model closeout: a prior interrupted run may
                    # have completed deterministic validation after its manifest
                    # was already marked INCOMPLETE.  Reassemble locally so a new
                    # run can truthfully finish with a COMPLETED manifest.
                    from turtle_agent.tools.write_tools import assemble_report as _assemble_validated_repair
                    assembled = _assemble_validated_repair(
                        output_dir=output_dir,
                        company_name="",
                        ts_code=code,
                        validation_only=validation_only,
                    )
                    report_path = str(assembled.get("path") or report_path)
                    completion = (
                        assembled.get("completion")
                        if isinstance(assembled.get("completion"), dict)
                        else _load_completion_report(output_dir)
                    )
                    # Enabling a newer policy/route can invalidate a completion
                    # report that was valid when the previous run ended.  The
                    # deterministic closeout above is the source of truth: only
                    # keep the zero-model path when that *fresh* result still
                    # passes.  Otherwise schedule the normal bounded repair
                    # passes instead of silently finishing with zero LLM calls.
                    already_validated_repair = bool(
                        not completion.get("blocking_findings")
                        and completion.get("status")
                        in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}
                    )
                    if already_validated_repair:
                        print("  ✅ completion已通过；零模型幂等validation-only收口。")
                    else:
                        print("  ↪ 新契约重验发现阻断；进入有界 repair-only 修复轮。")
                if review_return_payload:
                    feedback_status = _feedback_route_from_completion(completion).get("status")
                    total_passes = (
                        1
                        if requested_repairs > 0 and feedback_status in {
                            "UPSTREAM_REPAIR_REQUIRED", "READER_REPAIR_READY",
                        }
                        else 0
                    )
                else:
                    total_passes = (
                        _scheduled_repair_passes(
                            completion,
                            requested=requested_repairs,
                            resumed_existing_work=resumed_existing_work,
                        )
                        if repair_only
                        else (0 if resumed_existing_work else 1 + requested_repairs)
                    )
                for loop_index in range(total_passes):
                    repair_targets: tuple[int, ...] = ()
                    feedback_route: dict[str, Any] = {}
                    repair_round = loop_index + 1 if repair_only else loop_index
                    if repair_round:
                        refreshed = (
                            None
                            if review_return_payload
                            else _repair_stale_decision_bindings_before_model(
                                output_dir,
                                code=code,
                                validation_only=validation_only,
                            )
                        )
                        if refreshed is not None:
                            completion = refreshed
                        completion = _completion_with_review_return(
                            completion, review_return_payload,
                        )
                        if not explicit_repairs:
                            feedback_route = _feedback_route_from_completion(completion)
                        repair_targets = (
                            _explicit_repair_targets_for_pass(
                                explicit_repairs,
                                repair_round,
                                requested_repairs,
                            )
                            if explicit_repairs else
                            _repair_targets_for_pass(
                                completion,
                                repair_round,
                                requested_repairs,
                            )
                        )
                        if not repair_targets:
                            if feedback_route.get("status") == "UPSTREAM_REPAIR_REQUIRED":
                                owners = [
                                    str(item.get("owner") or "")
                                    for item in feedback_route.get("execution_queue") or []
                                    if isinstance(item, dict) and item.get("owner") != "READER_WRITER"
                                ]
                                owner_text = ", ".join(dict.fromkeys(owners)) or "UPSTREAM"
                                diagnostics["status"] = "blocked"
                                diagnostics["feedback_route"] = feedback_route
                                raise RuntimeError(
                                    "Golden Report 存在未验收的上游问题；读者报告保持不变，"
                                    "先完成责任层修复: " + owner_text
                                )
                            break
                        print(f"\n{'━'*40}")
                        print(f"🔧 自动质量修复轮 {repair_round}/{requested_repairs} — fresh context")
                        print("   目标章节: " + ", ".join(f"Ch{i}" for i in repair_targets))
                        print(f"{'━'*40}")

                    pass_label = "build" if not repair_round else f"repair-{repair_round}"
                    pass_iterations = (
                        max_iterations
                        if not repair_round
                        else _repair_iteration_budget(repair_targets, repair_max_iterations)
                    )
                    binding_only = bool(
                        repair_round
                        and not explicit_repairs
                        and not feedback_route.get("reader_repair_brief")
                        and _is_binding_only_repair(completion)
                    )
                    if binding_only:
                        # A clerical binding pass needs read/patch/validate turns,
                        # not the budget of a fresh research chapter.
                        pass_iterations = min(pass_iterations, 8 + 2 * len(repair_targets))
                        from scripts.decision_ledger import repair_chapter_decision_references
                        from turtle_agent.tools.write_tools import assemble_report as _assemble_binding_repair
                        ledger = _load_json_file(
                            os.path.join(output_dir, "decision_ledger.json")
                        )
                        deterministic_started = time.time()
                        deterministic = repair_chapter_decision_references(
                            output_dir,
                            ledger,
                            chapters=repair_targets,
                        )
                        assembled_binding = _assemble_binding_repair(
                            output_dir=output_dir,
                            company_name="",
                            ts_code=code,
                            validation_only=validation_only,
                        )
                        report_path = str(assembled_binding.get("path") or report_path)
                        completion = (
                            assembled_binding.get("completion")
                            if isinstance(assembled_binding.get("completion"), dict)
                            else _load_completion_report(output_dir)
                        )
                        remaining_targets = set(_repair_targets_from_completion(completion))
                        unresolved_current = tuple(
                            idx for idx in repair_targets if idx in remaining_targets
                        )
                        print(
                            "  🧷 确定性绑定修复: removed="
                            f"{deterministic.get('removed_invalid_anchors', 0)}, inserted="
                            f"{deterministic.get('anchors_inserted', 0)}, remaining="
                            + (", ".join(f"Ch{idx}" for idx in unresolved_current) or "none")
                        )
                        if not unresolved_current:
                            progress = progress_guard.observe(
                                completion.get("blocking_findings", [])
                            )
                            agent_passes.append({
                                "pass": pass_label + "-deterministic-binding",
                                "repair_targets": list(repair_targets),
                                "max_iterations": 0,
                                "iterations_used": 0,
                                "run_metrics": {"usage": {"calls": 0}},
                                "duration_sec": round(time.time() - deterministic_started, 3),
                                "status": completion.get("status", "INCOMPLETE"),
                                "blocking_findings": completion.get("blocking_findings", []),
                                "report_path": report_path,
                                "progress": progress,
                                "deterministic_binding": deterministic,
                                "resource_efficiency": {
                                    "llm_calls": 0,
                                    "uncached_input_tokens": 0,
                                    "duration_sec": round(time.time() - deterministic_started, 3),
                                    "blockers_resolved": progress["resolved_count"],
                                    "estimated_cost_usd": 0.0,
                                    "calls_per_resolved_blocker": 0.0,
                                },
                            })
                            if progress["tripped"]:
                                raise RuntimeError(
                                    "确定性binding修复后阻断集合无进展；必须离线修复，禁止付费重试"
                                )
                            if completion.get("status") in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
                                break
                            continue
                        repair_targets = unresolved_current
                    config = AgentConfig(
                        code=code,
                        contract_path=contract_path,
                        output_dir=output_dir,
                        max_iterations=pass_iterations,
                        max_chapter_attempts_per_pass=max(1, int(chapter_attempts_per_pass)),
                        template_path=template_path,
                        pass_name=pass_label,
                        repair_targets=repair_targets,
                        reader_repair_brief=list(
                            feedback_route.get("reader_repair_brief") or []
                        ),
                        source_deepening=(
                            bool(source_deepening)
                            and not binding_only
                            and not feedback_route.get("reader_repair_brief")
                        ),
                        binding_only=binding_only,
                        publish_downstream=not validation_only,
                        run_id=run_id,
                        synthesis_only=(
                            False
                            if feedback_route.get("reader_repair_brief")
                            else _should_use_synthesis_only(
                                output_dir,
                                repair_targets,
                                binding_only=binding_only,
                                completion=completion,
                            )
                        ),
                    )
                    agent = TurtleAgent(llm=llm, tools=tools, config=config)
                    pass_started = time.time()
                    usage_before = dict(runtime.manifest.data.get("usage") or {})
                    pass_error = ""
                    try:
                        report_path = agent.analyze()
                        ran_judgment_tasks = _drain_judgment_research()
                        ran_judgment_review = _ensure_judgment_synthesis_review()
                        if ran_judgment_tasks or ran_judgment_review:
                            from turtle_agent.tools.write_tools import assemble_report as _assemble_after_judgment
                            assembled = _assemble_after_judgment(
                                output_dir=output_dir,
                                company_name="",
                                ts_code=code,
                                validation_only=validation_only,
                            )
                            report_path = str(assembled.get("path") or report_path)
                        completion = _load_completion_report(output_dir)
                    except RuntimeError as exc:
                        if "来源驱动深化未覆盖全部目标章节" not in str(exc):
                            raise
                        pass_error = str(exc)
                        completion = _refresh_completion_after_incomplete_source_pass(output_dir)
                        report_path = str(Path(output_dir) / "reports" / "drafts" / f"{code.split('.')[0]}_分析报告_v13_draft.md")
                        print("  ↪ 本轮来源深化预算耗尽；已刷新完成契约，继续下一 fresh-context 修复轮。")
                    status = completion.get('status', 'INCOMPLETE')
                    progress = progress_guard.observe(completion.get("blocking_findings", []))
                    usage_after = dict(runtime.manifest.data.get("usage") or {})
                    pass_calls = int(usage_after.get("calls", 0) or 0) - int(usage_before.get("calls", 0) or 0)
                    pass_uncached = int(usage_after.get("uncached_input_tokens", 0) or 0) - int(
                        usage_before.get("uncached_input_tokens", 0) or 0
                    )
                    cost_before = usage_before.get("estimated_cost_usd")
                    cost_after = usage_after.get("estimated_cost_usd")
                    pass_cost = (
                        round(float(cost_after or 0.0) - float(cost_before or 0.0), 8)
                        if cost_before is not None and cost_after is not None else None
                    )
                    resource_efficiency = {
                        "llm_calls": pass_calls,
                        "uncached_input_tokens": pass_uncached,
                        "duration_sec": round(time.time() - pass_started, 3),
                        "blockers_resolved": progress["resolved_count"],
                        "estimated_cost_usd": pass_cost,
                        "calls_per_resolved_blocker": (
                            round(pass_calls / progress["resolved_count"], 2)
                            if progress["resolved_count"] else None
                        ),
                    }
                    agent_passes.append({
                        "pass": pass_label,
                        "repair_targets": list(repair_targets),
                        "max_iterations": pass_iterations,
                        "iterations_used": agent._iterations,
                        "run_metrics": agent.run_metrics(),
                        "duration_sec": round(time.time() - pass_started, 3),
                        "status": status,
                        "blocking_findings": completion.get("blocking_findings", []),
                        "report_path": report_path,
                        "pass_error": pass_error,
                        "progress": progress,
                        "resource_efficiency": resource_efficiency,
                    })
                    if progress["tripped"]:
                        diagnostics["status"] = "blocked"
                        diagnostics["circuit_breaker"] = "no_progress"
                        runtime.manifest.add_error(
                            "no_progress_circuit_breaker",
                            "blocking findings unchanged across repair passes",
                        )
                        raise RuntimeError(
                            "连续修复轮未减少任何阻断项；无进展熔断已停止真实运行，"
                            "必须离线修复框架后再重跑"
                        )
                    if status in {'COMPLETE', 'COMPLETE_WITH_WARNINGS'} and (
                        not explicit_repairs or loop_index >= total_passes - 1
                    ):
                        break

                diagnostics['agent_passes'] = agent_passes
                status = completion.get('status', 'INCOMPLETE') if isinstance(completion, dict) else 'INCOMPLETE'
                elapsed = time.time() - start_time
                print(f"\n{'='*60}")
                if status in {'COMPLETE', 'COMPLETE_WITH_WARNINGS'}:
                    print(f"✅ 分析完成 ({elapsed:.0f}s)")
                else:
                    print(f"❌ 分析未通过完成契约 ({elapsed:.0f}s) — {status}")
                print(f"📄 {report_path}")
                print(f"{'='*60}\n")
                diagnostics['report_path'] = report_path
                diagnostics['agent_mode'] = 'auto'
                if status not in {'COMPLETE', 'COMPLETE_WITH_WARNINGS'}:
                    diagnostics['status'] = 'blocked'
                    diagnostics['blocking_findings'] = completion.get('blocking_findings', []) if isinstance(completion, dict) else []
                    diagnostics['draft_path'] = report_path
                    raise RuntimeError(f'分析未通过完成契约: {status}')
                _extract_tracking_meta_from_report(output_dir, report_path)
                report_path = _materialize_tracking_outputs(
                    output_dir, report_path, diagnostics, validation_only=validation_only
                )
                diagnostics['status'] = 'completed'
                diagnostics['report_path'] = report_path
                return report_path
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"\n❌ Agent Loop 失败 ({elapsed:.0f}s): {e}")
                import traceback
                traceback.print_exc()
                if diagnostics.get('status') != 'blocked':
                    diagnostics['status'] = 'failed'
                diagnostics['error'] = str(e)
                diagnostics['agent_mode'] = 'auto'
                raise RuntimeError(f"Agent Loop 失败: {e}") from e
        else:
            # 无 API key → Claude Code 模式：生成 prompt 文件
            print(f"\n{'━'*40}")
            print(f"🤖 {'V12' if is_v12 else 'V11'} Agent — Prompt 生成模式")
            print(f"   (设置 DEEPSEEK_API_KEY 或 ANTHROPIC_API_KEY 环境变量以启用全自动模式)")
            print(f"━'*40")
    
            config = AgentConfig(
                code=code,
                contract_path=contract_path,
                output_dir=output_dir,
                max_iterations=max_iterations,
                template_path=template_path,
            )
            agent = TurtleAgent(llm=None, tools=tools, config=config)
            agent._load_context()
    
            qual_info = ""
            if agent._context.get("qualitative_summary"):
                qual_info = " (含定性摘要)"
            print(f"  📖 上下文: {len(agent._context)} 项{qual_info}")
    
            system_prompt = agent._build_system_prompt()
    
            fname = "_v12_system_prompt.md" if is_v12 else "_v11_system_prompt.md"
            prompt_path = os.path.join(output_dir, fname)
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(system_prompt)
    
            tool_path = os.path.join(output_dir, "_v12_tools.json" if is_v12 else "_v11_tools.json")
            with open(tool_path, "w", encoding="utf-8") as f:
                json.dump(tools.get_anthropic_schemas(), f, ensure_ascii=False, indent=2)
    
            print(f"  📄 System Prompt → {prompt_path} ({len(system_prompt):,} chars)")
            print(f"  🔧 Tool Schemas  → {tool_path} ({len(tools)} tools)")
    
            report_path = _materialize_tracking_outputs(
                output_dir, prompt_path, diagnostics, validation_only=validation_only
            )
            diagnostics['status'] = 'completed'
            diagnostics['report_path'] = report_path
            diagnostics['agent_mode'] = 'prompt_only'
            return report_path
    except Exception as exc:
        if diagnostics.get('status') != 'blocked':
            diagnostics['status'] = 'failed'
        diagnostics['error'] = str(exc)
        raise
    finally:
        diagnostics['completed_at'] = _utc_now_iso()
        diagnostics['elapsed_sec'] = round(time.time() - start_time, 3)
        if report_path:
            diagnostics['report_path'] = report_path
        diagnostics_path = _write_diagnostics(output_dir, diagnostics)
        print(f"  🩺 diagnostics → {diagnostics_path}")
        try:
            runtime.manifest.add_artifact(diagnostics_path, "diagnostics")
            if report_path:
                runtime.manifest.add_artifact(report_path, "report_or_draft")
            runtime_status = {
                "completed": "COMPLETED",
                "blocked": "BLOCKED",
                "failed": "FAILED",
                "running": "INCOMPLETE",
            }.get(str(diagnostics.get("status") or "").lower(), "INCOMPLETE")
            if any(item.get("category") == "budget_exhausted" for item in runtime.manifest.data.get("errors", [])):
                runtime_status = "INCOMPLETE"
            runtime.manifest.finalize(
                runtime_status,
                publication={
                    "status": "PUBLISHED" if runtime_status == "COMPLETED" and not validation_only else
                    "VALIDATED_NOT_PUBLISHED" if runtime_status == "COMPLETED" else "NOT_PUBLISHED",
                    "validation_only": bool(validation_only),
                },
            )
        except Exception as manifest_exc:
            print(f"  ⚠️ runtime manifest 收口失败: {manifest_exc}")


# ===================================================================
# Phase 执行器
# ===================================================================


def _ensure_data_source_code(ts_code: str, data_source: str) -> None:
    """V12.19: 确保 stocks.data_source_code 已写入。如果 stock 不存在则自动创建。"""
    import sqlite3

    def _infer_listing_profile(code: str) -> tuple[str, str]:
        code = str(code or "").upper()
        if code.endswith(".HK"):
            return "HKD", "HK"
        if code.endswith(".DE"):
            return "EUR", "DE"
        if code.endswith(".SZ") and code.startswith("200"):
            return "HKD", "B"
        if code.endswith(".SH") and code.startswith("900"):
            return "USD", "B"
        if code.endswith(".US"):
            return "USD", "US"
        return "RMB", "A"

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "stock_analysis.db")
    if not os.path.exists(db_path):
        db_path = "stock_analysis.db"
        if not os.path.exists(db_path):
            return
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT ts_code, data_source_code FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()
        inferred_currency, inferred_market = _infer_listing_profile(ts_code)
        if row is None:
            # Auto-create stock entry: copy name/shares/industry from data_source
            src = conn.execute("SELECT name_cn, shares_m, currency, market, industry FROM stocks WHERE ts_code=?",
                               (data_source,)).fetchone()
            if src:
                name = (src["name_cn"] or ts_code) + "B"
                shares = src["shares_m"]
            else:
                name = ts_code
                shares = None
                print(f"  ⚠️  母标 {data_source} 也不在 stocks 表中，请先导入财务数据")
            conn.execute(
                "INSERT INTO stocks (ts_code, name_cn, shares_m, currency, market, data_source_code) VALUES (?,?,?,?,?,?)",
                (ts_code, name, shares, inferred_currency, inferred_market, data_source)
            )
            conn.commit()
            print(f"  ✅ {ts_code} ({name}) 已创建 → 母标 {data_source}（{inferred_currency} {inferred_market}股）")
        else:
            existing = row["data_source_code"]
            stock_row = conn.execute(
                "SELECT currency, market FROM stocks WHERE ts_code=?",
                (ts_code,),
            ).fetchone()
            if stock_row and (
                (stock_row["currency"] or "").upper() != inferred_currency
                or (stock_row["market"] or "").upper() != inferred_market
            ):
                conn.execute(
                    "UPDATE stocks SET currency=?, market=? WHERE ts_code=?",
                    (inferred_currency, inferred_market, ts_code),
                )
                conn.commit()
                print(f"  🔧 {ts_code} 交易币种已校正为 {inferred_currency}，市场类型校正为 {inferred_market}")
            if existing and existing != data_source:
                print(f"  ⚠️  {ts_code} data_source_code 已是 {existing}，忽略 --data-source {data_source}")
            elif not existing:
                conn.execute("UPDATE stocks SET data_source_code=? WHERE ts_code=?", (data_source, ts_code))
                conn.commit()
                print(f"  🔗 {ts_code} → {data_source}（已写入 stocks.data_source_code）")
    except sqlite3.OperationalError as e:
        print(f"  ⚠️  data_source_code 写入失败: {e}")
    finally:
        conn.close()


def _run_phase(
    phase: str,
    code: str,
    output_dir: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """执行单个 Phase。"""
    if phase == "pre_analysis":
        from turtle_agent.tools.phase_tools import run_pre_analysis
        return run_pre_analysis(
            code=code,
            output_dir=output_dir,
            report_type=kwargs.get("report_type", "annual"),
            fiscal_year=kwargs.get("fiscal_year"),
            period_end=kwargs.get("period_end", ""),
        )

    elif phase == "check":
        from turtle_agent.tools.phase_tools import check_report_completeness
        return check_report_completeness(code=code, save_dir=output_dir)

    elif phase == "download":
        from turtle_agent.tools.phase_tools import download_annual_reports
        return download_annual_reports(code=code, save_dir=output_dir, missing_years=kwargs.get("missing_years", ""))

    elif phase == "compute":
        from turtle_agent.tools.phase_tools import compute_bundle_db
        return compute_bundle_db(
            code=code,
            output_dir=output_dir,
            data_source=kwargs.get("data_source", ""),
            price_source=kwargs.get("price_source", ""),
        )

    elif phase == "financial_trends":
        from turtle_agent.tools.phase_tools import build_financial_trends
        return build_financial_trends(code=code, output_dir=output_dir)

    elif phase == "industry_context":
        from turtle_agent.tools.phase_tools import build_industry_context
        return build_industry_context(code=code, output_dir=output_dir)

    elif phase == "technical_snapshot":
        from turtle_agent.tools.technical_tools import build_technical_snapshot
        return build_technical_snapshot(output_dir=output_dir, ts_code=code)

    elif phase == "extract_pdf":
        from turtle_agent.tools.phase_tools import extract_pdf_sections
        return extract_pdf_sections(
            pdf_path=kwargs.get("pdf_path", ""),
            output_dir=output_dir,
            year=kwargs.get("year", 0),
        )

    elif phase == "pdf_preprocessor":
        from turtle_agent.tools.phase_tools import run_pdf_preprocessor
        return run_pdf_preprocessor(
            pdf_path=kwargs.get("pdf_path", ""),
            output_dir=output_dir,
            year=kwargs.get("year", 0),
        )

    elif phase == "pdf_to_markdown":
        from turtle_agent.tools.phase_tools import pdf_to_markdown
        return pdf_to_markdown(
            pdf_path=kwargs.get("pdf_path", ""),
            output_dir=output_dir,
            year=kwargs.get("year", 0),
        )

    elif phase == "build_full_text":
        from turtle_agent.tools.phase_tools import build_full_text_phase
        return build_full_text_phase(stock_dir=output_dir, ts_code=code)

    elif phase == "zone_b_years":
        from turtle_agent.tools.phase_tools import extract_zone_b_years
        return extract_zone_b_years(
            stock_dir=output_dir,
            ts_code=code,
            llm_client=kwargs.get("llm_client"),
        )

    elif phase == "zone_b_master":
        from turtle_agent.tools.phase_tools import extract_zone_b_master
        return extract_zone_b_master(
            ts_code=code,
            stock_dir=output_dir,
            llm_client=kwargs.get("llm_client"),
        )

    elif phase == "zone_j":
        from turtle_agent.tools.phase_tools import extract_zone_j
        return extract_zone_j(
            ts_code=code,
            stock_dir=output_dir,
            llm_client=kwargs.get("llm_client"),
        )

    elif phase == "verify":
        from turtle_agent.tools.phase_tools import verify_report
        return verify_report(
            report_path=kwargs.get("report_path", ""),
            output_dir=output_dir,
        )

    return {"ok": False, "error": f"未知 Phase: {phase}"}


# ===================================================================
# CLI
# ===================================================================


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Turtle V12 — 全流程分析 (单Agent)")
    ap.add_argument("--code", required=True, help="股票代码")
    ap.add_argument("--output", default="", help="输出目录")
    ap.add_argument("--skip-prepare", action="store_true", help="跳过Phase 0/0.5/1/2")
    ap.add_argument("--dry-run", action="store_true", help="仅Python计算，不调LLM")
    ap.add_argument("--model", default="claude-sonnet-4-20250514")
    ap.add_argument("--max-iter", type=int, default=80, help="首轮 Agent 最大迭代次数（默认80）")
    ap.add_argument("--repair-passes", type=int, default=6,
                    help="unified 首轮后自动 fresh-context 分批修复轮数（默认6，末轮专用于综合账本）")
    ap.add_argument("--repair-max-iter", type=int, default=40,
                    help="每个自动修复轮最大迭代次数（默认40）")
    ap.add_argument("--judgment-task-retries", type=int, default=2,
                    help="每个定向研究任务中断后的fresh-context续跑次数（默认2）")
    ap.add_argument("--judgment-task-max-iter", type=int, default=14,
                    help="每个定向研究fresh context最大LLM轮数（默认14，仍受任务工具预算约束）")
    ap.add_argument("--chapter-attempts-per-pass", type=int, default=2,
                    help="每轮单章最大落盘尝试次数，短章也计数（默认2）")
    ap.add_argument("--repair-only", action="store_true",
                    help="跳过首轮全文读取，直接从现有 BLOCKED completion_report 做定向修复")
    ap.add_argument("--repair-chapters", default="",
                    help="显式深化章节，逗号分隔（如 0,1,2,14）；允许对 COMPLETE 报告执行 repair-only")
    ap.add_argument("--review-return", default="",
                    help="结构化 Golden Report 审阅返回；仅与 repair-only 联用并按责任层分流")
    ap.add_argument("--source-deepening", dest="source_deepening", action="store_true",
                    help="来源驱动深化（unified 默认开启）")
    ap.add_argument("--no-source-deepening", dest="source_deepening", action="store_false",
                    help="显式关闭来源深化（仅用于调试/兼容）")
    ap.set_defaults(source_deepening=None)
    ap.add_argument("--template", default="templates/report_template_v10.md")
    # V12 flags
    ap.add_argument("--unified", action="store_true", help="V12: Dayu定性+Turtle定量 → 15章统一报告")
    ap.add_argument("--qualitative-only", action="store_true", help="V12: 仅定性分析(Ch1-9)")
    ap.add_argument("--data-source", type=str, default=None,
                    help="V12.19: 卫星标的 — 指定财务数据来源母标代码")
    ap.add_argument("--price-source", type=str, default=None,
                    help="指定市场价格、市值和仓位计算所用的交易代码")
    ap.add_argument("--report-type", type=str, default="annual",
                    help="报告口径: annual/q1/h1/q3")
    ap.add_argument("--fiscal-year", type=int, default=None,
                    help="报告对应财年，例如 2026")
    ap.add_argument("--period-end", type=str, default="",
                    help="报告截止日，例如 2026-03-31")
    ap.add_argument("--validation-only", action="store_true",
                    help="真实生成并验证报告，但不写入 _niangao 等下游系统")
    ap.add_argument("--approve-expensive-run", action="store_true",
                    help="明确批准超过预检阈值的真实 LLM 运行；仍受硬预算和无进展熔断约束")
    ap.add_argument("--pit-source-manifest", default="",
                    help="P10-A PIT source manifest；启用只读来源包 preflight")
    ap.add_argument("--pit-package-root", default="",
                    help="P10-A PIT 来源包目录；必须是独立历史输入目录")
    ap.add_argument("--pit-framework-root", default="",
                    help="兼容参数；只能是仓库内受控的 P10 PIT framework 根目录")
    ap.add_argument("--pit-case-id", default="", help="P10-A case identity")
    ap.add_argument("--pit-experiment-id", default="", help="P10-A experiment identity")
    ap.add_argument("--pit-preflight", action="store_true",
                    help="仅执行 P10-A PIT 来源包和工具隔离预检，不生成报告")
    ap.add_argument("--pit-writer", action="store_true",
                    help="执行 P10-B PIT 受限 writer，生成草案但不解锁生产回测")
    ap.add_argument("--pit-production-freeze", action="store_true",
                    help="执行 P10 生产冻结：仅PIT读取、完整V3报告出口和独立验收根目录")
    ap.add_argument("--analysis-purpose", default="INVESTMENT_DECISION",
                    choices=["INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"],
                    help="分析用途；CJO 只允许经营机制、前瞻判断与结算，不产生投资决策")
    ap.add_argument("--company-judgment-snapshot", default="",
                    help="Legacy G1J compatibility: same-cutoff CJO publication_snapshot.json")
    ap.add_argument("--frozen-cjo", default="",
                    help="Episode-first investment production: source-bound, independently frozen current-company CJO")
    ap.add_argument("--current-company-cjo-admission", default="",
                    help="Episode-first investment production: PRIMARY_ADMITTED receipt bound to --frozen-cjo")
    args = ap.parse_args(argv)
    try:
        repair_chapters = tuple(
            int(value.strip()) for value in str(args.repair_chapters or "").split(",")
            if value.strip()
        )
    except ValueError as exc:
        ap.error(f"--repair-chapters 必须是0-14的逗号分隔整数: {exc}")
    if any(idx < 0 or idx > 14 for idx in repair_chapters):
        ap.error("--repair-chapters 只允许0-14")

    try:
        report_path = run_full_pipeline(
            code=args.code,
            output_dir=args.output or "",
            skip_prepare=args.skip_prepare,
            dry_run=args.dry_run,
            model=args.model,
            max_iterations=args.max_iter,
            repair_passes=args.repair_passes,
            repair_max_iterations=args.repair_max_iter,
            judgment_task_retries=args.judgment_task_retries,
            judgment_task_max_iterations=args.judgment_task_max_iter,
            chapter_attempts_per_pass=args.chapter_attempts_per_pass,
            repair_only=args.repair_only,
            repair_chapters=repair_chapters,
            source_deepening=args.source_deepening,
            template_path=args.template,
            unified=args.unified,
            qualitative_only=args.qualitative_only,
            data_source=args.data_source or "",
            price_source=args.price_source or "",
            report_type=args.report_type,
            fiscal_year=args.fiscal_year,
            period_end=args.period_end,
            validation_only=args.validation_only,
            approve_expensive_run=args.approve_expensive_run,
            pit_source_manifest=args.pit_source_manifest,
            pit_package_root=args.pit_package_root,
            pit_framework_root=args.pit_framework_root,
            pit_case_id=args.pit_case_id,
            pit_experiment_id=args.pit_experiment_id,
            pit_preflight=args.pit_preflight,
            pit_writer=args.pit_writer,
            pit_production_freeze=args.pit_production_freeze,
            analysis_purpose=args.analysis_purpose,
            company_judgment_snapshot=args.company_judgment_snapshot,
            review_return=args.review_return,
            frozen_cjo=args.frozen_cjo,
            current_company_cjo_admission=args.current_company_cjo_admission,
        )
        print(f"\n📄 {report_path}")
        return 0
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n⏹ 用户中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
