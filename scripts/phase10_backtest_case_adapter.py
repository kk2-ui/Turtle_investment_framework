#!/usr/bin/env python3
"""Build a frozen historical-backtest-case.v2 from one PIT production report.

The production report proves only its own point-in-time boundary.  It cannot
invent a historical case's operating forecast, measurement period, execution
rule, or independent review.  This adapter therefore derives report/source
identity from the completed production artifacts and accepts those investment
judgments only as an explicit, pre-freeze case specification.

It deliberately reads no source-package body, later disclosure, market price,
corporate-action, or benchmark file.  The existing case validator subsequently
replays the production-origin contract before the case is written.  Current
production outputs do not yet expose a historical, source-bound execution
decision contract.  The caller must therefore explicitly preserve an unknown
route, price, and action; the adapter emits no investment decision and fixes
the valuation route and price identity to unknown.  That leaves
operating-forecast settlement available while preventing a return result from
being manufactured.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import historical_backtest
from scripts.historical_backtest import CASE_SCHEMA_VERSION_V2, validate_case
from scripts.metric_reconstruction_contract import contract_findings
from scripts.phase10_acquisition import licensed_industry_series_contract_findings
from scripts.real_report_acceptance import (
    CONFIG_VERSION,
    PHASE10_PRODUCTION_FREEZE_CONFIG_NAME,
    PHASE10_PRODUCTION_FREEZE_PHASE,
    evaluate_phase10_production_freeze_acceptance,
    resolve_report_variant,
)


READY_ACCEPTANCE_STATES = {
    "READY_FOR_BLIND_REVIEW",
    "BENCHMARK_CANDIDATE",
    "BENCHMARK_APPROVED",
}
READY_SNAPSHOT_STATES = {"DECISION_READY", "MONITORING"}
CASE_PURPOSES = {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}
REQUIRED_SNAPSHOT_GATES_BY_PURPOSE = {
    # An investment conclusion still needs its value and action controls.  Do
    # not let a company-learning case profile weaken that requirement.
    "INVESTMENT_DECISION": ("decision", "claim_evidence", "valuation", "thesis_test", "insight"),
    # Company-judgment settlement tests operating mechanisms, not a return or
    # trade.  Evidence, thesis and insight remain mandatory; valuation and
    # decision are deliberately out of scope.
    "COMPANY_JUDGMENT_ONLY": ("claim_evidence", "thesis_test", "insight"),
}
FUTURE_SETTLEMENT_FIELDS = {
    *historical_backtest.LEAKAGE_FIELDS,
    "cash_flows", "corporate_actions", "benchmark_identity",
}
CASE_SPEC_FIELDS = {
    "case_id", "experiment_id", "sample_id", "company_code", "simulation_cutoff", "frozen_at",
    "report_id", "writer_id", "writer_provenance", "review_artifact_path", "route", "forecast",
    "purpose", "inputs", "calibration_ledger", "taxes_fees_fx", "price_identity", "investment_decision",
}
FROZEN_CASE_CONTRACT_FIELDS = (
    "purpose", "route", "forecast", "inputs", "calibration_ledger", "taxes_fees_fx", "price_identity",
)
CJO_FROZEN_REPORT_SECTIONS = (
    "## 公司判断摘要", "## 经营表现与核心驱动", "## 财务表现与资本配置",
    "## 竞争性机制与早期判别信号", "## 监测、结算与再研究", "## 公司判断结论与数据边界",
)
INVESTMENT_FROZEN_REPORT_SECTIONS = (
    "## Evidence", "## Operating forecast", "## Valuation", "## Risks and unknowns", "## Decision",
)
FORWARD_JUDGMENT_LEDGER_SOURCE = "FROZEN_FORWARD_JUDGMENTS"


class ProductionFreezeCaseError(ValueError):
    """Raised when a production report cannot become a frozen v2 case."""


def _root() -> Path:
    # Match the existing historical-case validator, including its test seam.
    return Path(historical_backtest.__file__).resolve().parents[1]


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionFreezeCaseError(f"{label} is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise ProductionFreezeCaseError(f"{label} must be a JSON object: {path}")
    return value


def _repo_path(value: str | Path, label: str) -> tuple[Path, str]:
    root = _root()
    candidate = Path(value).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise ProductionFreezeCaseError(f"{label} must be inside the repository")
    try:
        return resolved, resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ProductionFreezeCaseError(f"{label} must be repository-relative") from exc


def _required(record: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if record.get(field) in (None, "", [], {})]
    if missing:
        raise ProductionFreezeCaseError(label + " missing: " + ", ".join(missing))


def _uses_frozen_forward_judgments(value: Any) -> bool:
    """Return true only for the explicit no-retyping settlement mode."""
    return value == {"source": FORWARD_JUDGMENT_LEDGER_SOURCE}


def _frozen_financial_driver_bridge(
    output: Path, snapshot: dict[str, Any], *, expected_analysis_purpose: str | None = None,
) -> dict[str, Any] | None:
    """Project the exact snapshot-hashed driver bridge for later diagnosis.

    This remains separate from settlement arithmetic.  Its only purpose is to
    preserve the company facts, monitoring contracts, and (where applicable)
    model/decision bindings that existed when a forward judgment was frozen,
    so feedback cannot recreate them after the outcome is known.
    """
    if snapshot.get("financial_driver_bridge_required") is not True:
        return None
    path = output / "financial_driver_bridge.json"
    if not path.is_file():
        raise ProductionFreezeCaseError("production snapshot requires a frozen financial_driver_bridge ledger")
    expected = (snapshot.get("ledger_sha256") or {}).get("financial_driver_bridge")
    if not isinstance(expected, str) or not expected:
        raise ProductionFreezeCaseError("publication snapshot lacks financial_driver_bridge ledger identity")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ProductionFreezeCaseError("frozen financial_driver_bridge differs from publication snapshot")
    bridge = _load_object(path, "frozen financial_driver_bridge ledger")
    if bridge.get("schema_version") != "financial-driver-bridge.v1":
        raise ProductionFreezeCaseError("frozen financial_driver_bridge schema is invalid")
    analysis_purpose = str(bridge.get("analysis_purpose") or "")
    if analysis_purpose not in CASE_PURPOSES:
        raise ProductionFreezeCaseError("frozen financial_driver_bridge analysis_purpose is invalid")
    if expected_analysis_purpose is not None and analysis_purpose != expected_analysis_purpose:
        raise ProductionFreezeCaseError("frozen financial_driver_bridge analysis_purpose does not match case purpose")
    drivers = bridge.get("drivers")
    events = bridge.get("allocation_events")
    if not isinstance(drivers, list) or not isinstance(events, list):
        raise ProductionFreezeCaseError("frozen financial_driver_bridge is structurally incomplete")
    return {
        "schema_version": "frozen-financial-driver-bridge.v1",
        "ledger_sha256": expected,
        "validation_state": "REVIEWABLE",
        "analysis_purpose": analysis_purpose,
        "drivers": deepcopy(drivers),
        "allocation_events": deepcopy(events),
    }


def _forward_judgment_ids(value: Any) -> set[str]:
    """Return explicit forward-judgment references without coercing objects."""
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _financial_driver_bridge_forward_judgment_links(
    bridge: dict[str, Any] | None,
) -> tuple[
    dict[str, set[str]], set[str], dict[str, set[str]], dict[str, dict[str, Any]],
    dict[str, str], dict[str, str],
]:
    """Read the two FDB-to-forward-judgment relationships needed at freeze.

    A driver's ongoing monitoring contract must name the judgment that cites
    that driver.  Allocation realization contracts have no driver-id field on
    the thesis judgment, so their useful invariant is that every named
    judgment survives in the frozen thesis ledger.
    """
    if bridge is None:
        return {}, set(), {}, {}, {}, {}
    driver_links: dict[str, set[str]] = {}
    driver_monitoring_source_types: dict[str, set[str]] = {}
    driver_monitoring_contracts: dict[str, dict[str, Any]] = {}
    driver_layers: dict[str, str] = {}
    cash_normalization_states: dict[str, str] = {}
    for driver in bridge.get("drivers") or []:
        if not isinstance(driver, dict):
            continue
        driver_id = str(driver.get("driver_id") or "").strip()
        monitoring = driver.get("monitoring_contract")
        if not driver_id or not isinstance(monitoring, dict):
            continue
        driver_layers[driver_id] = str(driver.get("layer") or "")
        if driver_layers[driver_id] == "CASH_CONVERSION":
            cash_normalization = driver.get("cash_normalization_contract")
            cash_normalization_states[driver_id] = (
                str(cash_normalization.get("state") or "")
                if isinstance(cash_normalization, dict) else "MISSING"
            )
        driver_links[driver_id] = _forward_judgment_ids(monitoring.get("forward_judgment_ids"))
        driver_monitoring_contracts[driver_id] = deepcopy(monitoring)
        allowed_source_types = monitoring.get("allowed_source_types")
        if isinstance(allowed_source_types, list):
            driver_monitoring_source_types[driver_id] = {
                str(item).strip() for item in allowed_source_types if str(item).strip()
            }
    realization_links: set[str] = set()
    for event in bridge.get("allocation_events") or []:
        if not isinstance(event, dict):
            continue
        realization = event.get("realization_contract")
        if not isinstance(realization, dict):
            continue
        realization_links.update(_forward_judgment_ids(realization.get("forward_judgment_ids")))
        for stage in ("early_signal", "terminal_outcome"):
            stage_contract = realization.get(stage)
            if isinstance(stage_contract, dict):
                realization_links.update(_forward_judgment_ids(stage_contract.get("forward_judgment_ids")))
    return (
        driver_links, realization_links, driver_monitoring_source_types,
        driver_monitoring_contracts, driver_layers, cash_normalization_states,
    )


def _frozen_forward_judgment_ledger(
    output: Path, snapshot: dict[str, Any], sources: list[dict[str, Any]], simulation_cutoff: str,
    *, frozen_financial_driver_bridge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load the exact snapshot-hashed thesis ledger and project its judgments.

    This is intentionally available only after the adapter has established the
    report's admitted PIT sources.  It prevents a caller from replacing the
    report's frozen predictions with a hand-maintained parallel ledger.
    """
    thesis_path = output / "thesis_test.json"
    if not thesis_path.is_file():
        raise ProductionFreezeCaseError("production output has no frozen thesis_test ledger for forward judgment projection")
    expected = (snapshot.get("ledger_sha256") or {}).get("thesis_test")
    if not isinstance(expected, str) or not expected:
        raise ProductionFreezeCaseError("publication snapshot lacks thesis_test ledger identity for forward judgment projection")
    actual = hashlib.sha256(thesis_path.read_bytes()).hexdigest()
    if actual != expected:
        raise ProductionFreezeCaseError("frozen thesis_test ledger differs from publication snapshot")
    (
        driver_links,
        realization_links,
        driver_monitoring_source_types,
        driver_monitoring_contracts,
        driver_layers,
        cash_normalization_states,
    ) = _financial_driver_bridge_forward_judgment_links(
        frozen_financial_driver_bridge,
    )
    known_sources = {
        str(source.get("source_id")): source
        for source in sources
        if isinstance(source, dict) and str(source.get("source_id") or "").strip()
    }
    return build_calibration_ledger_from_forward_judgments(
        _load_object(thesis_path, "frozen thesis_test ledger"),
        simulation_cutoff=simulation_cutoff,
        known_source_ids=set(known_sources),
        known_sources=known_sources,
        known_financial_driver_ids=set(driver_links) if frozen_financial_driver_bridge is not None else None,
        financial_driver_monitoring_links=driver_links if frozen_financial_driver_bridge is not None else None,
        financial_driver_monitoring_source_types=driver_monitoring_source_types if frozen_financial_driver_bridge is not None else None,
        financial_driver_monitoring_contracts=driver_monitoring_contracts if frozen_financial_driver_bridge is not None else None,
        financial_driver_layers=driver_layers if frozen_financial_driver_bridge is not None else None,
        financial_driver_cash_normalization_states=cash_normalization_states if frozen_financial_driver_bridge is not None else None,
        financial_driver_realization_judgment_ids=realization_links if frozen_financial_driver_bridge is not None else None,
    )


def _future_fields(value: Any, *, path: str = "case_spec") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = path + "." + str(key)
            if str(key).lower() in FUTURE_SETTLEMENT_FIELDS:
                findings.append(item_path)
            findings.extend(_future_fields(item, path=item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_future_fields(item, path=f"{path}[{index}]"))
    return findings


def _require_company_judgment_boundary(case_spec: dict[str, Any]) -> None:
    """Freeze an operating-learning case without turning it into a trade."""
    if case_spec.get("purpose") != "COMPANY_JUDGMENT_ONLY":
        raise ProductionFreezeCaseError("current production bridge requires purpose COMPANY_JUDGMENT_ONLY")
    if case_spec.get("route") != "DUAL":
        raise ProductionFreezeCaseError("current production bridge requires route DUAL while the primary route is unknown")
    forecast = case_spec.get("forecast") if isinstance(case_spec.get("forecast"), dict) else {}
    if forecast.get("terminal_handling") != "DUAL_TERMINAL_PATH":
        raise ProductionFreezeCaseError("current production bridge requires DUAL_TERMINAL_PATH while the primary route is unknown")
    price = case_spec.get("price_identity") if isinstance(case_spec.get("price_identity"), dict) else {}
    if (
        price.get("primary_route") != "PRIMARY_ROUTE_UNKNOWN"
        or price.get("primary_price_identity") != "UNKNOWN"
        or price.get("prices") != []
    ):
        raise ProductionFreezeCaseError("current production bridge requires UNKNOWN price identity and no frozen prices")
    if case_spec.get("investment_decision") is not None:
        raise ProductionFreezeCaseError("company-judgment-only production case cannot carry an investment decision")


def _required_snapshot_gates(purpose: str, snapshot: dict[str, Any]) -> tuple[str, ...]:
    """Return the frozen-snapshot controls for the declared analysis purpose."""
    gates = list(REQUIRED_SNAPSHOT_GATES_BY_PURPOSE[purpose])
    if snapshot.get("financial_driver_bridge_required") is True:
        gates.append("financial_driver_bridge")
    return tuple(gates)


def _source_map(
    snapshot: dict[str, Any], source_manifest: dict[str, Any], document_manifest: dict[str, Any], output: Path,
) -> list[dict[str, Any]]:
    if snapshot.get("unresolved_source_ids"):
        raise ProductionFreezeCaseError("publication snapshot contains unresolved source references")
    visible = snapshot.get("visible_information")
    if not isinstance(visible, list) or not visible:
        raise ProductionFreezeCaseError("publication snapshot has no visible PIT sources")
    manifest_sources = {
        str(item.get("source_id") or ""): item
        for item in source_manifest.get("sources") or []
        if isinstance(item, dict) and item.get("source_id")
    }
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(visible):
        if not isinstance(item, dict):
            raise ProductionFreezeCaseError(f"publication snapshot visible_information[{index}] is invalid")
        source_id = str(item.get("source_id") or "").strip()
        if not source_id:
            raise ProductionFreezeCaseError(f"publication snapshot visible_information[{index}] has no source_id")
        if item.get("source_provenance") != "PIT_PROJECTED_AFTER_ALLOW_READ":
            raise ProductionFreezeCaseError("publication snapshot source is not an ALLOW-read PIT projection: " + source_id)
        document_id = str(item.get("evidence_source_id") or "")
        if not document_id.startswith("DOC:"):
            raise ProductionFreezeCaseError("publication snapshot source lacks its V3 document identity: " + source_id)
        source = manifest_sources.get(source_id)
        if source is None:
            raise ProductionFreezeCaseError("visible PIT source is absent from the admitted manifest: " + source_id)
        documents = document_manifest.get("documents") if isinstance(document_manifest.get("documents"), list) else []
        matches = [document for document in documents if isinstance(document, dict) and document.get("doc_id") == document_id]
        if len(matches) != 1:
            raise ProductionFreezeCaseError("publication snapshot V3 document is missing or non-unique: " + document_id)
        document = matches[0]
        if document.get("source_id") != source_id:
            raise ProductionFreezeCaseError("publication snapshot V3 document maps to a different PIT source: " + document_id)
        if document.get("acquisition_status") != "PIT_LINKED_AFTER_ALLOW_READ":
            raise ProductionFreezeCaseError("publication snapshot V3 document was not projected after an ALLOW read: " + document_id)
        local_path = Path(str(document.get("local_path") or ""))
        if not local_path.parts or local_path.is_absolute() or ".." in local_path.parts:
            raise ProductionFreezeCaseError("publication snapshot V3 document projection path is invalid: " + document_id)
        if not (output / local_path).is_file():
            raise ProductionFreezeCaseError("publication snapshot V3 document projection is missing: " + document_id)
        if source_id in seen:
            continue
        seen.add(source_id)
        _required(
            source,
            ("source_id", "source_version", "source_type", "published_at", "data_as_of", "revision_policy"),
            "admitted source " + source_id,
        )
        for field in ("source_version", "published_at", "data_as_of", "revision_policy"):
            if document.get(field) != source.get(field):
                raise ProductionFreezeCaseError("publication snapshot V3 document identity differs from admitted PIT source: " + document_id)
        result.append({
            "source_id": source_id,
            "source_version": source["source_version"],
            "source_type": source["source_type"],
            "published_at": source["published_at"],
            "data_as_of": source["data_as_of"],
            "revision_published_at": source.get("revision_published_at"),
            "revision_policy": source["revision_policy"],
            "admissible": True,
        })
        # Settlement must retain both the independent-data contract and the
        # fact that the source is not official after PIT projection.
        if source.get("source_type") == "LICENSED_INDUSTRY_DATA":
            result[-1]["official"] = source.get("official")
            result[-1]["industry_data_contract"] = deepcopy(source.get("industry_data_contract"))
    return sorted(result, key=lambda item: str(item["source_id"]))


def _review_from_artifact(
    path: Path, *, variant_id: str, report_sha256: str, frozen_case_contract: dict[str, Any],
) -> dict[str, Any]:
    review = _load_object(path, "independent review artifact")
    _required(
        review,
        (
            "reviewed_at", "variant_id", "report_sha256", "reviewer_id", "reviewer_provenance",
            "independence", "status", "claim_reviews", "frozen_case_contract",
        ),
        "independent review artifact",
    )
    if review.get("variant_id") != variant_id:
        raise ProductionFreezeCaseError("independent review artifact variant_id does not match production report")
    if review.get("report_sha256") != report_sha256:
        raise ProductionFreezeCaseError("independent review artifact report_sha256 does not match production report")
    if review.get("frozen_case_contract") != frozen_case_contract:
        raise ProductionFreezeCaseError("independent review frozen contract differs from the case specification")
    claim_reviews = review["claim_reviews"]
    if not isinstance(claim_reviews, list):
        raise ProductionFreezeCaseError("independent review artifact claim_reviews must be a list")
    normalized_reviews: list[dict[str, Any]] = []
    for index, claim_review in enumerate(claim_reviews):
        label = f"independent review artifact claim_reviews[{index}]"
        if not isinstance(claim_review, dict):
            raise ProductionFreezeCaseError(label + " must be an object")
        _required(claim_review, ("claim_id", "disposition", "source_ids", "notes"), label)
        claim_id = str(claim_review["claim_id"])
        normalized_reviews.append({
            "claim_id": claim_id,
            "disposition": claim_review["disposition"],
            "source_ids": deepcopy(claim_review["source_ids"]),
            "notes": deepcopy(claim_review["notes"]),
        })
    return {
        "review_id": "HBTREV:" + variant_id,
        "reviewed_variant_id": variant_id,
        "reviewer_id": review["reviewer_id"],
        "reviewer_provenance": deepcopy(review["reviewer_provenance"]),
        "independence": deepcopy(review["independence"]),
        "reviewed_report_sha256": report_sha256,
        "status": review["status"],
        # Retain the independently reviewed contract for later feedback
        # integrity checks.  It is not an execution input and does not affect
        # settlement arithmetic.
        "frozen_case_contract": deepcopy(review["frozen_case_contract"]),
        "claim_reviews": normalized_reviews,
    }


def _validate_production_artifacts(
    *,
    case_spec: dict[str, Any], output: Path, acceptance_root: Path, snapshot: dict[str, Any],
    run_manifest: dict[str, Any], completion: dict[str, Any], acceptance_config: dict[str, Any],
    acceptance_baseline: dict[str, Any], attestation: dict[str, Any], source_manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if attestation.get("execution_mode") != "PIT_PRODUCTION_FREEZE":
        raise ProductionFreezeCaseError("only PIT_PRODUCTION_FREEZE output may create a v2 case")
    if run_manifest.get("status") != "COMPLETED":
        raise ProductionFreezeCaseError("production run manifest is not completed")
    if completion.get("status") not in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
        raise ProductionFreezeCaseError("production completion contract is not complete")
    completion_snapshot = (completion.get("validators") or {}).get("publication_snapshot")
    if not isinstance(completion_snapshot, dict) or completion_snapshot.get("written") is not True:
        raise ProductionFreezeCaseError("production completion lacks a successful publication snapshot")
    if snapshot.get("v3_enforced") is not True or snapshot.get("lifecycle") != "MONITORING":
        raise ProductionFreezeCaseError("production snapshot is not a completed V3 monitoring snapshot")
    if snapshot.get("completion_status") not in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
        raise ProductionFreezeCaseError("production snapshot does not record a complete report")
    if snapshot.get("run_id") != run_manifest.get("run_id") or snapshot.get("run_id") != attestation.get("run_id"):
        raise ProductionFreezeCaseError("production snapshot, run manifest, and PIT attestation run_id differ")
    for field in ("case_id", "experiment_id", "company_code"):
        if attestation.get(field) != case_spec[field]:
            raise ProductionFreezeCaseError("PIT attestation does not match case specification: " + field)
    if attestation.get("cutoff_at") != case_spec["simulation_cutoff"]:
        raise ProductionFreezeCaseError("PIT attestation cutoff does not match case specification")
    if source_manifest.get("company_code") != case_spec["company_code"]:
        raise ProductionFreezeCaseError("PIT source manifest company does not match case specification")
    if source_manifest.get("cutoff_at") != case_spec["simulation_cutoff"]:
        raise ProductionFreezeCaseError("PIT source manifest cutoff does not match case specification")
    purpose = str(case_spec.get("purpose") or "")
    snapshot_purpose = str(snapshot.get("analysis_purpose") or "")
    if snapshot_purpose != purpose:
        raise ProductionFreezeCaseError("production snapshot analysis_purpose does not match case purpose")
    gate_states = snapshot.get("gate_states") if isinstance(snapshot.get("gate_states"), dict) else {}
    required_snapshot_gates = _required_snapshot_gates(purpose, snapshot)
    failed_gates = [
        name for name in required_snapshot_gates
        if gate_states.get(name) not in (
            {"REVIEWABLE", *READY_SNAPSHOT_STATES}
            if name == "financial_driver_bridge" else READY_SNAPSHOT_STATES
        )
    ]
    if failed_gates:
        raise ProductionFreezeCaseError("production snapshot has unfinished V3 gates: " + ", ".join(failed_gates))

    if acceptance_config.get("schema_version") != CONFIG_VERSION:
        raise ProductionFreezeCaseError("Phase 10 acceptance config schema is invalid")
    if acceptance_config.get("phase") != PHASE10_PRODUCTION_FREEZE_PHASE:
        raise ProductionFreezeCaseError("Phase 10 acceptance config is not a production freeze")
    sample_id = str(case_spec["sample_id"])
    samples = acceptance_config.get("samples") if isinstance(acceptance_config.get("samples"), list) else []
    matching_config = [item for item in samples if isinstance(item, dict) and item.get("sample_id") == sample_id]
    if len(matching_config) != 1:
        raise ProductionFreezeCaseError("Phase 10 acceptance config must contain exactly one matching sample")
    config_sample = matching_config[0]
    if config_sample.get("company_code") != case_spec["company_code"]:
        raise ProductionFreezeCaseError("Phase 10 acceptance company does not match the case")
    configured_output = Path(str(config_sample.get("output_dir") or "")).expanduser()
    configured_output = configured_output.resolve() if configured_output.is_absolute() else (_root() / configured_output).resolve()
    if configured_output != output:
        raise ProductionFreezeCaseError("Phase 10 acceptance output does not match the production output")
    expected_period = "PIT-" + str(case_spec["simulation_cutoff"])[:10]
    if config_sample.get("report_period") != expected_period:
        raise ProductionFreezeCaseError("Phase 10 acceptance report period does not match the case cutoff")

    baseline_samples = acceptance_baseline.get("samples") if isinstance(acceptance_baseline.get("samples"), list) else []
    matching_baseline = [item for item in baseline_samples if isinstance(item, dict) and item.get("sample_id") == sample_id]
    if len(matching_baseline) != 1:
        raise ProductionFreezeCaseError("Phase 10 acceptance baseline must contain exactly one matching sample")
    replay = evaluate_phase10_production_freeze_acceptance(
        sample_id=sample_id,
        company_code=str(case_spec["company_code"]),
        output_dir=output,
        report_period=expected_period,
        acceptance_root=acceptance_root,
        persist=False,
    )
    replay_samples = replay.get("samples") if isinstance(replay.get("samples"), list) else []
    matching_replay = [item for item in replay_samples if isinstance(item, dict) and item.get("sample_id") == sample_id]
    if len(matching_replay) != 1:
        raise ProductionFreezeCaseError("Phase 10 acceptance replay did not produce the requested sample")
    saved, replayed = matching_baseline[0], matching_replay[0]
    if replayed.get("machine_status") not in READY_ACCEPTANCE_STATES or not (replayed.get("hard_gates") or {}).get("passed"):
        raise ProductionFreezeCaseError("Phase 10 acceptance replay is not ready")
    for field in ("report_sha256", "machine_status"):
        if saved.get(field) != replayed.get(field):
            raise ProductionFreezeCaseError("saved Phase 10 acceptance differs from its replay: " + field)
    if (saved.get("hard_gates") or {}).get("passed") != (replayed.get("hard_gates") or {}).get("passed"):
        raise ProductionFreezeCaseError("saved Phase 10 acceptance hard gates differ from replay")
    return saved, replayed


def build_calibration_ledger_from_forward_judgments(
    thesis_ledger: dict[str, Any], *, simulation_cutoff: str, known_source_ids: set[str],
    known_sources: dict[str, dict[str, Any]] | None = None,
    known_financial_driver_ids: set[str] | None = None,
    financial_driver_monitoring_links: dict[str, set[str]] | None = None,
    financial_driver_monitoring_source_types: dict[str, set[str]] | None = None,
    financial_driver_monitoring_contracts: dict[str, dict[str, Any]] | None = None,
    financial_driver_layers: dict[str, str] | None = None,
    financial_driver_cash_normalization_states: dict[str, str] | None = None,
    financial_driver_realization_judgment_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Project frozen forward judgments into the historical settlement ledger.

    The function is deliberately a projection, not an inference layer.  Every
    historical-only field that the settlement engine needs must already be in
    ``settlement_contract`` on the judgment; a missing source, threshold, or
    observation window is an error instead of an opportunity for the adapter
    to invent one.  Price and execution remain outside this operating-forecast
    bridge.
    """
    if not isinstance(thesis_ledger, dict):
        raise ProductionFreezeCaseError("thesis_ledger must be an object")
    judgments = thesis_ledger.get("forward_judgments")
    if not isinstance(judgments, list) or not judgments:
        raise ProductionFreezeCaseError("thesis_ledger has no forward_judgments")
    selection_admission = thesis_ledger.get("selection_admission")
    selection_admission = selection_admission if isinstance(selection_admission, dict) else {}
    selection_judgment_ids = {
        str(judgment_id).strip()
        for judgment_id in selection_admission.get("selection_forward_judgment_ids") or []
        if str(judgment_id).strip()
    }
    if selection_admission.get("status") == "SELECTION_ADMITTED" and not selection_judgment_ids:
        raise ProductionFreezeCaseError("SELECTION_ADMITTED requires selection_forward_judgment_ids")
    central = thesis_ledger.get("central_path") if isinstance(thesis_ledger.get("central_path"), dict) else {}
    central_path_id = str(central.get("path_id") or "").strip()
    tests = {
        str(item.get("test_id") or ""): item
        for item in thesis_ledger.get("competitive_tests") or []
        if isinstance(item, dict) and str(item.get("test_id") or "").strip()
    }
    claims: list[dict[str, Any]] = []
    claim_by_judgment_id: dict[str, dict[str, Any]] = {}
    frozen_judgment_ids: set[str] = set()
    for index, judgment in enumerate(judgments):
        label = f"forward_judgments[{index}]"
        if not isinstance(judgment, dict):
            raise ProductionFreezeCaseError(label + " must be an object")
        judgment_id = str(judgment.get("judgment_id") or "").strip()
        prediction = judgment.get("prediction") if isinstance(judgment.get("prediction"), dict) else {}
        outcome = judgment.get("observable_outcome") if isinstance(judgment.get("observable_outcome"), dict) else {}
        settlement = judgment.get("settlement_contract") if isinstance(judgment.get("settlement_contract"), dict) else {}
        _required(judgment, ("judgment_id", "statement", "competitive_test_id", "falsifier", "mechanism_chain_ids"), label)
        _required(prediction, ("metric", "operator", "unit", "horizon"), label + ".prediction")
        _required(
            outcome,
            ("measurement_basis", "measurement_rule", "measurement_period", "allowed_source_types", "settlement_version_policy"),
            label + ".observable_outcome",
        )
        if judgment_id in selection_judgment_ids:
            contract_outcome = dict(outcome)
            contract_outcome["unit"] = prediction.get("unit")
            contract_invalid, contract_incomplete = contract_findings(
                contract_outcome,
                prefix=label + ".observable_outcome",
                allowed_source_types={
                    str(source_type).strip()
                    for source_type in outcome.get("allowed_source_types") or []
                    if str(source_type).strip()
                },
            )
            contract_findings_text = contract_invalid + contract_incomplete
            if contract_findings_text:
                raise ProductionFreezeCaseError(
                    label + " metric_reconstruction_contract is incomplete: "
                    + ", ".join(contract_findings_text)
                )
        _required(
            settlement,
            ("calibration_claim_id", "materiality", "source_ids", "threshold", "observation_window"),
            label + ".settlement_contract",
        )
        claim_id = str(settlement.get("calibration_claim_id") or "").strip()
        if not claim_id.startswith("HBTCLM:"):
            raise ProductionFreezeCaseError(label + " settlement calibration_claim_id is invalid")
        source_ids = settlement.get("source_ids") if isinstance(settlement.get("source_ids"), list) else []
        if not source_ids or any(str(source_id) not in known_source_ids for source_id in source_ids):
            raise ProductionFreezeCaseError(label + " settlement source_ids are not admitted PIT sources")
        outcome_source_types = {
            str(source_type).strip()
            for source_type in outcome.get("allowed_source_types") or []
            if str(source_type).strip()
        }
        if "LICENSED_INDUSTRY_DATA" in outcome_source_types:
            if known_sources is None:
                raise ProductionFreezeCaseError(
                    label + " licensed industry outcome requires admitted source records for series resolution"
                )
            series_invalid, series_incomplete = licensed_industry_series_contract_findings(
                outcome.get("licensed_industry_series_contract"),
                prefix=label + ".observable_outcome",
                pre_cutoff_sources=known_sources,
            )
            findings = series_invalid + series_incomplete
            if findings:
                raise ProductionFreezeCaseError(
                    label + " licensed industry series contract is invalid: " + ", ".join(findings)
                )
            series = outcome.get("licensed_industry_series_contract") or {}
            if series.get("metric_id") != prediction.get("metric"):
                raise ProductionFreezeCaseError(
                    label + " licensed industry series metric does not match frozen prediction"
                )
            if str(series.get("pre_cutoff_source_id")) not in {str(source_id) for source_id in source_ids}:
                raise ProductionFreezeCaseError(
                    label + " licensed industry series pre-cutoff source is not in settlement source_ids"
                )
        threshold = settlement.get("threshold") if isinstance(settlement.get("threshold"), dict) else {}
        if threshold.get("metric") != prediction.get("metric") or threshold.get("unit") != prediction.get("unit"):
            raise ProductionFreezeCaseError(label + " settlement threshold does not match frozen prediction")
        window = settlement.get("observation_window") if isinstance(settlement.get("observation_window"), dict) else {}
        if not str(window.get("opens_after") or "").strip() or not str(window.get("closes_at") or "").strip():
            raise ProductionFreezeCaseError(label + " settlement observation_window is incomplete")
        test = tests.get(str(judgment.get("competitive_test_id") or ""))
        if not isinstance(test, dict) or not str(test.get("strongest_alternative") or "").strip():
            raise ProductionFreezeCaseError(label + " cannot resolve a counter thesis from competitive_test_id")
        financial_driver_ids = judgment.get("financial_driver_ids")
        transmission = judgment.get("transmission") if isinstance(judgment.get("transmission"), dict) else {}
        if known_financial_driver_ids is not None:
            if not isinstance(financial_driver_ids, list) or not financial_driver_ids:
                raise ProductionFreezeCaseError(label + " requires financial_driver_ids when the frozen bridge is enabled")
            unknown_driver_ids = sorted(
                str(driver_id) for driver_id in financial_driver_ids
                if str(driver_id) not in known_financial_driver_ids
            )
            if unknown_driver_ids:
                raise ProductionFreezeCaseError(
                    label + " references unknown frozen financial drivers: " + ", ".join(unknown_driver_ids)
                )
            if financial_driver_monitoring_links is not None:
                unmonitored_driver_ids = sorted(
                    str(driver_id) for driver_id in financial_driver_ids
                    if judgment_id not in financial_driver_monitoring_links.get(str(driver_id), set())
                )
                if unmonitored_driver_ids:
                    raise ProductionFreezeCaseError(
                        label + " lacks FDB monitoring links for financial drivers: "
                        + ", ".join(unmonitored_driver_ids)
                    )
            if financial_driver_monitoring_source_types is not None:
                permitted_source_sets = [
                    financial_driver_monitoring_source_types.get(str(driver_id), set())
                    for driver_id in financial_driver_ids
                ]
                permitted_source_types = set.intersection(*permitted_source_sets) if permitted_source_sets else set()
                if not outcome_source_types or not outcome_source_types.issubset(permitted_source_types):
                    raise ProductionFreezeCaseError(
                        label + " observable_outcome allowed_source_types exceed frozen FDB monitoring contracts"
                    )
                if "LICENSED_INDUSTRY_DATA" in outcome_source_types:
                    contracts = [
                        financial_driver_monitoring_contracts.get(str(driver_id))
                        if financial_driver_monitoring_contracts is not None else None
                        for driver_id in financial_driver_ids
                    ]
                    expected_outcome_identity = {
                        "metric": prediction.get("metric"),
                        "unit": prediction.get("unit"),
                        "measurement_basis": outcome.get("measurement_basis"),
                        "measurement_period": outcome.get("measurement_period"),
                        "observation_window": window,
                    }
                    if any(
                        not isinstance(contract, dict)
                        or any(contract.get(field) != expected for field, expected in expected_outcome_identity.items())
                        for contract in contracts
                    ):
                        raise ProductionFreezeCaseError(
                            label + " licensed industry outcome does not match frozen FDB monitoring contract"
                        )
            if financial_driver_layers is not None and financial_driver_cash_normalization_states is not None:
                owner_cash = transmission.get("owner_cash") if isinstance(transmission.get("owner_cash"), dict) else {}
                owner_cash_direction = str(owner_cash.get("direction") or "")
                if owner_cash_direction not in {"unknown", "not_material", ""}:
                    cash_driver_ids = [
                        str(driver_id) for driver_id in financial_driver_ids
                        if financial_driver_layers.get(str(driver_id)) == "CASH_CONVERSION"
                    ]
                    if not cash_driver_ids:
                        raise ProductionFreezeCaseError(
                            label + " material owner_cash transmission requires a frozen CASH_CONVERSION driver"
                        )
                    unresolved_cash_drivers = sorted(
                        driver_id for driver_id in cash_driver_ids
                        if financial_driver_cash_normalization_states.get(driver_id) != "NORMALIZED"
                    )
                    if unresolved_cash_drivers:
                        raise ProductionFreezeCaseError(
                            label + " material owner_cash transmission requires NORMALIZED cash drivers: "
                            + ", ".join(unresolved_cash_drivers)
                        )
        elif financial_driver_ids is not None and not isinstance(financial_driver_ids, list):
            raise ProductionFreezeCaseError(label + " financial_driver_ids must be an array")
        projected_outcome = deepcopy(outcome)
        projected_outcome["metric"] = prediction.get("metric")
        projected_outcome["unit"] = prediction.get("unit")
        projected_outcome["observation_window"] = deepcopy(window)
        projected_claim = {
            "claim_id": claim_id,
            "statement": judgment.get("statement"),
            "materiality": settlement.get("materiality"),
            "frozen_disposition": "PREDICTION",
            "source_ids": deepcopy(source_ids),
            "prediction": deepcopy(prediction),
            "threshold": deepcopy(threshold),
            "unknown": None,
            "counter_thesis": test.get("strongest_alternative"),
            "flip_condition": judgment.get("falsifier"),
            "observable_outcome": projected_outcome,
            "forward_judgment_id": judgment_id,
            # A forward judgment in a G1-J pair has exactly one frozen
            # discriminator. Preserve that identity on the projected claim so
            # feedback can distinguish a diagnostic signal from a merely
            # calculated operating observation.
            "rival_hypothesis_pair_id": judgment.get("rival_hypothesis_pair_id"),
            "rival_signal_id": judgment.get("rival_signal_id"),
            "central_path_id": central_path_id or None,
            "mechanism_chain_ids": deepcopy(judgment.get("mechanism_chain_ids")),
            "financial_driver_ids": deepcopy(financial_driver_ids or []),
            "baseline_id": str(((judgment.get("baseline") or {}).get("baseline_id")) or "") or None,
            # The settlement engine need not score the baseline today, but the
            # frozen case must retain it.  Otherwise a later feedback review
            # can identify the author's claim but cannot compare it with the
            # same-scope simple challenger that existed at freeze time.
            "baseline": deepcopy(judgment.get("baseline")),
            # Preserve the author's economic transmission for task-level
            # feedback.  These are not outcome fields and do not participate
            # in settlement validation; they make it possible to distinguish a
            # failed mechanism/model link from a merely wrong point forecast.
            "transmission": deepcopy(transmission),
        }
        claims.append(projected_claim)
        claim_by_judgment_id[judgment_id] = projected_claim
        frozen_judgment_ids.add(judgment_id)
    missing_selection_judgments = sorted(selection_judgment_ids - frozen_judgment_ids)
    if missing_selection_judgments:
        raise ProductionFreezeCaseError(
            "SELECTION_ADMITTED references forward judgments not projected into the frozen case: "
            + ", ".join(missing_selection_judgments)
        )
    if financial_driver_monitoring_links is not None:
        for driver_id, monitored_judgment_ids in sorted(financial_driver_monitoring_links.items()):
            missing = sorted(monitored_judgment_ids - frozen_judgment_ids)
            if missing:
                raise ProductionFreezeCaseError(
                    "frozen FDB monitoring contract references forward judgments absent from thesis ledger: "
                    + driver_id + " -> " + ", ".join(missing)
                )
    if financial_driver_realization_judgment_ids is not None:
        missing = sorted(financial_driver_realization_judgment_ids - frozen_judgment_ids)
        if missing:
            raise ProductionFreezeCaseError(
                "frozen FDB realization contract references forward judgments absent from thesis ledger: "
                + ", ".join(missing)
            )
    # Keep the R-07 admission receipt alongside the immutable claims.  It is
    # not an outcome input: feedback uses it only to distinguish a diagnostic
    # mechanism signal from an eligible path-selection learning result.
    projected = {"claims": claims}
    if selection_admission:
        projected["selection_admission"] = deepcopy(selection_admission)
    pairs = thesis_ledger.get("rival_hypothesis_pairs")
    cards = thesis_ledger.get("analogy_transfer_cards")
    if pairs is not None or cards is not None:
        if not isinstance(pairs, list) or not pairs:
            raise ProductionFreezeCaseError("thesis_ledger rival_hypothesis_pairs are incomplete")
        if not isinstance(cards, list) or not cards:
            raise ProductionFreezeCaseError("thesis_ledger analogy_transfer_cards are incomplete")
        projected_pairs: list[dict[str, Any]] = []
        for index, pair in enumerate(pairs):
            label = f"rival_hypothesis_pairs[{index}]"
            if not isinstance(pair, dict):
                raise ProductionFreezeCaseError(label + " must be an object")
            frozen_pair = deepcopy(pair)
            discriminators = frozen_pair.get("discriminators")
            if not isinstance(discriminators, list) or not discriminators:
                raise ProductionFreezeCaseError(label + " has no frozen discriminators")
            for didx, discriminator in enumerate(discriminators):
                dlabel = f"{label}.discriminators[{didx}]"
                if not isinstance(discriminator, dict):
                    raise ProductionFreezeCaseError(dlabel + " must be an object")
                judgment_id = str(discriminator.get("forward_judgment_id") or "")
                claim = claim_by_judgment_id.get(judgment_id)
                if claim is None:
                    raise ProductionFreezeCaseError(dlabel + " references a forward judgment not projected into the frozen case")
                judgment = next(
                    (item for item in judgments if isinstance(item, dict) and item.get("judgment_id") == judgment_id),
                    {},
                )
                if discriminator.get("primary_prediction") != judgment.get("prediction"):
                    raise ProductionFreezeCaseError(dlabel + " primary prediction differs from the frozen forward judgment")
                if judgment.get("rival_hypothesis_pair_id") != pair.get("pair_id") or judgment.get("rival_signal_id") != discriminator.get("signal_id"):
                    raise ProductionFreezeCaseError(dlabel + " does not match the forward judgment rival-pair links")
                discriminator["claim_id"] = claim.get("claim_id")
            projected_pairs.append(frozen_pair)
        projected["rival_hypothesis_pairs"] = projected_pairs
        projected["analogy_transfer_cards"] = deepcopy(cards)
    invalid, incomplete = historical_backtest._validate_calibration_ledger(
        {
            "schema_version": historical_backtest.CASE_SCHEMA_VERSION_V2,
            "simulation_cutoff": simulation_cutoff,
            "calibration_ledger": projected,
        },
        known_sources or {
            str(source_id): {"source_id": str(source_id)}
            for source_id in known_source_ids
        },
    )
    if invalid or incomplete:
        findings = "; ".join([*invalid, *incomplete])
        raise ProductionFreezeCaseError("forward judgment projection is not settlement-ready: " + findings)
    return projected


def derive_v2_case(
    *,
    case_spec: dict[str, Any],
    production_output_dir: str | Path,
    acceptance_root: str | Path,
    pit_attestation_path: str | Path,
    source_manifest_path: str | Path,
    source_package_root: str | Path,
    case_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Derive and validate one v2 case without reading any later evidence body.

    ``case_spec`` contains only frozen investment judgments.  It must already
    have an external independent-review artifact.  The output is written only
    after the existing historical case validator declares it ``REVIEWABLE``.
    """
    if not isinstance(case_spec, dict):
        raise ProductionFreezeCaseError("case_spec must be an object")
    unsupported = sorted(set(case_spec) - CASE_SPEC_FIELDS)
    if unsupported:
        raise ProductionFreezeCaseError("case_spec contains unsupported fields: " + ", ".join(unsupported))
    _required(
        case_spec,
        (
            "case_id", "experiment_id", "sample_id", "company_code", "simulation_cutoff", "frozen_at",
            "report_id", "writer_id", "writer_provenance", "route", "forecast",
            "purpose", "inputs", "calibration_ledger", "taxes_fees_fx", "price_identity",
        ),
        "case_spec",
    )
    future_fields = _future_fields(case_spec)
    if future_fields:
        raise ProductionFreezeCaseError("case_spec contains post-freeze settlement fields: " + ", ".join(future_fields))
    if case_spec.get("purpose") not in CASE_PURPOSES:
        raise ProductionFreezeCaseError("case_spec purpose is invalid")
    _require_company_judgment_boundary(case_spec)

    output, output_rel = _repo_path(production_output_dir, "production_output_dir")
    acceptance, acceptance_rel = _repo_path(acceptance_root, "acceptance_root")
    attestation_path, attestation_rel = _repo_path(pit_attestation_path, "pit_attestation_path")
    manifest_path, manifest_rel = _repo_path(source_manifest_path, "source_manifest_path")
    package_root, package_rel = _repo_path(source_package_root, "source_package_root")
    for path, label in (
        (output, "production output"), (acceptance, "acceptance root"), (package_root, "source package root"),
    ):
        if not path.is_dir():
            raise ProductionFreezeCaseError(label + " is missing: " + str(path))
    for path, label in ((attestation_path, "PIT attestation"), (manifest_path, "source manifest")):
        if not path.is_file():
            raise ProductionFreezeCaseError(label + " is missing: " + str(path))

    snapshot = _load_object(output / "publication_snapshot.json", "publication snapshot")
    run_manifest = _load_object(output / "run_manifest.json", "run manifest")
    completion = _load_object(output / "completion_report.json", "completion report")
    acceptance_config = _load_object(acceptance / PHASE10_PRODUCTION_FREEZE_CONFIG_NAME, "Phase 10 acceptance config")
    acceptance_baseline = _load_object(acceptance / "acceptance_baseline.json", "Phase 10 acceptance baseline")
    attestation = _load_object(attestation_path, "PIT attestation")
    source_manifest = _load_object(manifest_path, "PIT source manifest")
    saved_acceptance, replayed_acceptance = _validate_production_artifacts(
        case_spec=case_spec,
        output=output,
        acceptance_root=acceptance,
        snapshot=snapshot,
        run_manifest=run_manifest,
        completion=completion,
        acceptance_config=acceptance_config,
        acceptance_baseline=acceptance_baseline,
        attestation=attestation,
        source_manifest=source_manifest,
    )
    report_variant = resolve_report_variant(output)
    report_path = report_variant.get("report")
    report_sha256 = str(snapshot.get("report_sha256") or "")
    variant_id = str(report_variant.get("variant_id") or "")
    if not isinstance(report_path, Path) or not report_path.is_file() or not report_sha256 or not variant_id:
        raise ProductionFreezeCaseError("production report identity is incomplete")
    if report_variant.get("technical_report") is not None or report_variant.get("report_sha256") != report_sha256:
        raise ProductionFreezeCaseError("production report variant does not match the frozen snapshot")
    if saved_acceptance.get("report_sha256") != report_sha256 or replayed_acceptance.get("report_sha256") != report_sha256:
        raise ProductionFreezeCaseError("Phase 10 acceptance report identity does not match the frozen snapshot")
    report_rel = _repo_path(report_path, "production report")[1]
    writer = attestation.get("writer") if isinstance(attestation.get("writer"), dict) else {}
    if Path(str(writer.get("final_report_path") or "")).resolve() != report_path.resolve():
        raise ProductionFreezeCaseError("PIT writer final report does not match the production report")
    writer_provenance = case_spec["writer_provenance"]
    if not isinstance(writer_provenance, dict):
        raise ProductionFreezeCaseError("writer_provenance must be an object")
    for field in ("provider", "model"):
        if writer_provenance.get(field) not in (None, "", writer.get(field)):
            raise ProductionFreezeCaseError("writer provenance does not match PIT attestation: " + field)
    document_manifest = _load_object(output / "document_manifest.json", "production document manifest")
    sources = _source_map(snapshot, source_manifest, document_manifest, output)
    source_ids = {str(source["source_id"]) for source in sources}
    frozen_driver_bridge = _frozen_financial_driver_bridge(
        output,
        snapshot,
        expected_analysis_purpose=str(case_spec["purpose"]),
    )
    calibration_ledger = deepcopy(case_spec["calibration_ledger"])
    if _uses_frozen_forward_judgments(calibration_ledger):
        calibration_ledger = _frozen_forward_judgment_ledger(
            output, snapshot, sources, str(case_spec["simulation_cutoff"]),
            frozen_financial_driver_bridge=frozen_driver_bridge,
        )
    writer_reads = {str(source_id) for source_id in writer.get("read_source_ids") or []}
    audit_reads = {
        str(event.get("source_id") or "")
        for event in attestation.get("read_audit") or []
        if isinstance(event, dict) and event.get("allowed") is True and event.get("kind") == "SOURCE"
    }
    if not source_ids.issubset(writer_reads) or not source_ids.issubset(audit_reads):
        raise ProductionFreezeCaseError("production snapshot source was not actually read by the PIT writer")
    frozen_case_contract = {
        field: deepcopy(case_spec[field])
        for field in FROZEN_CASE_CONTRACT_FIELDS
    }
    frozen_case_contract["calibration_ledger"] = deepcopy(calibration_ledger)
    if frozen_driver_bridge is not None:
        frozen_case_contract["financial_driver_bridge"] = deepcopy(frozen_driver_bridge)
    incomplete = {
        "state": "INCOMPLETE",
        "case": None,
        "validation": None,
        "path": None,
        "case_id": case_spec["case_id"],
        "variant_id": variant_id,
        "freeze_id": "HBTFRZ:" + variant_id,
        "next_action": "REGISTER_INDEPENDENT_REVIEW",
        "frozen_case_contract": frozen_case_contract,
    }
    review_reference = str(case_spec.get("review_artifact_path") or "").strip()
    if not review_reference:
        return {**incomplete, "blockers": ["independent_review_pending"]}
    try:
        review_path, review_rel = _repo_path(review_reference, "review_artifact_path")
    except ProductionFreezeCaseError:
        return {**incomplete, "blockers": ["independent_review_artifact_unregistered"]}
    if not review_path.is_file():
        return {**incomplete, "blockers": ["independent_review_artifact_missing"]}
    try:
        raw_review = _load_object(review_path, "independent review artifact")
    except ProductionFreezeCaseError:
        return {**incomplete, "blockers": ["independent_review_artifact_unreadable"]}
    if raw_review.get("status") != "PASS":
        return {**incomplete, "blockers": ["independent_review_not_passed"]}
    review = _review_from_artifact(
        review_path,
        variant_id=variant_id,
        report_sha256=report_sha256,
        frozen_case_contract=frozen_case_contract,
    )

    case = {
        "schema_version": CASE_SCHEMA_VERSION_V2,
        "case_id": case_spec["case_id"],
        "experiment_id": case_spec["experiment_id"],
        "company_code": case_spec["company_code"],
        "purpose": case_spec["purpose"],
        "simulation_cutoff": case_spec["simulation_cutoff"],
        "report_freeze": {
            "frozen_at": case_spec["frozen_at"],
            "evidence_cutoff": case_spec["simulation_cutoff"],
            "settlement_locked": True,
            "report_status": "FROZEN",
            "mode": "PRODUCTION_PIPELINE",
            "freeze_id": "HBTFRZ:" + variant_id,
            "frozen_report": {
                "report_id": case_spec["report_id"],
                "variant_id": variant_id,
                "origin": {
                    "kind": "TURTLE_PIPELINE",
                    "output_dir": output_rel,
                    "acceptance_root": acceptance_rel,
                    "sample_id": case_spec["sample_id"],
                    "run_manifest_path": output_rel + "/run_manifest.json",
                    "completion_report_path": output_rel + "/completion_report.json",
                    "publication_snapshot_path": output_rel + "/publication_snapshot.json",
                    "review_artifact_path": review_rel,
                    "pit_runner": {
                        "attestation_path": attestation_rel,
                        "source_package_manifest_path": manifest_rel,
                        "package_root": package_rel,
                        "status": "PASS",
                    },
                },
                "artifact_path": report_rel,
                "artifact_sha256": report_sha256,
                "format": "MARKDOWN",
                "writer_id": case_spec["writer_id"],
                "writer_provenance": deepcopy(writer_provenance),
                "writer_status": "COMPLETE",
                "claim_ids": [claim.get("claim_id") for claim in calibration_ledger.get("claims", []) if isinstance(claim, dict)],
                "section_markers": list(
                    CJO_FROZEN_REPORT_SECTIONS
                    if case_spec["purpose"] == "COMPANY_JUDGMENT_ONLY"
                    else INVESTMENT_FROZEN_REPORT_SECTIONS
                ),
            },
            "independent_review": review,
            "quality_failure": None,
        },
        "credibility": {
            "model_memory_control": "UNCONTROLLED",
            "backtest_credibility": "EXPLORATORY",
            "assessment_basis": "PIT production boundary is replayable, but deployment-level model-memory control is unavailable.",
            "control_evidence": [],
            "calibration_role": "ENGINEERING_DIAGNOSTIC_ONLY",
        },
        "route": "DUAL",
        "forecast": deepcopy(case_spec["forecast"]),
        "sources": sources,
        "inputs": deepcopy(case_spec["inputs"]),
        "calibration_ledger": deepcopy(calibration_ledger),
        **({"financial_driver_bridge": deepcopy(frozen_driver_bridge)} if frozen_driver_bridge is not None else {}),
        "taxes_fees_fx": deepcopy(case_spec["taxes_fees_fx"]),
        "price_identity": {
            "primary_route": "PRIMARY_ROUTE_UNKNOWN",
            "primary_price_identity": "UNKNOWN",
            "prices": [],
        },
        "status": "FROZEN",
    }
    result = validate_case(case, allow_test_fixtures=False)
    if result["state"] != "REVIEWABLE":
        findings = result["invalid_findings"] + result["incomplete_findings"]
        raise ProductionFreezeCaseError("derived v2 case is not reviewable: " + "; ".join(findings))
    written_path = None
    if case_output_path is not None:
        target, _ = _repo_path(case_output_path, "case_output_path")
        if target.exists():
            raise ProductionFreezeCaseError("case output already exists: " + str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        written_path = target
    return {"case": case, "validation": result, "path": str(written_path) if written_path else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-spec", required=True, help="repository-relative frozen v2 case specification JSON")
    parser.add_argument("--production-output", required=True, help="repository-relative PIT production output directory")
    parser.add_argument("--acceptance-root", required=True, help="repository-relative Phase 10 acceptance directory")
    parser.add_argument("--pit-attestation", required=True, help="repository-relative PIT production attestation JSON")
    parser.add_argument("--source-manifest", required=True, help="repository-relative admitted PIT source manifest JSON")
    parser.add_argument("--source-package", required=True, help="repository-relative admitted PIT source package")
    parser.add_argument("--case-output", help="fresh repository-relative v2 case destination")
    args = parser.parse_args(argv)
    try:
        spec_path, _ = _repo_path(args.case_spec, "case_spec")
        result = derive_v2_case(
            case_spec=_load_object(spec_path, "case specification"),
            production_output_dir=args.production_output,
            acceptance_root=args.acceptance_root,
            pit_attestation_path=args.pit_attestation,
            source_manifest_path=args.source_manifest,
            source_package_root=args.source_package,
            case_output_path=args.case_output,
        )
    except ProductionFreezeCaseError as exc:
        parser.error(str(exc))
    if result.get("state") == "INCOMPLETE":
        print(json.dumps({
            "state": "INCOMPLETE",
            "case_id": result["case_id"],
            "variant_id": result["variant_id"],
            "freeze_id": result["freeze_id"],
            "next_action": result["next_action"],
            "blockers": result["blockers"],
        }, ensure_ascii=False))
        return 2
    case = result["case"]
    print(json.dumps({
        "state": result["validation"]["state"],
        "case_id": case["case_id"],
        "freeze_id": case["report_freeze"]["freeze_id"],
        "path": result["path"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
