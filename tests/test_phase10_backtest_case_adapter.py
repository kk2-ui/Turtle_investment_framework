from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

import scripts.historical_backtest as historical_backtest
import scripts.phase10_pit_runner as phase10_pit_runner
from scripts.phase10_acquisition import enumerate_sse_announcements
from scripts.phase10_backtest_case_adapter import (
    ProductionFreezeCaseError,
    derive_v2_case,
)
from scripts.phase10_pit_runner import PITSourcePackage
from scripts.historical_backtest import SETTLEMENT_SCHEMA_VERSION_V2, validate_settlement
from scripts.real_report_acceptance import (
    REQUIRED_MACHINE_GATES,
    evaluate_phase10_production_freeze_acceptance,
    resolve_report_variant,
)
from tests.test_stage36_historical_backtest_pilot import _case, _settlement


def _v2_case_spec(*, review_artifact_path: str = "") -> dict:
    source = _case()
    ledger = deepcopy(source["calibration_ledger"])
    for claim in ledger["claims"]:
        outcome = claim["observable_outcome"]
        start = outcome.pop("period_start")
        end = outcome.pop("period_end")
        outcome["measurement_period"] = {
            "kind": "REPORTING_PERIOD",
            "start": start,
            "end": end,
        }
        outcome["observation_window"] = {
            "opens_after": "2021-09-01T00:00:00+08:00",
            "closes_at": "2022-08-31T18:00:00+08:00",
        }
    return {
        "case_id": "HBTCASE:TEST",
        "experiment_id": "HBT:test",
        "sample_id": "00506",
        "company_code": "00506.HK",
        "simulation_cutoff": "2021-08-31T18:00:00+08:00",
        "frozen_at": "2021-08-31T19:00:00+08:00",
        "report_id": "HBTREP:TEST",
        "writer_id": "writer:test",
        "writer_provenance": {
            "actor_type": "model",
            "provider": "test-provider",
            "model": "test-model",
            "context_id": "writer-context:test",
        },
        "review_artifact_path": review_artifact_path,
        "route": "DUAL",
        "forecast": {
            "horizon_years": 5,
            "terminal_handling": "DUAL_TERMINAL_PATH",
            "cash_flow_basis": source["forecast"]["cash_flow_basis"],
        },
        "inputs": deepcopy(source["inputs"]),
        "calibration_ledger": ledger,
        "taxes_fees_fx": deepcopy(source["taxes_fees_fx"]),
        "price_identity": {
            "primary_route": "PRIMARY_ROUTE_UNKNOWN",
            "primary_price_identity": "UNKNOWN",
            "prices": [],
        },
        "investment_decision": {
            "action": "UNKNOWN",
            "price_identity": "UNKNOWN",
            "execution_rule": "No execution is permitted while the primary route and price are unknown.",
        },
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _production_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    root = tmp_path / "repository"
    package = root / "historical" / "package"
    annual = package / "annual"
    annual.mkdir(parents=True)
    (annual / "2020.pdf").write_bytes(b"%PDF-original")
    (annual / "2020.pages.md").write_text(
        "# AR:00506:2020\n\n"
        "- source_id: AR:00506:2020\n"
        "- source_version: annual-report-original-2020\n"
        "- content_representation: PDF_PAGE_MARKDOWN\n\n"
        "## 第 1 页\n\n截止日前年报正文\n",
        encoding="utf-8",
    )
    framework_root = root / "config" / "phase10_pit_framework" / "framework"
    framework_root.mkdir(parents=True)
    (framework_root / "policy.md").write_text("PIT policy", encoding="utf-8")
    monkeypatch.setattr(phase10_pit_runner, "PIT_STATIC_FRAMEWORK_ROOT", framework_root.parent)
    monkeypatch.setattr(historical_backtest, "__file__", str(root / "scripts" / "historical_backtest.py"))

    manifest = enumerate_sse_announcements([{
        "source_id": "AR:00506:2020",
        "source_version": "annual-report-original-2020",
        "source_type": "ANNUAL_REPORT",
        "title": "2020 年年度报告",
        "published_at": "2021-03-25",
        "data_as_of": "2020-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
    }], cutoff_at="2021-08-31T18:00:00+08:00", period_start="2021-01-01")
    manifest["company_code"] = "00506.HK"
    for source in [*manifest["inventory"], *manifest["sources"]]:
        source.update({
            "package_path": "annual/2020.pdf",
            "content_representation": "PDF_PAGE_MARKDOWN",
            "reader_text_path": "annual/2020.pages.md",
            "reader_text_extractor": "pdf_preprocessor.extract_all_pages",
            "reader_text_extractor_version": "phase10-pdf-page-markdown.v1",
            "reader_text_page_count": 1,
        })
    manifest["framework_allowlist"] = [{"path": "framework/policy.md"}]
    manifest_path = root / "historical" / "source-manifest.json"
    _write_json(manifest_path, manifest)
    runner = PITSourcePackage(
        manifest,
        package,
        case_id="HBTCASE:TEST",
        experiment_id="HBT:test",
        run_id="pit-production-test",
        manifest_path=str(manifest_path),
    )
    assert runner.state == "REVIEWABLE"
    runner.read_framework("framework/policy.md")
    runner.read_source("AR:00506:2020")

    output = root / "pipeline-output"
    report_path = output / "reports" / "00506_分析报告_v13.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        "# HBTREP:TEST\n\n"
        "## Evidence\n\n"
        "HBTCLM:owner-cash 普通股每股 owner cash 在下一财年不少于 HKD0.20。\n\n"
        "## Operating forecast\n\n"
        "HBTCLM:minority-cash-access 子公司少数股东现金索取的实际比例尚未被官方披露闭合。\n\n"
        "## Valuation\n\n"
        "Primary price is UNKNOWN.\n\n"
        "## Risks and unknowns\n\n"
        "The route remains unknown.\n\n"
        "## Decision\n\n"
        "UNKNOWN; no execution.\n",
        encoding="utf-8",
    )
    projected_path = output / "pit_sources" / "AR_00506_2020" / "original.pdf"
    projected_path.parent.mkdir(parents=True)
    projected_path.write_bytes(b"projected pre-cutoff source")
    _write_json(output / "document_manifest.json", {"documents": [{
        "doc_id": "DOC:00506:2020",
        "source_id": "AR:00506:2020",
        "source_version": "annual-report-original-2020",
        "published_at": "2021-03-25",
        "data_as_of": "2020-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
        "local_path": "pit_sources/AR_00506_2020/original.pdf",
        "acquisition_status": "PIT_LINKED_AFTER_ALLOW_READ",
    }]})
    report_identity = resolve_report_variant(output)
    report_sha256 = str(report_identity["report_sha256"])
    _write_json(output / "run_manifest.json", {
        "run_id": "pit-production-test",
        "status": "COMPLETED",
    })
    _write_json(output / "completion_report.json", {
        "status": "COMPLETE",
        "validators": {"publication_snapshot": {"written": True}},
    })
    _write_json(output / "publication_snapshot.json", {
        "report_sha256": report_sha256,
        "run_id": "pit-production-test",
        "completion_status": "COMPLETE",
        "v3_enforced": True,
        "lifecycle": "MONITORING",
        "gate_states": {
            "decision": "DECISION_READY",
            "claim_evidence": "DECISION_READY",
            "valuation": "DECISION_READY",
            "thesis_test": "DECISION_READY",
            "insight": "DECISION_READY",
        },
        "unresolved_source_ids": [],
        "visible_information": [{
            "source_id": "AR:00506:2020",
            "evidence_source_id": "DOC:00506:2020",
            "source_provenance": "PIT_PROJECTED_AFTER_ALLOW_READ",
        }],
    })
    for gate, (filename, accepted) in REQUIRED_MACHINE_GATES.items():
        if gate in {"completion", "runtime_manifest"}:
            continue
        key = "status" if gate in {"completion", "runtime_manifest", "absolute_quality"} else "state"
        payload = {key: sorted(accepted)[0]}
        if gate == "thesis_test":
            payload["forward_judgment_state"] = "DECISION_READY"
        _write_json(output / filename, payload)
    _write_json(output / "research_execution.json", {
        "enforced": True,
        "chapters": {"2": {
            "enforced": True,
            "tool_counts": {"read_section": 2},
            "fiscal_years": [2019, 2020],
            "sections": ["MDA", "STMT"],
        }},
    })
    _write_json(output / "judgment_review_validation.json", {
        "state": "REVIEWED", "ceiling_verdict": "COMPETENT",
    })
    _write_json(output / "judgment_review.json", {
        "ceiling_verdict": "COMPETENT", "fragile_leaps": [], "dimension_assessments": {},
    })
    acceptance_root = root / "acceptance"
    acceptance = evaluate_phase10_production_freeze_acceptance(
        sample_id="00506",
        company_code="00506.HK",
        output_dir=output,
        report_period="PIT-2021-08-31",
        acceptance_root=acceptance_root,
    )
    assert acceptance["samples"][0]["machine_status"] == "READY_FOR_BLIND_REVIEW"

    attestation = runner.attestation()
    attestation.update({
        "execution_mode": "PIT_PRODUCTION_FREEZE",
        "writer": {
            "provider": "test-provider",
            "model": "test-model",
            "run_id": "pit-production-test",
            "case_id": "HBTCASE:TEST",
            "experiment_id": "HBT:test",
            "final_report_path": str(report_path),
            "source_anchor_ids": ["AR:00506:2020"],
            "read_source_ids": ["AR:00506:2020"],
        },
    })
    attestation_path = root / "historical" / "pit-attestation.json"
    _write_json(attestation_path, attestation)
    return {
        "root": root,
        "output": output,
        "acceptance_root": acceptance_root,
        "attestation": attestation_path,
        "manifest": manifest_path,
        "package": package,
        "report": report_path,
    }


def _derive(paths: dict[str, Path], case_spec: dict, output_path: Path | None = None) -> dict:
    return derive_v2_case(
        case_spec=case_spec,
        production_output_dir=paths["output"],
        acceptance_root=paths["acceptance_root"],
        pit_attestation_path=paths["attestation"],
        source_manifest_path=paths["manifest"],
        source_package_root=paths["package"],
        case_output_path=output_path,
    )


def _write_pass_review(paths: dict[str, Path], review_path: Path, *, case_spec: dict | None = None) -> None:
    identity = resolve_report_variant(paths["output"])
    reviewed_spec = case_spec or _v2_case_spec()
    frozen_case_contract = {
        field: deepcopy(reviewed_spec[field])
        for field in (
            "route", "forecast", "inputs", "calibration_ledger", "taxes_fees_fx", "price_identity", "investment_decision",
        )
    }
    _write_json(review_path, {
        "reviewed_at": "2021-08-31T20:00:00+08:00",
        "variant_id": identity["variant_id"],
        "report_sha256": identity["report_sha256"],
        "reviewer_id": "reviewer:test",
        "reviewer_provenance": {
            "actor_type": "human",
            "context_id": "reviewer-context:test",
        },
        "independence": {
            "did_not_generate_candidate": True,
            "no_prior_review_seen": True,
            "reviewer_context_isolated": True,
            "generator_identity_disjoint": True,
        },
        "status": "PASS",
        "frozen_case_contract": frozen_case_contract,
        "claim_reviews": [{
            "claim_id": "HBTCLM:owner-cash",
            "disposition": "SUPPORTED",
            "source_ids": ["AR:00506:2020"],
            "notes": ["Prediction, threshold, and measurement contract are frozen."],
        }, {
            "claim_id": "HBTCLM:minority-cash-access",
            "disposition": "UNKNOWN_PRESERVED",
            "source_ids": ["AR:00506:2020"],
            "notes": ["The unknown and its economic impact remain explicit."],
        }],
    })


def test_adapter_writes_reviewable_v2_case_without_action_or_future_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    review = paths["root"] / "reviews" / "independent.json"
    _write_pass_review(paths, review)
    sentinel = Path(__file__).resolve().parents[1] / "config" / "historical_backtest_600340_pit_engineering_case.json"
    original_v1 = sentinel.read_bytes()
    output_path = paths["root"] / "historical" / "case.v2.json"

    case_spec = _v2_case_spec(review_artifact_path="reviews/independent.json")
    result = _derive(paths, case_spec, output_path)

    assert result["validation"]["state"] == "REVIEWABLE"
    assert Path(str(result["path"])) == output_path
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "historical-backtest-case.v2"
    assert written["sources"] == [{
        "source_id": "AR:00506:2020",
        "source_version": "annual-report-original-2020",
        "source_type": "ANNUAL_REPORT",
        "published_at": "2021-03-25",
        "data_as_of": "2020-12-31",
        "revision_published_at": None,
        "revision_policy": "ORIGINAL_VINTAGE",
        "admissible": True,
    }]
    assert written["price_identity"]["primary_price_identity"] == "UNKNOWN"
    assert written["forecast"] == case_spec["forecast"]
    assert "investment_decision" not in written
    assert written["credibility"]["calibration_role"] == "ENGINEERING_DIAGNOSTIC_ONLY"
    settlement = _settlement()
    settlement["schema_version"] = SETTLEMENT_SCHEMA_VERSION_V2
    for source in settlement["actual_sources"]:
        source["content_access"] = "BODY_READ"
    for observation in settlement["actual_outcomes"]["operating_observations"]:
        start = observation.pop("period_start")
        end = observation.pop("period_end")
        observation["measurement_period"] = {
            "kind": "REPORTING_PERIOD", "start": start, "end": end,
        }
    assert "frozen_investment_decision_required_for_return_settlement" in validate_settlement(
        settlement, case=written,
    )["invalid_findings"]
    assert sentinel.read_bytes() == original_v1


def test_adapter_returns_identified_incomplete_candidate_before_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    output_path = paths["root"] / "historical" / "case.v2.json"

    result = _derive(paths, _v2_case_spec(), output_path)

    assert result == {
        "state": "INCOMPLETE",
        "case": None,
        "validation": None,
        "path": None,
        "case_id": "HBTCASE:TEST",
        "variant_id": resolve_report_variant(paths["output"])["variant_id"],
        "freeze_id": "HBTFRZ:" + resolve_report_variant(paths["output"])["variant_id"],
        "next_action": "REGISTER_INDEPENDENT_REVIEW",
        "blockers": ["independent_review_pending"],
    }
    assert not output_path.exists()


def test_adapter_rejects_identity_or_read_boundary_before_review_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    attestation = json.loads(paths["attestation"].read_text(encoding="utf-8"))
    attestation["case_id"] = "HBTCASE:OTHER"
    _write_json(paths["attestation"], attestation)
    with pytest.raises(ProductionFreezeCaseError, match="case_id"):
        _derive(paths, _v2_case_spec())

    attestation["case_id"] = "HBTCASE:TEST"
    attestation["writer"]["read_source_ids"] = []
    _write_json(paths["attestation"], attestation)
    with pytest.raises(ProductionFreezeCaseError, match="not actually read"):
        _derive(paths, _v2_case_spec())


def test_adapter_rejects_nonproduction_or_unready_freeze_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    review = paths["root"] / "reviews" / "independent.json"
    _write_pass_review(paths, review)
    case_spec = _v2_case_spec(review_artifact_path="reviews/independent.json")

    attestation = json.loads(paths["attestation"].read_text(encoding="utf-8"))
    attestation["execution_mode"] = "PIT_WRITER"
    _write_json(paths["attestation"], attestation)
    with pytest.raises(ProductionFreezeCaseError, match="only PIT_PRODUCTION_FREEZE"):
        _derive(paths, case_spec)

    attestation["execution_mode"] = "PIT_PRODUCTION_FREEZE"
    _write_json(paths["attestation"], attestation)
    snapshot = json.loads((paths["output"] / "publication_snapshot.json").read_text(encoding="utf-8"))
    snapshot["v3_enforced"] = False
    _write_json(paths["output"] / "publication_snapshot.json", snapshot)
    with pytest.raises(ProductionFreezeCaseError, match="completed V3"):
        _derive(paths, case_spec)

    snapshot["v3_enforced"] = True
    _write_json(paths["output"] / "publication_snapshot.json", snapshot)
    _write_json(paths["output"] / "claim_evidence_validation.json", {"state": "INCOMPLETE"})
    with pytest.raises(ProductionFreezeCaseError, match="acceptance replay is not ready"):
        _derive(paths, case_spec)


def test_adapter_rejects_executable_decision_or_unbound_v3_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    review = paths["root"] / "reviews" / "independent.json"
    _write_pass_review(paths, review)
    case_spec = _v2_case_spec(review_artifact_path="reviews/independent.json")
    case_spec["route"] = "FINITE_XIRR"
    case_spec["forecast"]["terminal_handling"] = "LEGAL_END"
    case_spec["price_identity"] = {
        "primary_route": "FINITE_XIRR",
        "primary_price_identity": "P_XIRR",
        "prices": [{"identity": "P_XIRR", "currency": "HKD", "value": 999, "meaning": "post hoc buy point"}],
    }
    case_spec["investment_decision"] = {
        "action": "BUY", "price_identity": "P_XIRR", "execution_rule": "Buy after the report.",
    }
    with pytest.raises(ProductionFreezeCaseError, match="requires route DUAL"):
        _derive(paths, case_spec)

    document_manifest = json.loads((paths["output"] / "document_manifest.json").read_text(encoding="utf-8"))
    document_manifest["documents"][0]["source_id"] = "AR:wrong"
    _write_json(paths["output"] / "document_manifest.json", document_manifest)
    with pytest.raises(ProductionFreezeCaseError, match="maps to a different PIT source"):
        _derive(paths, _v2_case_spec(review_artifact_path="reviews/independent.json"))


@pytest.mark.parametrize("mutation", ["prediction", "observation_window", "input", "tax"])
def test_adapter_rejects_claim_contract_changed_after_independent_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    review = paths["root"] / "reviews" / "independent.json"
    case_spec = _v2_case_spec(review_artifact_path="reviews/independent.json")
    _write_pass_review(paths, review, case_spec=case_spec)
    claim = case_spec["calibration_ledger"]["claims"][0]
    if mutation == "prediction":
        claim["prediction"]["value"] = 0.21
    elif mutation == "observation_window":
        claim["observable_outcome"]["observation_window"]["closes_at"] = "2022-09-01T18:00:00+08:00"
    elif mutation == "input":
        case_spec["inputs"][0]["value"] = 0.21
    else:
        case_spec["taxes_fees_fx"]["transaction_fee_rate"] = 0.002

    with pytest.raises(ProductionFreezeCaseError, match="frozen contract differs"):
        _derive(paths, case_spec)


def test_adapter_requires_review_to_bind_the_report_variant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    review = paths["root"] / "reviews" / "independent.json"
    _write_pass_review(paths, review)
    review_payload = json.loads(review.read_text(encoding="utf-8"))
    review_payload.pop("report_sha256")
    _write_json(review, review_payload)

    with pytest.raises(ProductionFreezeCaseError, match="independent review artifact missing: report_sha256"):
        _derive(paths, _v2_case_spec(review_artifact_path="reviews/independent.json"))


def test_adapter_refuses_future_settlement_content_in_the_frozen_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    case_spec = _v2_case_spec()
    case_spec["calibration_ledger"]["claims"][0]["prediction"]["outcome"] = "cutoff-after result"

    with pytest.raises(ProductionFreezeCaseError, match="post-freeze settlement fields: case_spec.calibration_ledger.claims\\[0\\].prediction.outcome"):
        _derive(paths, case_spec)
