from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

import scripts.historical_backtest as historical_backtest
import scripts.phase10_pit_runner as phase10_pit_runner
from scripts.phase10_acquisition import enumerate_sse_announcements
from scripts.phase10_backtest_case_adapter import (
    ProductionFreezeCaseError,
    _frozen_financial_driver_bridge,
    _required_snapshot_gates,
    _source_map,
    build_calibration_ledger_from_forward_judgments,
    derive_v2_case,
)
from scripts.phase10_pit_runner import PITSourcePackage
from scripts.historical_backtest import SETTLEMENT_SCHEMA_VERSION_V2, validate_settlement
from scripts.real_report_acceptance import (
    CJO_REQUIRED_MACHINE_GATES,
    evaluate_phase10_production_freeze_acceptance,
    resolve_report_variant,
)
from tests.test_stage36_historical_backtest_pilot import _case, _settlement
from tests.test_stage14_thesis_test_gate import _forward_payload


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
        "purpose": "COMPANY_JUDGMENT_ONLY",
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
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _licensed_industry_pre_cutoff_source() -> dict:
    return {
        "source_id": "AVC:TEST:AC:2026:ORIGINAL",
        "source_type": "LICENSED_INDUSTRY_DATA",
        "official": False,
        "industry_data_contract": {
            "provider_id": "AVC",
            "dataset_id": "room-air-conditioner-retail-tracker",
            "measurement_profile": {"permitted_inference": "WITHIN_PROVIDER_RELATIVE_CHANGE"},
            "metric": {"metric_id": "same_scope_retention", "semantic": "RETAIL_SELL_OUT"},
            "scope": {
                "geography": "中国大陆国内零售市场",
                "product_mapping": {"mapping_id": "AVC-ROOM-AC-v1"},
                "channel_mapping": {"mapping_id": "AVC-RETAIL-v1"},
                "brand_mapping": {"mapping_id": "AVC-GREE-v1"},
                "denominator": {"mapping_id": "AVC-ALL-BRANDS-v1"},
            },
        },
    }


def _licensed_industry_series_contract(source: dict) -> dict:
    contract = source["industry_data_contract"]
    scope = contract["scope"]
    return {
        "pre_cutoff_source_id": source["source_id"],
        "provider_id": contract["provider_id"],
        "dataset_id": contract["dataset_id"],
        "metric_id": contract["metric"]["metric_id"],
        "semantic": contract["metric"]["semantic"],
        "geography": scope["geography"],
        "product_mapping_id": scope["product_mapping"]["mapping_id"],
        "channel_mapping_id": scope["channel_mapping"]["mapping_id"],
        "brand_mapping_id": scope["brand_mapping"]["mapping_id"],
        "denominator_mapping_id": scope["denominator"]["mapping_id"],
    }


def test_adapter_projects_forward_judgments_without_retyping_or_range_midpoint(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)

    ledger = build_calibration_ledger_from_forward_judgments(
        payload,
        simulation_cutoff="2026-08-02T00:00:00+08:00",
        known_source_ids={"AR:TEST:2026"},
    )

    claims = {claim["forward_judgment_id"]: claim for claim in ledger["claims"]}
    assert set(claims) == {"fj.retention", "fj.owner_cash", "fj.value"}
    assert claims["fj.owner_cash"]["prediction"] == payload["forward_judgments"][1]["prediction"]
    assert claims["fj.owner_cash"]["observable_outcome"]["observation_window"] == {
        "opens_after": "2027-08-03T00:00:00+08:00",
        "closes_at": "2029-12-31T18:00:00+08:00",
    }
    assert claims["fj.owner_cash"]["baseline_id"] == "baseline.fj.owner_cash"
    assert claims["fj.owner_cash"]["baseline"] == payload["forward_judgments"][1]["baseline"]
    assert claims["fj.owner_cash"]["transmission"] == payload["forward_judgments"][1]["transmission"]
    assert claims["fj.owner_cash"]["financial_driver_ids"] == []
    assert claims["fj.owner_cash"]["rival_hypothesis_pair_id"] == "RHP:retention-vs-erosion"
    assert claims["fj.owner_cash"]["rival_signal_id"] == "RHPSIG:fj.owner_cash"
    assert ledger["rival_hypothesis_pairs"][0]["discriminators"][0]["claim_id"] == "HBTCLM:fj.retention"
    assert (
        ledger["rival_hypothesis_pairs"][0]["critical_assumptions"]
        == payload["rival_hypothesis_pairs"][0]["critical_assumptions"]
    )
    assert ledger["analogy_transfer_cards"] == payload["analogy_transfer_cards"]


def test_adapter_projects_the_frozen_selection_admission_for_feedback_only(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    selected = next(item for item in payload["forward_judgments"] if item["judgment_id"] == "fj.retention")
    selected["observable_outcome"]["metric_reconstruction_contract"] = {
        "source_targets": [{
            "source_type": "ANNUAL_REPORT",
            "file_scope": "FY2027 H1 annual filing",
            "reported_label": "same_scope_retention",
            "reported_locator": "Operating KPI table / retention",
        }],
        "prohibited_substitutes": ["revenue", "management commentary"],
        "definition_change_action": "MEASUREMENT_MISMATCH",
    }
    payload["selection_admission"] = {
        "status": "SELECTION_ADMITTED",
        "selection_forward_judgment_ids": ["fj.retention"],
        "selection_register_binding": {
            "register_id": "CSR:adapter", "register_fingerprint": "a" * 64,
            "selection_entry_id": "CSRSEL:adapter", "company_id": "COMPANY:adapter",
            "company_cluster_id": "COMPANY:adapter",
        },
    }

    ledger = build_calibration_ledger_from_forward_judgments(
        payload,
        simulation_cutoff="2026-08-02T00:00:00+08:00",
        known_source_ids={"AR:TEST:2026"},
    )

    assert ledger["selection_admission"] == payload["selection_admission"]
    assert (
        ledger["claims"][0]["observable_outcome"]["metric_reconstruction_contract"]
        == selected["observable_outcome"]["metric_reconstruction_contract"]
    )

    selected["observable_outcome"].pop("metric_reconstruction_contract")
    with pytest.raises(ProductionFreezeCaseError, match="metric_reconstruction_contract is incomplete"):
        build_calibration_ledger_from_forward_judgments(
            payload,
            simulation_cutoff="2026-08-02T00:00:00+08:00",
            known_source_ids={"AR:TEST:2026"},
        )


def test_adapter_refuses_to_infer_a_pit_source_for_forward_judgment(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)

    with pytest.raises(ProductionFreezeCaseError, match="not admitted PIT sources"):
        build_calibration_ledger_from_forward_judgments(
            payload,
            simulation_cutoff="2026-08-02T00:00:00+08:00",
            known_source_ids=set(),
        )


def test_adapter_refuses_a_pair_signal_when_it_no_longer_matches_its_frozen_forward_judgment(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["rival_hypothesis_pairs"][0]["discriminators"][0]["primary_prediction"]["value"] = 91.0

    with pytest.raises(ProductionFreezeCaseError, match="primary prediction differs"):
        build_calibration_ledger_from_forward_judgments(
            payload,
            simulation_cutoff="2026-08-02T00:00:00+08:00",
            known_source_ids={"AR:TEST:2026"},
        )


def test_adapter_requires_driver_links_when_the_frozen_bridge_is_enabled(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)

    with pytest.raises(ProductionFreezeCaseError, match="requires financial_driver_ids"):
        build_calibration_ledger_from_forward_judgments(
            payload,
            simulation_cutoff="2026-08-02T00:00:00+08:00",
            known_source_ids={"AR:TEST:2026"},
            known_financial_driver_ids={"FDBDRV:cash"},
        )


def test_adapter_requires_forward_judgment_monitoring_links_for_each_frozen_driver(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    judgment_ids = {str(item["judgment_id"]) for item in payload["forward_judgments"]}
    for judgment in payload["forward_judgments"]:
        judgment["financial_driver_ids"] = ["FDBDRV:cash"]

    projected = build_calibration_ledger_from_forward_judgments(
        payload,
        simulation_cutoff="2026-08-02T00:00:00+08:00",
        known_source_ids={"AR:TEST:2026"},
        known_financial_driver_ids={"FDBDRV:cash"},
        financial_driver_monitoring_links={"FDBDRV:cash": judgment_ids},
        financial_driver_realization_judgment_ids=judgment_ids,
    )
    assert {claim["forward_judgment_id"] for claim in projected["claims"]} == judgment_ids

    with pytest.raises(ProductionFreezeCaseError, match="lacks FDB monitoring links"):
        build_calibration_ledger_from_forward_judgments(
            payload,
            simulation_cutoff="2026-08-02T00:00:00+08:00",
            known_source_ids={"AR:TEST:2026"},
            known_financial_driver_ids={"FDBDRV:cash"},
            financial_driver_monitoring_links={"FDBDRV:cash": {"fj.retention"}},
            financial_driver_realization_judgment_ids=judgment_ids,
        )

    with pytest.raises(ProductionFreezeCaseError, match="realization contract references"):
        build_calibration_ledger_from_forward_judgments(
            payload,
            simulation_cutoff="2026-08-02T00:00:00+08:00",
            known_source_ids={"AR:TEST:2026"},
            known_financial_driver_ids={"FDBDRV:cash"},
            financial_driver_monitoring_links={"FDBDRV:cash": judgment_ids},
            financial_driver_realization_judgment_ids={"fj.not_in_thesis"},
        )


def test_adapter_requires_frozen_driver_monitoring_contract_to_permit_industry_data(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    judgment_ids = {str(item["judgment_id"]) for item in payload["forward_judgments"]}
    for judgment in payload["forward_judgments"]:
        judgment["financial_driver_ids"] = ["FDBDRV:cash"]
    industry_judgment = payload["forward_judgments"][0]
    industry_judgment["observable_outcome"]["allowed_source_types"] = ["LICENSED_INDUSTRY_DATA"]
    industry_judgment["observable_outcome"]["industry_measurement_inference"] = "WITHIN_PROVIDER_RELATIVE_CHANGE"
    source = _licensed_industry_pre_cutoff_source()
    industry_judgment["settlement_contract"]["source_ids"] = [source["source_id"]]
    industry_judgment["observable_outcome"]["licensed_industry_series_contract"] = _licensed_industry_series_contract(source)

    with pytest.raises(ProductionFreezeCaseError, match="allowed_source_types exceed frozen FDB monitoring contracts"):
        build_calibration_ledger_from_forward_judgments(
            payload,
            simulation_cutoff="2026-08-02T00:00:00+08:00",
            known_source_ids={"AR:TEST:2026", source["source_id"]},
            known_sources={source["source_id"]: source},
            known_financial_driver_ids={"FDBDRV:cash"},
            financial_driver_monitoring_links={"FDBDRV:cash": judgment_ids},
            financial_driver_monitoring_source_types={"FDBDRV:cash": {"ANNUAL_REPORT", "INTERIM_REPORT"}},
            financial_driver_realization_judgment_ids=judgment_ids,
        )


def test_adapter_requires_a_licensed_industry_fj_to_keep_the_frozen_monitoring_identity(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["forward_judgments"] = [payload["forward_judgments"][0]]
    payload.pop("rival_hypothesis_pairs", None)
    payload.pop("analogy_transfer_cards", None)
    judgment = payload["forward_judgments"][0]
    judgment["financial_driver_ids"] = ["FDBDRV:competition"]
    judgment["observable_outcome"]["allowed_source_types"] = ["LICENSED_INDUSTRY_DATA"]
    judgment["observable_outcome"]["industry_measurement_inference"] = "WITHIN_PROVIDER_RELATIVE_CHANGE"
    source = _licensed_industry_pre_cutoff_source()
    judgment["settlement_contract"]["source_ids"] = [source["source_id"]]
    judgment["observable_outcome"]["licensed_industry_series_contract"] = _licensed_industry_series_contract(source)
    monitoring_contract = {
        "metric": judgment["prediction"]["metric"],
        "unit": judgment["prediction"]["unit"],
        "measurement_basis": judgment["observable_outcome"]["measurement_basis"],
        "measurement_period": judgment["observable_outcome"]["measurement_period"],
        "observation_window": judgment["settlement_contract"]["observation_window"],
    }
    kwargs = {
        "simulation_cutoff": "2026-08-02T00:00:00+08:00",
        "known_source_ids": {source["source_id"]},
        "known_sources": {source["source_id"]: source},
        "known_financial_driver_ids": {"FDBDRV:competition"},
        "financial_driver_monitoring_links": {"FDBDRV:competition": {judgment["judgment_id"]}},
        "financial_driver_monitoring_source_types": {"FDBDRV:competition": {"LICENSED_INDUSTRY_DATA"}},
        "financial_driver_monitoring_contracts": {"FDBDRV:competition": monitoring_contract},
    }

    projected = build_calibration_ledger_from_forward_judgments(payload, **kwargs)
    assert projected["claims"][0]["forward_judgment_id"] == judgment["judgment_id"]
    assert (
        projected["claims"][0]["observable_outcome"]["licensed_industry_series_contract"]
        == judgment["observable_outcome"]["licensed_industry_series_contract"]
    )

    mismatched = deepcopy(monitoring_contract)
    mismatched["metric"] = "other_market_metric"
    with pytest.raises(ProductionFreezeCaseError, match="licensed industry outcome does not match frozen FDB monitoring contract"):
        build_calibration_ledger_from_forward_judgments(
            payload,
            **{**kwargs, "financial_driver_monitoring_contracts": {"FDBDRV:competition": mismatched}},
        )

    provider_mismatch = deepcopy(source)
    provider_mismatch["industry_data_contract"]["provider_id"] = "OTHER_VENDOR"
    with pytest.raises(ProductionFreezeCaseError, match="provider_id_does_not_match_pre_cutoff_source"):
        build_calibration_ledger_from_forward_judgments(
            payload,
            **{**kwargs, "known_sources": {source["source_id"]: provider_mismatch}},
        )


def test_adapter_blocks_material_owner_cash_without_a_normalized_cash_driver(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    owner_cash_judgment = next(
        item for item in payload["forward_judgments"]
        if item["judgment_id"] == "fj.owner_cash"
    )
    payload["forward_judgments"] = [owner_cash_judgment]
    payload.pop("rival_hypothesis_pairs", None)
    payload.pop("analogy_transfer_cards", None)
    owner_cash_judgment["financial_driver_ids"] = ["FDBDRV:cash"]
    kwargs = {
        "simulation_cutoff": "2026-08-02T00:00:00+08:00",
        "known_source_ids": {"AR:TEST:2026"},
        "known_financial_driver_ids": {"FDBDRV:cash"},
        "financial_driver_monitoring_links": {"FDBDRV:cash": {"fj.owner_cash"}},
        "financial_driver_layers": {"FDBDRV:cash": "CASH_CONVERSION"},
        "financial_driver_cash_normalization_states": {"FDBDRV:cash": "UNKNOWN"},
    }

    with pytest.raises(ProductionFreezeCaseError, match="requires NORMALIZED cash drivers"):
        build_calibration_ledger_from_forward_judgments(payload, **kwargs)

    projected = build_calibration_ledger_from_forward_judgments(
        payload,
        **{**kwargs, "financial_driver_cash_normalization_states": {"FDBDRV:cash": "NORMALIZED"}},
    )
    assert projected["claims"][0]["forward_judgment_id"] == "fj.owner_cash"


def test_adapter_preserves_non_official_industry_contract_in_the_frozen_source_map(tmp_path: Path) -> None:
    source_id = "AVC:000651:AC:2025Q4:ORIGINAL"
    output = tmp_path / "output"
    local_path = output / "pit_sources" / "AVC_000651_AC_2025Q4_ORIGINAL" / "original.csv"
    local_path.parent.mkdir(parents=True)
    local_path.write_text("brand,share\nGREE,24.3\n", encoding="utf-8")
    contract = {
        "schema_version": "phase10-independent-industry-data.v2",
        "provider_id": "AVC", "dataset_id": "room-air-conditioner-retail-tracker",
        "measurement_profile": {
            "methodology_disclosure": "PROVIDER_METHOD_PARTIAL",
            "methodology_locator": {"statement": "供应商口径说明。", "locator": "README.md#methodology"},
            "error_status": "UNQUANTIFIED",
            "permitted_inference": "WITHIN_PROVIDER_RELATIVE_CHANGE",
            "known_limitations": [{"statement": "覆盖范围可能变化。", "conservative_treatment": "不与其他来源平均。"}],
            "disagreement_treatment": "DO_NOT_AVERAGE_REOPEN_MECHANISM",
        },
    }
    source = {
        "source_id": source_id,
        "source_version": "avc-room-ac-retail-2025q4-original",
        "source_type": "LICENSED_INDUSTRY_DATA",
        "official": False,
        "published_at": "2026-01-20T10:00:00+08:00",
        "data_as_of": "2025-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
        "industry_data_contract": contract,
    }
    snapshot = {
        "unresolved_source_ids": [],
        "visible_information": [{
            "source_id": source_id,
            "evidence_source_id": "DOC:000651:licensed-industry:2025-12-31",
            "source_provenance": "PIT_PROJECTED_AFTER_ALLOW_READ",
        }],
    }
    document_manifest = {"documents": [{
        "doc_id": "DOC:000651:licensed-industry:2025-12-31",
        "source_id": source_id,
        "source_version": source["source_version"],
        "published_at": source["published_at"],
        "data_as_of": source["data_as_of"],
        "revision_policy": source["revision_policy"],
        "local_path": local_path.relative_to(output).as_posix(),
        "acquisition_status": "PIT_LINKED_AFTER_ALLOW_READ",
    }]}

    projected = _source_map(snapshot, {"sources": [source]}, document_manifest, output)

    assert projected[0]["official"] is False
    assert projected[0]["industry_data_contract"] == contract


def test_adapter_carries_only_snapshot_hashed_driver_context(tmp_path: Path) -> None:
    bridge_path = tmp_path / "financial_driver_bridge.json"
    bridge = {
        "schema_version": "financial-driver-bridge.v1",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "drivers": [{"driver_id": "FDBDRV:cash", "layer": "CASH_CONVERSION"}],
        "allocation_events": [{"event_id": "FDBEV:cash", "classification": "UNRESOLVED"}],
    }
    _write_json(bridge_path, bridge)
    snapshot = {
        "financial_driver_bridge_required": True,
        "ledger_sha256": {"financial_driver_bridge": hashlib.sha256(bridge_path.read_bytes()).hexdigest()},
    }

    frozen = _frozen_financial_driver_bridge(
        tmp_path, snapshot, expected_analysis_purpose="COMPANY_JUDGMENT_ONLY",
    )

    assert frozen["validation_state"] == "REVIEWABLE"
    assert frozen["analysis_purpose"] == "COMPANY_JUDGMENT_ONLY"
    assert frozen["drivers"] == bridge["drivers"]
    with pytest.raises(ProductionFreezeCaseError, match="does not match case purpose"):
        _frozen_financial_driver_bridge(tmp_path, snapshot, expected_analysis_purpose="INVESTMENT_DECISION")
    bridge["drivers"][0]["driver_id"] = "FDBDRV:rewritten"
    _write_json(bridge_path, bridge)
    with pytest.raises(ProductionFreezeCaseError, match="differs from publication snapshot"):
        _frozen_financial_driver_bridge(tmp_path, snapshot)


def test_adapter_projects_snapshot_hashed_forward_judgments_into_the_reviewed_case_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    thesis = _forward_payload(tmp_path, freeze=False)
    for judgment in thesis["forward_judgments"]:
        judgment["settlement_contract"]["source_ids"] = ["AR:00506:2020"]
        judgment["financial_driver_ids"] = ["FDBDRV:" + judgment["judgment_id"]]
    thesis_path = paths["output"] / "thesis_test.json"
    _write_json(thesis_path, thesis)
    bridge_path = paths["output"] / "financial_driver_bridge.json"
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    bridge["drivers"] = [
        {
            "driver_id": judgment["financial_driver_ids"][0],
            "layer": "CASH_CONVERSION",
            "cash_normalization_contract": {"state": "NORMALIZED"},
            "monitoring_contract": {
                "forward_judgment_ids": [judgment["judgment_id"]],
                "allowed_source_types": judgment["observable_outcome"]["allowed_source_types"],
            },
        }
        for judgment in thesis["forward_judgments"]
    ]
    _write_json(bridge_path, bridge)
    report_text = paths["report"].read_text(encoding="utf-8") + "\n".join(
        f"\n{claim['claim_id']} {claim['statement']}\n"
        for claim in build_calibration_ledger_from_forward_judgments(
            thesis, simulation_cutoff="2021-08-31T18:00:00+08:00", known_source_ids={"AR:00506:2020"},
        )["claims"]
    )
    paths["report"].write_text(report_text, encoding="utf-8")
    snapshot_path = paths["output"] / "publication_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["report_sha256"] = resolve_report_variant(paths["output"])["report_sha256"]
    snapshot["ledger_sha256"]["financial_driver_bridge"] = hashlib.sha256(bridge_path.read_bytes()).hexdigest()
    snapshot["ledger_sha256"]["thesis_test"] = hashlib.sha256(thesis_path.read_bytes()).hexdigest()
    _write_json(snapshot_path, snapshot)
    evaluate_phase10_production_freeze_acceptance(
        sample_id="00506", company_code="00506.HK", output_dir=paths["output"],
        report_period="PIT-2021-08-31", acceptance_root=paths["acceptance_root"],
    )
    case_spec = _v2_case_spec()
    case_spec["calibration_ledger"] = {"source": "FROZEN_FORWARD_JUDGMENTS"}
    pending = _derive(paths, case_spec)
    assert pending["state"] == "INCOMPLETE"
    projected = pending["frozen_case_contract"]["calibration_ledger"]
    assert {item["forward_judgment_id"] for item in projected["claims"]} == {
        "fj.retention", "fj.owner_cash", "fj.value",
    }
    review = paths["root"] / "reviews" / "forward-judgments.json"
    reviewed_spec = deepcopy(case_spec)
    reviewed_spec["calibration_ledger"] = projected
    _write_pass_review(paths, review, case_spec=reviewed_spec)
    case_spec["review_artifact_path"] = str(review)
    result = _derive(paths, case_spec)
    assert result["validation"]["state"] == "REVIEWABLE"
    assert result["case"]["calibration_ledger"] == projected


def test_adapter_refuses_forward_judgments_when_the_snapshot_hash_does_not_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    _write_json(paths["output"] / "thesis_test.json", _forward_payload(tmp_path, freeze=False))
    snapshot = json.loads((paths["output"] / "publication_snapshot.json").read_text(encoding="utf-8"))
    snapshot["ledger_sha256"]["thesis_test"] = "not-the-file-hash"
    _write_json(paths["output"] / "publication_snapshot.json", snapshot)
    case_spec = _v2_case_spec()
    case_spec["calibration_ledger"] = {"source": "FROZEN_FORWARD_JUDGMENTS"}
    with pytest.raises(ProductionFreezeCaseError, match="differs from publication snapshot"):
        _derive(paths, case_spec)


def test_adapter_requires_an_enabled_financial_driver_bridge_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    case_spec = _v2_case_spec(review_artifact_path="reviews/independent.json")
    (paths["output"] / "financial_driver_bridge.json").unlink()
    with pytest.raises(ProductionFreezeCaseError, match="financial_driver_bridge"):
        _derive(paths, case_spec)


def test_adapter_uses_company_judgment_snapshot_profile_without_decision_or_valuation() -> None:
    assert _required_snapshot_gates("COMPANY_JUDGMENT_ONLY", {}) == (
        "claim_evidence", "thesis_test", "insight",
    )
    assert _required_snapshot_gates("COMPANY_JUDGMENT_ONLY", {"financial_driver_bridge_required": True}) == (
        "claim_evidence", "thesis_test", "insight", "financial_driver_bridge",
    )
    assert _required_snapshot_gates("INVESTMENT_DECISION", {}) == (
        "decision", "claim_evidence", "valuation", "thesis_test", "insight",
    )


def test_adapter_requires_snapshot_analysis_purpose_to_match_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    snapshot_path = paths["output"] / "publication_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["analysis_purpose"] = "INVESTMENT_DECISION"
    _write_json(snapshot_path, snapshot)

    with pytest.raises(ProductionFreezeCaseError, match="analysis_purpose does not match case purpose"):
        _derive(paths, _v2_case_spec())


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
        "## 公司判断摘要\n\n"
        "HBTCLM:owner-cash 普通股每股 owner cash 在下一财年不少于 HKD0.20。\n\n"
        "## 经营表现与核心驱动\n\n"
        "Current operating mechanism is stated without a security conclusion.\n\n"
        "## 财务表现与资本配置\n\n"
        "Cash and capital facts remain within the company-judgment boundary.\n\n"
        "## 竞争性机制与早期判别信号\n\n"
        "HBTCLM:minority-cash-access 子公司少数股东现金索取的实际比例尚未被官方披露闭合。\n\n"
        "## 监测、结算与再研究\n\n"
        "The route remains unknown.\n\n"
        "## 公司判断结论与数据边界\n\n"
        "No price, valuation, return, position, or investment action is asserted.\n",
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
    _write_json(output / "analysis_contract.json", {
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
    })
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
    bridge_path = output / "financial_driver_bridge.json"
    _write_json(bridge_path, {
        "schema_version": "financial-driver-bridge.v1",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "drivers": [],
        "allocation_events": [],
    })
    _write_json(output / "publication_snapshot.json", {
        "report_sha256": report_sha256,
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "run_id": "pit-production-test",
        "completion_status": "COMPLETE",
        "v3_enforced": True,
        "financial_driver_bridge_required": True,
        "lifecycle": "MONITORING",
        "gate_states": {
            "official_evidence": "REVIEWABLE",
            "claim_evidence": "DECISION_READY",
            "financial_driver_bridge": "REVIEWABLE",
            "thesis_test": "DECISION_READY",
            "insight": "DECISION_READY",
        },
        "ledger_sha256": {
            "financial_driver_bridge": hashlib.sha256(bridge_path.read_bytes()).hexdigest(),
        },
        "unresolved_source_ids": [],
        "visible_information": [{
            "source_id": "AR:00506:2020",
            "evidence_source_id": "DOC:00506:2020",
            "source_provenance": "PIT_PROJECTED_AFTER_ALLOW_READ",
        }],
    })
    for gate, (filename, accepted) in CJO_REQUIRED_MACHINE_GATES.items():
        if gate in {"completion", "runtime_manifest"}:
            continue
        key = "status" if gate in {"completion", "runtime_manifest", "absolute_quality"} else "state"
        payload = {key: sorted(accepted)[0]}
        if gate == "thesis_test":
            payload.update({
                "forward_judgment_state": "DECISION_READY",
                "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
            })
        if gate == "financial_driver_bridge":
            payload["analysis_purpose"] = "COMPANY_JUDGMENT_ONLY"
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
            "purpose", "route", "forecast", "inputs", "calibration_ledger", "taxes_fees_fx", "price_identity",
        )
    }
    snapshot = json.loads((paths["output"] / "publication_snapshot.json").read_text(encoding="utf-8"))
    frozen_driver_bridge = _frozen_financial_driver_bridge(
        paths["output"],
        snapshot,
        expected_analysis_purpose=str(reviewed_spec["purpose"]),
    )
    if frozen_driver_bridge is not None:
        frozen_case_contract["financial_driver_bridge"] = frozen_driver_bridge
    claim_reviews = [
        {
            "claim_id": claim["claim_id"],
            "disposition": "UNKNOWN_PRESERVED" if claim.get("frozen_disposition") == "UNKNOWN" else "SUPPORTED",
            "source_ids": deepcopy(claim.get("source_ids") or []),
            "notes": ["Prediction, threshold, and measurement contract are frozen."],
        }
        for claim in reviewed_spec["calibration_ledger"].get("claims") or []
        if isinstance(claim, dict)
    ]
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
        "claim_reviews": claim_reviews,
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
    settlement_findings = validate_settlement(settlement, case=written)["invalid_findings"]
    assert "investment_return_outcome:company_judgment_only_requires_not_applicable" in settlement_findings
    assert "frozen_investment_decision_required_for_return_settlement" not in settlement_findings
    assert sentinel.read_bytes() == original_v1


def test_adapter_returns_identified_incomplete_candidate_before_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _production_fixture(tmp_path, monkeypatch)
    output_path = paths["root"] / "historical" / "case.v2.json"

    result = _derive(paths, _v2_case_spec(), output_path)

    assert {key: value for key, value in result.items() if key != "frozen_case_contract"} == {
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
    assert result["frozen_case_contract"]["purpose"] == "COMPANY_JUDGMENT_ONLY"
    assert result["frozen_case_contract"]["calibration_ledger"] == _v2_case_spec()["calibration_ledger"]
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
