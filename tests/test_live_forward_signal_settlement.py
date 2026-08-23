from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scripts.judgment_learning import build_judgment_learning_note
from scripts.live_forward_signal_settlement import (
    EXPOSURE_ATTESTATION_SCHEMA_VERSION,
    NO_NONCLAIM_RESULT_EXPOSURE,
    OUTCOME_EXPOSURE_BREACH,
    build_live_forward_judgment_feedback,
    main,
    settle_live_forward_signals,
    validate_live_forward_exposure_attestation,
)
from scripts.outcome_acquisition import (
    OUTCOME_EXTRACTION_SCHEMA_VERSION,
    OUTCOME_PACKAGE_SCHEMA_VERSION,
    read_outcome_package,
    validate_live_forward_outcome_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = (
    REPO_ROOT / "docs/development/research/experiments/R-05_prospective_operating_feedback/08_outcome_acquisition_contract.json",
    REPO_ROOT / "docs/development/research/experiments/R-06_prospective_retail_feedback/08_outcome_acquisition_contract.json",
)


def _contract(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _exposure_attestation(contract: dict, read_attestation: dict, settlement_as_of: str) -> dict:
    return {
        "schema_version": EXPOSURE_ATTESTATION_SCHEMA_VERSION,
        "case_id": contract["case_id"], "freeze_id": contract["report_freeze"]["freeze_id"],
        "settlement_as_of": settlement_as_of, "status": NO_NONCLAIM_RESULT_EXPOSURE,
        "pipeline_read_source_ids": [item["source_id"] for item in read_attestation["read_audit"]],
        "nonclaim_exposure_descriptions": [],
    }


def _materialize(contract: dict, *, values: tuple[float, ...]) -> tuple[dict, Path, dict, dict]:
    """Create a synthetic reader package only to exercise the frozen path."""
    directory = tempfile.TemporaryDirectory(dir=REPO_ROOT, prefix="live-forward-settlement-")
    root = Path(directory.name)
    (root / "raw").mkdir()
    (root / "reader").mkdir()
    claims = contract["calibration_ledger"]["claims"]
    sources, observations = [], []
    for index, (claim, value) in enumerate(zip(claims, values, strict=True)):
        outcome = claim["observable_outcome"]
        target = outcome["metric_reconstruction_contract"]["source_targets"][0]
        window = outcome["observation_window"]
        source_id = f"IR:SYNTHETIC:{claim['claim_id']}"
        quote = f"{target['reported_period_anchor']} | Comparative period | {target['reported_label']} was {value}% in the comparable-sales table."
        raw_path, reader_path = f"raw/{index}.html", f"reader/{index}.md"
        root.joinpath(raw_path).write_text("<html>" + quote + "</html>", encoding="utf-8")
        root.joinpath(reader_path).write_text(quote, encoding="utf-8")
        source = {
            "source_id": source_id, "source_type": target["source_type"], "official": True,
            "published_at": (
                "2027-02-15T08:00:00-08:00" if index == 0 else "2027-08-15T08:00:00-07:00"
            ),
            "source_version": "synthetic-result-v1", "data_as_of": outcome["measurement_period"]["label"],
            "revision_policy": "ORIGINAL_VINTAGE", "official_publisher_domain": outcome["publisher_domains"][0],
            "package_path": raw_path, "reader_text_path": reader_path, "candidate_claim_ids": [claim["claim_id"]],
        }
        # The two frozen experiments use different opening dates.  Keep the
        # synthetic source inside each declared window without reading a live release.
        if source["published_at"] <= window["opens_after"]:
            source["published_at"] = (
                "2027-02-20T08:00:00-08:00" if index == 0 else "2027-08-20T08:00:00-07:00"
            )
        sources.append(source)
        observations.append({
            "observation_id": f"LFSOBS:{claim['claim_id']}", "claim_id": claim["claim_id"],
            "metric": outcome["metric"], "value": value, "unit": outcome["unit"],
            "measurement_basis": outcome["measurement_basis"], "measurement_period": outcome["measurement_period"],
            "source_ids": [source_id], "comparability_status": "COMPARABLE",
            "reported_file_scope": target["file_scope"], "reported_label": target["reported_label"],
            "reported_locator": target["reported_locator"], "reported_text": quote,
            "reported_value_text": f"{value}%",
            "reported_period_text": target["reported_period_anchor"],
        })
    manifest = {
        "schema_version": OUTCOME_PACKAGE_SCHEMA_VERSION, "outcome_package_id": "OUTPKG:" + contract["case_id"],
        "case_id": contract["case_id"], "freeze_id": contract["report_freeze"]["freeze_id"],
        "frozen_cutoff": contract["simulation_cutoff"],
        "enumeration": {"status": "COMPLETE", "query_identity": "synthetic official result archive", "source_ids": [item["source_id"] for item in sources]},
        "inventory": sources, "selected_source_ids": [item["source_id"] for item in sources], "source_package_status": "COMPLETE",
        "_temporary_directory": directory,
    }
    as_of = max(claim["observable_outcome"]["observation_window"]["closes_at"] for claim in claims)
    attestation = read_outcome_package(manifest, root, case=contract, settlement_as_of=as_of)
    extraction = {
        "schema_version": OUTCOME_EXTRACTION_SCHEMA_VERSION, "outcome_package_id": manifest["outcome_package_id"],
        "case_id": contract["case_id"], "freeze_id": contract["report_freeze"]["freeze_id"],
        "settlement_as_of": as_of, "observations": observations,
    }
    return manifest, root, attestation, extraction


def test_frozen_live_forward_pair_is_derived_from_read_extraction_but_no_primary_cannot_feed_method_learning() -> None:
    for path in CONTRACTS:
        contract = _contract(path)
        assert validate_live_forward_outcome_contract(contract)["state"] == "REVIEWABLE"
        manifest, root, attestation, extraction = _materialize(contract, values=(1.0, -1.0))
        directory = manifest.pop("_temporary_directory")
        try:
            exposure = _exposure_attestation(contract, attestation, extraction["settlement_as_of"])
            result = settle_live_forward_signals(
                contract, manifest=manifest, package_root=root, read_attestation=attestation,
                exposure_attestation=exposure, extraction=extraction, settlement_id="LFSSET:" + contract["case_id"],
                settlement_as_of=extraction["settlement_as_of"],
            )
            assert result["state"] == "REVIEWABLE"
            assert result["learning_eligibility"] == "MECHANISM_SETTLEMENT_ONLY"
            assert [item["signal_verdict"] for item in result["claim_settlements"]] == ["A_ONLY", "B_ONLY"]
            assert result["pair_settlement"]["verdict"] == "MIXED"
            assert result["pair_settlement"]["selection_status"] == "NO_PRIMARY"

            feedback = build_live_forward_judgment_feedback(result)
            assert feedback["state"] == "MECHANISM_SETTLEMENT_ONLY"
            assert feedback["cards"] == []
        finally:
            directory.cleanup()


def test_live_forward_pair_refuses_a_rewritten_or_unfrozen_signal_predicate() -> None:
    contract = _contract(CONTRACTS[0])
    contract["mechanism_signal_pair"]["signals"][0]["hypothesis_b_prediction"] = {
        "operator": "GREATER_THAN", "value": 0,
    }
    result = validate_live_forward_outcome_contract(contract)
    assert result["state"] == "INVALID"
    assert "mechanism_signal_pair.signals[0]:hypothesis_predictions_must_differ" in result["invalid_findings"]

    gap = _contract(CONTRACTS[0])
    gap["mechanism_signal_pair"]["signals"][0]["hypothesis_b_prediction"] = {
        "operator": "LESS_THAN", "value": 0,
    }
    result = validate_live_forward_outcome_contract(gap)
    assert result["state"] == "INVALID"
    assert "mechanism_signal_pair.signals[0]:hypothesis_predictions_must_partition_observation_space" in result["invalid_findings"]

    missing = _contract(CONTRACTS[0])
    missing["mechanism_signal_pair"]["signals"] = []
    result = validate_live_forward_outcome_contract(missing)
    assert result["state"] == "INCOMPLETE"
    assert "mechanism_signal_pair:signals_missing" in result["incomplete_findings"]

    reversed_windows = _contract(CONTRACTS[0])
    reversed_windows["calibration_ledger"]["claims"][1]["observable_outcome"]["observation_window"]["opens_after"] = "2027-03-01T00:00:00-08:00"
    result = validate_live_forward_outcome_contract(reversed_windows)
    assert result["state"] == "INVALID"
    assert "mechanism_signal_pair:early_signal_must_close_before_continuation_opens" in result["invalid_findings"]

    identity_missing = _contract(CONTRACTS[0])
    del identity_missing["research_identity"]
    result = validate_live_forward_outcome_contract(identity_missing)
    assert result["state"] == "INCOMPLETE"
    assert "research_identity:company_cluster_id_missing" in result["incomplete_findings"]


def test_live_forward_pair_keeps_early_results_partial_and_definition_failure_non_diagnostic() -> None:
    contract = _contract(CONTRACTS[0])
    manifest, root, attestation, extraction = _materialize(contract, values=(1.0, -1.0))
    directory = manifest.pop("_temporary_directory")
    try:
        exposure = _exposure_attestation(contract, attestation, extraction["settlement_as_of"])
        partial = json.loads(json.dumps(extraction))
        second = partial["observations"].pop()
        result = settle_live_forward_signals(
            contract, manifest=manifest, package_root=root, read_attestation=attestation,
            exposure_attestation=exposure, extraction=partial, settlement_id="LFSSET:partial", settlement_as_of=partial["settlement_as_of"],
        )
        assert result["state"] == "REVIEWABLE"
        assert result["pair_settlement"]["state"] == "PARTIAL"
        assert result["pair_settlement"]["verdict"] == "NOT_YET_DUE"

        partial["non_diagnostic_resolutions"] = [{
            "claim_id": second["claim_id"], "resolution": "MEASUREMENT_MISMATCH",
            "source_ids": second["source_ids"], "reported_label": second["reported_label"],
            "reported_locator": second["reported_locator"], "reported_text": second["reported_text"],
        }]
        result = settle_live_forward_signals(
            contract, manifest=manifest, package_root=root, read_attestation=attestation,
            exposure_attestation=exposure, extraction=partial, settlement_id="LFSSET:mismatch", settlement_as_of=partial["settlement_as_of"],
        )
        assert result["state"] == "REVIEWABLE"
        assert result["pair_settlement"]["state"] == "CLOSED"
        assert result["pair_settlement"]["verdict"] == "NOT_DIAGNOSTIC"
    finally:
        directory.cleanup()


def test_live_forward_feedback_locks_learning_note_to_frozen_experiment_and_company_cluster() -> None:
    contract = _contract(CONTRACTS[0])
    manifest, root, attestation, extraction = _materialize(contract, values=(1.0, 1.0))
    directory = manifest.pop("_temporary_directory")
    try:
        exposure = _exposure_attestation(contract, attestation, extraction["settlement_as_of"])
        settlement = settle_live_forward_signals(
            contract, manifest=manifest, package_root=root, read_attestation=attestation,
            exposure_attestation=exposure, extraction=extraction, settlement_id="LFSSET:identity", settlement_as_of=extraction["settlement_as_of"],
        )
        feedback = build_live_forward_judgment_feedback(settlement)
        from scripts.judgment_learning import JudgmentLearningError
        try:
            build_judgment_learning_note(
                feedback, note_id="LNOTE:identity:mismatch", claim_id="R05-S1", disposition="RETAIN",
                feedback_ref="/tmp/live-forward-feedback.json",
                state_scope="Customer transactions.", measurement_scope="Frozen issuer metric.",
                learning_basis="Derived signal.", next_research_change="Use a different company.",
                experiment_id="R-06", company_cluster_id="COMPANY:WMT.US", root_cause_classes=["REASONING"],
                failure_loci=["MECHANISM"], economic_failure_loci=["MECHANISM"],
                recorded_at="2026-08-21T00:00:00+00:00",
            )
            assert False, "a feedback-bound note must reject a substituted company cluster"
        except JudgmentLearningError as exc:
            assert "experiment_id_feedback_mismatch" in str(exc)
            assert "company_cluster_id_feedback_mismatch" in str(exc)
    finally:
        directory.cleanup()


def test_live_forward_settlement_cli_only_projects_existing_artifacts() -> None:
    contract = _contract(CONTRACTS[0])
    manifest, root, attestation, extraction = _materialize(contract, values=(1.0, 1.0))
    directory = manifest.pop("_temporary_directory")
    try:
        paths = {
            "contract": root / "contract.json", "manifest": root / "manifest.json",
            "attestation": root / "attestation.json", "exposure": root / "exposure.json", "extraction": root / "extraction.json",
            "event_root": root / "event-output",
        }
        exposure = _exposure_attestation(contract, attestation, extraction["settlement_as_of"])
        for name in ("contract", "manifest", "attestation", "exposure", "extraction"):
            payload = {"contract": contract, "manifest": manifest, "attestation": attestation, "exposure": exposure, "extraction": extraction}[name]
            paths[name].write_text(json.dumps(payload), encoding="utf-8")
        assert main([
            "settle", str(paths["contract"]), str(paths["manifest"]), str(root), str(paths["attestation"]), str(paths["exposure"]), str(paths["extraction"]),
            "--settlement-id", "LFSSET:cli", "--settlement-as-of", extraction["settlement_as_of"], "--event-root", str(paths["event_root"]),
        ]) == 0
        settlement_path = paths["event_root"] / "outcome_events" / "LFSSET:cli" / "09_signal_settlement.json"
        feedback_path = paths["event_root"] / "outcome_events" / "LFSSET:cli" / "10_judgment_feedback.json"
        generated = json.loads(settlement_path.read_text(encoding="utf-8"))
        assert generated["pair_settlement"]["verdict"] == "SUPPORTS_HYPOTHESIS_A"
        assert main(["feedback", str(settlement_path), "--event-root", str(paths["event_root"])]) == 0
        feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
        assert feedback["state"] == "MECHANISM_SETTLEMENT_ONLY"
        assert feedback["cards"] == []
        try:
            main([
                "settle", str(paths["contract"]), str(paths["manifest"]), str(root), str(paths["attestation"]), str(paths["exposure"]), str(paths["extraction"]),
                "--settlement-id", "LFSSET:cli", "--settlement-as-of", extraction["settlement_as_of"], "--event-root", str(paths["event_root"]),
            ])
            assert False, "a repeat event ID must not overwrite the first settlement"
        except FileExistsError as exc:
            assert "event_output_already_exists" in str(exc)
    finally:
        directory.cleanup()


def test_nonclaim_outcome_exposure_keeps_mechanical_settlement_but_blocks_learning() -> None:
    contract = _contract(CONTRACTS[0])
    manifest, root, attestation, extraction = _materialize(contract, values=(1.0, 1.0))
    directory = manifest.pop("_temporary_directory")
    try:
        exposure = _exposure_attestation(contract, attestation, extraction["settlement_as_of"])
        exposure["status"] = OUTCOME_EXPOSURE_BREACH
        exposure["nonclaim_exposure_descriptions"] = ["FY2026 Q4 result body was read before R05-S1 became due."]
        assert validate_live_forward_exposure_attestation(
            exposure, contract=contract, read_attestation=attestation,
            settlement_as_of=extraction["settlement_as_of"],
        )["state"] == "REVIEWABLE"
        settlement = settle_live_forward_signals(
            contract, manifest=manifest, package_root=root, read_attestation=attestation,
            exposure_attestation=exposure, extraction=extraction,
            settlement_id="LFSSET:exposed", settlement_as_of=extraction["settlement_as_of"],
        )
        assert settlement["state"] == "REVIEWABLE"
        assert settlement["pair_settlement"]["verdict"] == "SUPPORTS_HYPOTHESIS_A"
        assert settlement["learning_eligibility"] == "MECHANISM_SETTLEMENT_ONLY"
        feedback = build_live_forward_judgment_feedback(settlement)
        assert feedback["state"] == "MECHANISM_SETTLEMENT_ONLY"
        assert feedback["cards"] == []
        from scripts.judgment_learning import JudgmentLearningError
        try:
            build_judgment_learning_note(
                feedback, note_id="LNOTE:exposed", claim_id="R05-S1", disposition="RETAIN",
                feedback_ref="/tmp/live-forward-feedback.json",
                state_scope="Customer transactions.", measurement_scope="Frozen issuer metric.",
                learning_basis="This must not be accepted after outcome exposure.",
                next_research_change="Use a different company.", experiment_id="R-05",
                company_cluster_id="COMPANY:SBUX.US", root_cause_classes=["REASONING"],
                failure_loci=["MECHANISM"], economic_failure_loci=["MECHANISM"],
                recorded_at="2026-08-21T00:00:00+00:00",
            )
            assert False, "an exposed outcome cannot create a learning note"
        except JudgmentLearningError as exc:
            assert "claim_id_not_in_feedback" in str(exc)

        missing = _exposure_attestation(contract, attestation, extraction["settlement_as_of"])
        missing["pipeline_read_source_ids"] = []
        result = settle_live_forward_signals(
            contract, manifest=manifest, package_root=root, read_attestation=attestation,
            exposure_attestation=missing, extraction=extraction,
            settlement_id="LFSSET:missing-attestation", settlement_as_of=extraction["settlement_as_of"],
        )
        assert result["state"] == "INVALID"
        assert "exposure_attestation:pipeline_read_source_ids_do_not_match_read_audit" in result["invalid_findings"]
    finally:
        directory.cleanup()
