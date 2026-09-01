from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import current_company_cjo_admission as admission
from scripts import enterprise_judgment_core as core
from scripts.thesis_test_gate import thesis_test_fingerprint
from tests import test_enterprise_judgment_core as core_fixture
from tests import test_financial_driver_bridge as bridge_fixture
from tests import test_stage14_thesis_test_gate as thesis_fixture


def _primary_inputs(tmp_path):
    """Build one entirely synthetic, current-company PRIMARY package."""
    bridge_fixture._prepare(tmp_path)
    source_package = core_fixture._source_package()
    source_package["cutoff_at"] = "2026-08-02T00:00:00+00:00"
    model = core_fixture._model(source_package=source_package)
    model["cutoff_at"] = source_package["cutoff_at"]
    ledger = core_fixture._ledger()
    judgment_input = core_fixture._judgment_input()
    # This test fixture is not a claim about an actual company.  It simply
    # supplies an observed loss-path FJ so the admission gate can prove its
    # binding behaviour rather than stopping at Core's allowed UNKNOWN state.
    judgment_input["forward_judgments"][2].update(
        {"evidence_state": "SUPPORTED", "direction": "DETERIORATES", "status": "OPEN"}
    )
    candidate = core.compile_cjo_candidate(
        model=model,
        ledger=ledger,
        source_package=source_package,
        judgment_input=judgment_input,
    )

    bridge = bridge_fixture._payload(tmp_path, analysis_purpose=admission.ANALYSIS_PURPOSE)
    for driver in bridge["drivers"]:
        driver.pop("model_bindings", None)
    bridge["report_id"] = "SYNTHETIC-CURRENT-CJO"
    bridge["as_of"] = "2026-08-02"
    driver_fjs = {
        "FDBDRV:demand": ["fj.retention"],
        "FDBDRV:margin": ["fj.retention"],
        "FDBDRV:cash": ["fj.owner_cash", "fj.value"],
        "FDBDRV:allocation": ["fj.value"],
    }
    for driver in bridge["drivers"]:
        driver["monitoring_contract"]["forward_judgment_ids"] = driver_fjs[driver["driver_id"]]
    for event in bridge["allocation_events"]:
        thesis_fj = "fj.owner_cash" if event["event_id"] == "FDBEV:financial-products" else "fj.value"
        realization = event["realization_contract"]
        realization["forward_judgment_ids"] = [thesis_fj]
        realization["early_signal"]["forward_judgment_ids"] = [thesis_fj]
        realization["terminal_outcome"]["forward_judgment_ids"] = [thesis_fj]

    thesis = thesis_fixture._selection_bundle_payload(tmp_path)
    thesis["report_id"] = bridge["report_id"]
    thesis["freeze"]["fingerprint"] = thesis_test_fingerprint(thesis)

    def binding(cjo_id, thesis_id, driver_ids, event_ids, variable_ids, transmission_ids):
        cjo_judgment = next(item for item in candidate["forward_judgments"] if item["judgment_id"] == cjo_id)
        thesis_judgment = next(item for item in thesis["forward_judgments"] if item["judgment_id"] == thesis_id)
        return {
            "cjo_forward_judgment_id": cjo_id,
            "thesis_forward_judgment_id": thesis_id,
            "financial_driver_ids": driver_ids,
            "allocation_event_ids": event_ids,
            "cjo_variable_ids": variable_ids,
            "cjo_transmission_ids": transmission_ids,
            "material_to_primary": True,
            "selected_side": "PRIMARY",
            "thesis_mechanism_chain_ids": list(thesis_judgment["mechanism_chain_ids"]),
            "cjo_trace_ids": list(cjo_judgment["trace_ids"]),
            "cjo_direction": cjo_judgment["direction"],
        }

    contract = {
        "schema_version": admission.SCHEMA_VERSION,
        "admission_id": "CCJOADM:SYNTHETIC:2026",
        "analysis_purpose": admission.ANALYSIS_PURPOSE,
        "company_id": candidate["company_id"],
        "report_id": bridge["report_id"],
        "cutoff_at": candidate["cutoff_at"],
        "method_version": candidate["method_version"],
        "source_package_id": source_package["source_package_id"],
        "primary_binding": {
            "rival_hypothesis_pair_id": "RHP:retention-vs-erosion",
            "selected_scenario_id": "primary",
            "central_trace_ids": list(candidate["central_path"]["trace_ids"]),
            "forward_judgment_bindings": [
                binding(
                    "FJ:RETENTION", "fj.retention", ["FDBDRV:demand", "FDBDRV:margin"], [],
                    ["VAR:CUSTOMER_RETENTION"], ["TX:NORMAL_EARNINGS"],
                ),
                binding(
                    "FJ:CASH", "fj.owner_cash", ["FDBDRV:cash"], ["FDBEV:financial-products"],
                    ["VAR:OWNER_CASH"], ["TX:OWNER_CASH"],
                ),
                binding(
                    "FJ:LOSS", "fj.value", ["FDBDRV:cash", "FDBDRV:allocation"], ["FDBEV:titanium"],
                    ["VAR:OWNER_CASH"], ["TX:PERMANENT_LOSS"],
                ),
            ],
        },
    }
    return {
        "model": model,
        "ledger": ledger,
        "source_package": source_package,
        "judgment_input": judgment_input,
        "candidate": candidate,
        "financial_driver_bridge": bridge,
        "thesis_test_ledger": thesis,
        "admission_contract": contract,
    }


def _validate(inputs, tmp_path):
    return admission.validate_current_company_cjo_admission(
        candidate=inputs["candidate"],
        model=inputs["model"],
        ledger=inputs["ledger"],
        source_package=inputs["source_package"],
        admission_contract=inputs["admission_contract"],
        financial_driver_bridge=inputs["financial_driver_bridge"],
        thesis_test_ledger=inputs["thesis_test_ledger"],
        validation_dir=tmp_path,
    )


def _review_binding(candidate, admission_receipt, review):
    return admission.build_current_company_cjo_review_binding(
        candidate=candidate,
        admission=admission_receipt,
        independent_review=review,
    )


def test_primary_requires_exact_identity_observed_bindings_and_can_freeze(tmp_path) -> None:
    inputs = _primary_inputs(tmp_path)

    validation = _validate(inputs, tmp_path)
    assert validation["state"] == admission.PRIMARY_ADMITTED
    assert validation["financial_driver_bridge_validation"]["state"] == "REVIEWABLE"
    assert validation["thesis_test_validation"]["state"] == "DECISION_READY"
    assert validation["admission"]["authority"] == {
        "primary_cjo_admitted": True,
        "overlay_read_allowed": True,
        "report_read_allowed": True,
        "publication_authorization": False,
        "investment_authorization": False,
    }

    compiled = admission.compile_current_company_cjo_candidate(
        **{key: inputs[key] for key in (
            "model", "ledger", "source_package", "judgment_input", "admission_contract",
            "financial_driver_bridge", "thesis_test_ledger",
        )},
        validation_dir=tmp_path,
    )
    review = core_fixture._review(compiled["candidate"])
    frozen = admission.freeze_admitted_current_company_cjo(
        **{key: inputs[key] for key in (
            "model", "ledger", "source_package", "judgment_input", "admission_contract",
            "financial_driver_bridge", "thesis_test_ledger",
        )},
        independent_review=review,
        admission_review=_review_binding(compiled["candidate"], compiled["admission"], review),
        validation_dir=tmp_path,
    )
    assert core.validate_frozen_cjo(frozen["frozen_cjo"])["state"] == "VALID"
    assert frozen["admission"]["status"] == admission.PRIMARY_ADMITTED
    assert admission.validate_frozen_current_company_cjo_admission(
        frozen_cjo=frozen["frozen_cjo"], admission_receipt=frozen["admission"], require_overlay=True,
    )["state"] == "VALID"


def test_complete_underwriting_episode_admits_current_company_without_selection_gate(
    tmp_path,
) -> None:
    inputs = _primary_inputs(tmp_path)
    episode = core_fixture._underwriting_episode()
    episode["cutoff_at"] = inputs["source_package"]["cutoff_at"]
    episode["episode_id"] = "EUE:COMPANY:SYNTHETIC:20260802:BLIND:V1"
    episode["underwriting_thesis"]["thesis_id"] = "UWT:COMPANY:SYNTHETIC:20260802:V1"
    episode["evidence_trace"][0]["source_ref"] = "SRC:OPERATING"
    inputs["admission_contract"]["primary_binding"] = {
        "binding_kind": "ENTERPRISE_UNDERWRITING_EPISODE",
        "episode_id": episode["episode_id"],
        "underwriting_thesis_id": episode["underwriting_thesis"]["thesis_id"],
        "central_trace_ids": list(inputs["candidate"]["central_path"]["trace_ids"]),
    }

    compiled = admission.compile_current_company_cjo_candidate(
        model=inputs["model"],
        ledger=inputs["ledger"],
        source_package=inputs["source_package"],
        judgment_input=inputs["judgment_input"],
        admission_contract=inputs["admission_contract"],
        underwriting_episode=episode,
    )

    assert compiled["admission"]["status"] == admission.PRIMARY_ADMITTED
    assert compiled["candidate"]["underwriting_thesis_projection"]["episode_id"] == episode["episode_id"]
    assert "selection" not in str(compiled["admission"]["primary_binding"]).lower()
    review = core_fixture._review(compiled["candidate"])
    frozen = admission.freeze_admitted_current_company_cjo(
        model=inputs["model"],
        ledger=inputs["ledger"],
        source_package=inputs["source_package"],
        judgment_input=inputs["judgment_input"],
        admission_contract=inputs["admission_contract"],
        underwriting_episode=episode,
        independent_review=review,
        admission_review=_review_binding(
            compiled["candidate"], compiled["admission"], review,
        ),
    )
    assert frozen["admission"]["status"] == admission.PRIMARY_ADMITTED
    assert frozen["frozen_cjo"]["underwriting_thesis_projection"]["episode_id"] == episode["episode_id"]


def test_current_company_review_binds_the_compiled_candidate_and_selected_side(tmp_path) -> None:
    inputs = _primary_inputs(tmp_path)
    compiled = admission.compile_current_company_cjo_candidate(
        **{key: inputs[key] for key in (
            "model", "ledger", "source_package", "judgment_input", "admission_contract",
            "financial_driver_bridge", "thesis_test_ledger",
        )},
        validation_dir=tmp_path,
    )
    review = core_fixture._review(compiled["candidate"])
    review_binding = _review_binding(compiled["candidate"], compiled["admission"], review)

    valid_drift = deepcopy(inputs)
    valid_drift["judgment_input"]["compiled_at"] = "2026-01-03T00:00:00+00:00"
    valid_drift["judgment_input"]["forward_judgments"][0]["claim"] = "Retention remains above the reset baseline on the same boundary."
    with pytest.raises(admission.CurrentCompanyCjoAdmissionError, match="compiled_at_mismatch"):
        admission.freeze_admitted_current_company_cjo(
            **{key: valid_drift[key] for key in (
                "model", "ledger", "source_package", "judgment_input", "admission_contract",
                "financial_driver_bridge", "thesis_test_ledger",
            )},
            independent_review=review,
            admission_review=review_binding,
            validation_dir=tmp_path,
        )

    opposite_side = deepcopy(inputs)
    opposite_side["admission_contract"]["primary_binding"]["forward_judgment_bindings"][0]["selected_side"] = "RIVAL"
    result = _validate(opposite_side, tmp_path)
    assert result["state"] == admission.REJECTED
    assert any("selected_side_must_match_selected_scenario" in finding for finding in result["findings"])


def test_primary_rejects_identity_drift_and_non_normalized_owner_cash(tmp_path) -> None:
    inputs = _primary_inputs(tmp_path)
    drifted = deepcopy(inputs)
    drifted["admission_contract"]["source_package_id"] = "SP:OTHER"
    result = _validate(drifted, tmp_path)
    assert result["state"] == admission.REJECTED
    assert "admission_contract.source_package_id_input_mismatch" in result["findings"]

    cash_unknown = deepcopy(inputs)
    cash = next(item for item in cash_unknown["financial_driver_bridge"]["drivers"] if item["driver_id"] == "FDBDRV:cash")
    cash["cash_normalization_contract"]["state"] = "REPORTED_CASH_STATE_ONLY"
    result = _validate(cash_unknown, tmp_path)
    assert result["state"] == admission.REJECTED
    assert any("owner_cash_requires_normalized_cash_driver:FDBDRV:cash" in finding for finding in result["findings"])


def test_primary_rejects_unknown_selected_thesis_path_and_missing_event_realization(tmp_path) -> None:
    inputs = _primary_inputs(tmp_path)
    unknown_path = deepcopy(inputs)
    pair = unknown_path["thesis_test_ledger"]["rival_hypothesis_pairs"][0]
    pair["critical_assumptions"][0].update({
        "status": "UNKNOWN",
        "conservative_treatment": "Do not use the selected mechanism as a directional path.",
    })
    pair["critical_assumptions"][0].pop("linked_discriminator_ids", None)
    unknown_path["thesis_test_ledger"]["freeze"]["fingerprint"] = thesis_test_fingerprint(
        unknown_path["thesis_test_ledger"]
    )
    result = _validate(unknown_path, tmp_path)
    assert result["state"] == admission.REJECTED
    assert "thesis_test.selected_critical_assumption_unknown" in result["findings"]

    no_realization = deepcopy(inputs)
    event = next(item for item in no_realization["financial_driver_bridge"]["allocation_events"] if item["event_id"] == "FDBEV:titanium")
    event["realization_contract"].pop("terminal_outcome")
    result = _validate(no_realization, tmp_path)
    assert result["state"] == admission.REJECTED
    assert any("allocation_event_realization_not_bound:FDBEV:titanium" in finding for finding in result["findings"])


def test_primary_admission_only_requires_the_operating_judgment_consumed_downstream(tmp_path) -> None:
    inputs = _primary_inputs(tmp_path)
    model = inputs["model"]
    next(
        item for item in model["financial_transmissions"]
        if item["transmission_id"] == "TX:OWNER_CASH"
    )["direction"] = "UNKNOWN"
    next(
        item for item in model["financial_transmissions"]
        if item["transmission_id"] == "TX:PERMANENT_LOSS"
    )["direction"] = "UNKNOWN"
    judgment = inputs["judgment_input"]
    judgment["forward_judgments"][1].update({
        "evidence_state": "MODEL_UNCERTAIN", "direction": "UNKNOWN", "status": "UNKNOWN",
    })
    judgment["forward_judgments"][2].update({
        "evidence_state": "MODEL_UNCERTAIN", "direction": "UNKNOWN", "status": "UNKNOWN",
    })
    inputs["candidate"] = core.compile_cjo_candidate(
        model=model,
        ledger=inputs["ledger"],
        source_package=inputs["source_package"],
        judgment_input=judgment,
    )
    inputs["admission_contract"]["primary_binding"]["forward_judgment_bindings"] = [
        inputs["admission_contract"]["primary_binding"]["forward_judgment_bindings"][0]
    ]
    cash_driver = next(
        item for item in inputs["financial_driver_bridge"]["drivers"]
        if item["driver_id"] == "FDBDRV:cash"
    )
    cash_driver["cash_normalization_contract"]["state"] = "REPORTED_CASH_STATE_ONLY"

    result = _validate(inputs, tmp_path)

    assert result["state"] == admission.PRIMARY_ADMITTED
    assert result["admission"]["authority"]["overlay_read_allowed"] is True
    assert not any("must_all_be_bound" in finding for finding in result["findings"])
    assert not any("owner_cash_requires_normalized" in finding for finding in result["findings"])


@pytest.mark.parametrize("resolution", ["NO_PRIMARY", "MIXED"])
def test_no_primary_and_mixed_are_reviewable_but_never_downstream_primary_inputs(tmp_path, resolution) -> None:
    package = core_fixture._source_package()
    model = core_fixture._model(
        source_package=package,
        owner_cash_direction="DETERIORATES" if resolution == "MIXED" else "IMPROVES",
    )
    ledger = core_fixture._ledger()
    judgment = core_fixture._judgment_input(
        resolution=resolution,
        central=resolution == "MIXED",
    )
    candidate = core.compile_cjo_candidate(
        model=model, ledger=ledger, source_package=package, judgment_input=judgment,
    )
    contract = {
        "schema_version": admission.SCHEMA_VERSION,
        "admission_id": "CCJOADM:ABSTAIN",
        "analysis_purpose": admission.ANALYSIS_PURPOSE,
        "company_id": candidate["company_id"],
        "report_id": "SYNTHETIC-ABSTAIN",
        "cutoff_at": candidate["cutoff_at"],
        "method_version": candidate["method_version"],
        "source_package_id": package["source_package_id"],
    }
    result = admission.validate_current_company_cjo_admission(
        candidate=candidate,
        model=model,
        ledger=ledger,
        source_package=package,
        admission_contract=contract,
    )
    assert result["state"] == admission.REVIEWED_NOT_PRIMARY
    assert result["admission"]["authority"] == {
        "primary_cjo_admitted": False,
        "overlay_read_allowed": False,
        "report_read_allowed": True,
        "publication_authorization": False,
        "investment_authorization": False,
    }
    frozen = admission.freeze_admitted_current_company_cjo(
        model=model,
        ledger=ledger,
        source_package=package,
        judgment_input=judgment,
        admission_contract=contract,
        independent_review=core_fixture._review(candidate),
        admission_review=_review_binding(
            candidate,
            result["admission"],
            core_fixture._review(candidate),
        ),
    )
    assert core.validate_frozen_cjo(frozen["frozen_cjo"])["state"] == "VALID"
    assert frozen["admission"]["status"] == admission.REVIEWED_NOT_PRIMARY


def test_freeze_revalidates_current_inputs_instead_of_trusting_a_prior_admission(tmp_path) -> None:
    inputs = _primary_inputs(tmp_path)
    compiled = admission.compile_current_company_cjo_candidate(
        **{key: inputs[key] for key in (
            "model", "ledger", "source_package", "judgment_input", "admission_contract",
            "financial_driver_bridge", "thesis_test_ledger",
        )},
        validation_dir=tmp_path,
    )
    changed = deepcopy(inputs)
    changed["financial_driver_bridge"]["drivers"][2]["status"] = "UNKNOWN"
    changed["financial_driver_bridge"]["drivers"][2]["observation_ids"] = []
    changed["financial_driver_bridge"]["drivers"][2].update({
        "unknown_reason": "Synthetic only.",
        "conservative_treatment": "Do not treat cash as owner cash.",
    })
    with pytest.raises(admission.CurrentCompanyCjoAdmissionError, match="current_company_cjo_admission_rejected"):
        admission.freeze_admitted_current_company_cjo(
            **{key: changed[key] for key in (
                "model", "ledger", "source_package", "judgment_input", "admission_contract",
                "financial_driver_bridge", "thesis_test_ledger",
            )},
            independent_review=core_fixture._review(compiled["candidate"]),
            admission_review=_review_binding(
                compiled["candidate"], compiled["admission"], core_fixture._review(compiled["candidate"]),
            ),
            validation_dir=tmp_path,
        )
