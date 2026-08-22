#!/usr/bin/env python3
"""Mechanically settle a lightweight, frozen H-A/H-B signal probe.

This is deliberately smaller than a ``COMPANY_JUDGMENT_ONLY`` historical
backtest.  R-05/R-06 do not select a central path, estimate value, or make an
investment decision.  They only ask whether the two frozen mechanisms receive
different support from a pre-specified operating signal sequence.

The module accepts an observation only after ``outcome_acquisition`` has
replayed the frozen source, reader text, metric mapping and version policy.
It derives ``A_ONLY``/``B_ONLY`` itself; callers cannot enter a winner.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from scripts.outcome_acquisition import (
    OUTCOME_EXTRACTION_SCHEMA_VERSION,
    validate_live_forward_outcome_contract,
    validate_outcome_extraction,
)


SETTLEMENT_SCHEMA_VERSION = "turtle-live-forward-signal-settlement.v1"
FEEDBACK_SCHEMA_VERSION = "judgment-feedback-card.v2"
EXPOSURE_ATTESTATION_SCHEMA_VERSION = "turtle-live-forward-exposure-attestation.v1"
NO_NONCLAIM_RESULT_EXPOSURE = "NO_NONCLAIM_RESULT_EXPOSURE"
OUTCOME_EXPOSURE_BREACH = "OUTCOME_EXPOSURE_BREACH"
EXPOSURE_STATUSES = {NO_NONCLAIM_RESULT_EXPOSURE, OUTCOME_EXPOSURE_BREACH}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _matches(prediction: dict[str, Any], value: Any) -> bool:
    observed = _number(value)
    threshold = _number(prediction.get("value")) if isinstance(prediction, dict) else None
    if observed is None or threshold is None:
        raise ValueError("non-numeric frozen signal prediction or observation")
    return {
        "GREATER_THAN": observed > threshold,
        "GREATER_THAN_OR_EQUAL": observed >= threshold,
        "LESS_THAN": observed < threshold,
        "LESS_THAN_OR_EQUAL": observed <= threshold,
        "EQUALS": observed == threshold,
    }.get(prediction.get("operator"), False)


def _signal_verdict(signal: dict[str, Any], observation: dict[str, Any]) -> str:
    a_matches = _matches(signal["hypothesis_a_prediction"], observation.get("value"))
    b_matches = _matches(signal["hypothesis_b_prediction"], observation.get("value"))
    if a_matches and not b_matches:
        return "A_ONLY"
    if b_matches and not a_matches:
        return "B_ONLY"
    # A valid signal contract normally partitions the observation space.  If
    # it does not, neither overlap nor a gap may be re-described as evidence.
    return "NOT_DIAGNOSTIC"


def validate_live_forward_exposure_attestation(
    exposure_attestation: dict[str, Any], *, contract: dict[str, Any], read_attestation: dict[str, Any],
    settlement_as_of: str,
) -> dict[str, Any]:
    """Keep non-claim outcome exposure out of human-learning feedback.

    The existing reader audit proves which result bodies entered the pipeline.
    It cannot prove what a researcher saw elsewhere, so this small companion
    requires an explicit disclosure.  A declared breach does not erase the
    mechanical settlement; it only makes that settlement ineligible for a
    learning note or a replication claim.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(exposure_attestation, dict):
        return {"state": "INVALID", "invalid_findings": ["exposure_attestation_not_object"], "incomplete_findings": []}
    if exposure_attestation.get("schema_version") != EXPOSURE_ATTESTATION_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    for field, expected in (
        ("case_id", contract.get("case_id")),
        ("freeze_id", (contract.get("report_freeze") or {}).get("freeze_id")),
        ("settlement_as_of", settlement_as_of),
    ):
        value = exposure_attestation.get(field)
        if not isinstance(value, str) or not value.strip():
            incomplete.append(field + "_missing")
        elif value != expected:
            invalid.append(field + "_does_not_match_bound_artifact")
    status = exposure_attestation.get("status")
    if status not in EXPOSURE_STATUSES:
        invalid.append("status_invalid")
    read_source_ids = exposure_attestation.get("pipeline_read_source_ids")
    if not isinstance(read_source_ids, list) or not all(isinstance(item, str) and item.strip() for item in read_source_ids):
        incomplete.append("pipeline_read_source_ids_missing_or_invalid")
    else:
        expected_source_ids = {
            str(item.get("source_id") or "")
            for item in read_attestation.get("read_audit") or []
            if isinstance(item, dict) and str(item.get("source_id") or "")
        }
        if set(read_source_ids) != expected_source_ids or len(read_source_ids) != len(set(read_source_ids)):
            invalid.append("pipeline_read_source_ids_do_not_match_read_audit")
    descriptions = exposure_attestation.get("nonclaim_exposure_descriptions")
    if not isinstance(descriptions, list) or not all(isinstance(item, str) and item.strip() for item in descriptions):
        invalid.append("nonclaim_exposure_descriptions_invalid")
    elif status == NO_NONCLAIM_RESULT_EXPOSURE and descriptions:
        invalid.append("no_exposure_status_cannot_list_nonclaim_exposure")
    elif status == OUTCOME_EXPOSURE_BREACH and not descriptions:
        incomplete.append("breach_requires_nonclaim_exposure_description")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": invalid, "incomplete_findings": incomplete}


def settle_live_forward_signals(
    contract: dict[str, Any], *, manifest: dict[str, Any], package_root: str | Path,
    read_attestation: dict[str, Any], exposure_attestation: dict[str, Any], extraction: dict[str, Any], settlement_id: str,
    settlement_as_of: str,
) -> dict[str, Any]:
    """Derive a sequence verdict from a validated post-freeze extraction.

    ``PARTIAL`` is the expected state after the early signal.  A complete
    sequence remains a signal-level result: it supports one frozen hypothesis
    about the observed arrow, never a company conclusion or path selection.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    contract_result = validate_live_forward_outcome_contract(contract)
    invalid.extend("contract:" + item for item in contract_result["invalid_findings"])
    incomplete.extend("contract:" + item for item in contract_result["incomplete_findings"])
    pair = contract.get("mechanism_signal_pair") if isinstance(contract.get("mechanism_signal_pair"), dict) else {}
    if not pair:
        incomplete.append("mechanism_signal_pair_missing")
    if extraction.get("schema_version") != OUTCOME_EXTRACTION_SCHEMA_VERSION:
        invalid.append("extraction_schema_version_invalid")
    extraction_result = validate_outcome_extraction(
        extraction, manifest=manifest, package_root=package_root,
        read_attestation=read_attestation, case=contract, settlement_as_of=settlement_as_of,
    )
    invalid.extend("extraction:" + item for item in extraction_result["invalid_findings"])
    incomplete.extend("extraction:" + item for item in extraction_result["incomplete_findings"])
    exposure_result = validate_live_forward_exposure_attestation(
        exposure_attestation, contract=contract, read_attestation=read_attestation,
        settlement_as_of=settlement_as_of,
    )
    invalid.extend("exposure_attestation:" + item for item in exposure_result["invalid_findings"])
    incomplete.extend("exposure_attestation:" + item for item in exposure_result["incomplete_findings"])
    if not str(settlement_id or "").strip():
        incomplete.append("settlement_id_missing")
    if invalid or incomplete:
        return {
            "schema_version": SETTLEMENT_SCHEMA_VERSION,
            "case_id": contract.get("case_id"), "freeze_id": (contract.get("report_freeze") or {}).get("freeze_id"),
            "settlement_id": settlement_id, "settlement_as_of": settlement_as_of,
            "state": "INVALID" if invalid else "INCOMPLETE",
            "invalid_findings": invalid, "incomplete_findings": incomplete,
            "claim_settlements": [], "pair_settlement": {},
        }

    observations = {
        str(item.get("claim_id") or ""): item
        for item in extraction.get("observations") or []
        if isinstance(item, dict) and str(item.get("claim_id") or "")
    }
    non_diagnostic = {
        str(item.get("claim_id") or ""): str(item.get("resolution") or "")
        for item in extraction.get("non_diagnostic_resolutions") or []
        if isinstance(item, dict) and str(item.get("claim_id") or "")
    }
    claim_settlements: list[dict[str, Any]] = []
    for signal in pair.get("signals") or []:
        claim_id = str(signal.get("claim_id") or "")
        item = {
            "claim_id": claim_id,
            "signal_id": signal.get("signal_id"),
            "stage": signal.get("stage"),
            "frozen_locator": signal.get("frozen_locator"),
        }
        if claim_id in non_diagnostic:
            item.update({"status": "NOT_CALCULABLE", "signal_verdict": "NOT_DIAGNOSTIC", "resolution": non_diagnostic[claim_id]})
        elif claim_id not in observations:
            item.update({"status": "NOT_YET_DUE", "signal_verdict": "NOT_YET_DUE"})
        else:
            observation = observations[claim_id]
            item.update({
                "status": "CALCULATED", "observation_id": observation.get("observation_id"),
                "value": observation.get("value"), "unit": observation.get("unit"),
                "signal_verdict": _signal_verdict(signal, observation),
            })
        claim_settlements.append(item)

    verdicts = [str(item["signal_verdict"]) for item in claim_settlements]
    if "NOT_DIAGNOSTIC" in verdicts:
        pair_state, pair_verdict = "CLOSED", "NOT_DIAGNOSTIC"
    elif "NOT_YET_DUE" in verdicts:
        pair_state, pair_verdict = "PARTIAL", "NOT_YET_DUE"
    elif verdicts and all(verdict == "A_ONLY" for verdict in verdicts):
        pair_state, pair_verdict = "CLOSED", "SUPPORTS_HYPOTHESIS_A"
    elif verdicts and all(verdict == "B_ONLY" for verdict in verdicts):
        pair_state, pair_verdict = "CLOSED", "SUPPORTS_HYPOTHESIS_B"
    else:
        pair_state, pair_verdict = "CLOSED", "MIXED"
    return {
        "schema_version": SETTLEMENT_SCHEMA_VERSION,
        "case_id": contract.get("case_id"), "freeze_id": (contract.get("report_freeze") or {}).get("freeze_id"),
        "experiment_id": ((contract.get("research_identity") or {}).get("experiment_id")),
        "company_cluster_id": ((contract.get("research_identity") or {}).get("company_cluster_id")),
        "settlement_id": settlement_id, "settlement_as_of": settlement_as_of,
        "state": "REVIEWABLE", "invalid_findings": [], "incomplete_findings": [],
        "claim_settlements": claim_settlements,
        "outcome_exposure": {
            "status": exposure_attestation.get("status"),
            "nonclaim_exposure_descriptions": list(exposure_attestation.get("nonclaim_exposure_descriptions") or []),
        },
        "learning_eligibility": (
            "MECHANISM_SETTLEMENT_ONLY"
            if str(pair.get("selection_status") or "NO_PRIMARY").upper() != "SELECTION_ADMITTED"
            else (
                "ELIGIBLE"
                if exposure_attestation.get("status") == NO_NONCLAIM_RESULT_EXPOSURE
                else "OUTCOME_EXPOSED_TRAINING_ONLY"
            )
        ),
        "pair_settlement": {
            "pair_id": pair.get("pair_id"), "selection_status": pair.get("selection_status"),
            "hypothesis_a_id": pair.get("hypothesis_a_id"), "hypothesis_b_id": pair.get("hypothesis_b_id"),
            "state": pair_state, "verdict": pair_verdict,
            "scope": "MECHANISM_SIGNAL_ONLY_NO_COMPANY_CONCLUSION_OR_SELECTION_LEARNING",
        },
    }


def build_live_forward_judgment_feedback(settlement: dict[str, Any]) -> dict[str, Any]:
    """Project an immutable, derived signal settlement into learning input.

    The feedback preserves the frozen selection status.  A ``NO_PRIMARY``
    signal probe can improve an evidence contract but is never selection or
    method-learning evidence.
    """
    if settlement.get("schema_version") != SETTLEMENT_SCHEMA_VERSION or settlement.get("state") != "REVIEWABLE":
        raise ValueError("live forward settlement is not reviewable")
    if settlement.get("learning_eligibility") in {"OUTCOME_EXPOSED_TRAINING_ONLY", "MECHANISM_SETTLEMENT_ONLY"}:
        return {
            "schema_version": FEEDBACK_SCHEMA_VERSION, "case_id": settlement.get("case_id"),
            "freeze_id": settlement.get("freeze_id"), "settlement_id": settlement.get("settlement_id"),
            "experiment_id": settlement.get("experiment_id"), "company_cluster_id": settlement.get("company_cluster_id"),
            "state": settlement.get("learning_eligibility"),
            "outcome_exposure": settlement.get("outcome_exposure"),
            "pair_settlement": settlement.get("pair_settlement"),
            "cards": [],
        }
    pair = settlement.get("pair_settlement") if isinstance(settlement.get("pair_settlement"), dict) else {}
    selection_status = str(pair.get("selection_status") or "NO_PRIMARY").upper()
    cards: list[dict[str, Any]] = []
    for item in settlement.get("claim_settlements") or []:
        if not isinstance(item, dict):
            continue
        verdict = item.get("signal_verdict")
        derived = {
            "state": "DERIVED_FROM_FROZEN_HYPOTHESIS_SIGNAL",
            "pair_id": pair.get("pair_id"), "signal_id": item.get("signal_id"),
            "signal_stage": item.get("stage"), "signal_verdict": verdict,
            "pair_verdict": pair.get("verdict"),
            "selection_status": selection_status,
        }
        cards.append({
            "claim_id": item.get("claim_id"), "forward_judgment_id": item.get("signal_id"),
            "settlement_status": item.get("status"),
            "judgment_outcome": {"status": verdict},
            "increment_vs_baseline": (
                "BASELINE_NONDISCRIMATING" if selection_status != "SELECTION_ADMITTED" else "SELECTION_COMPARISON_PENDING"
            ),
            "rival_hypothesis_feedback": derived,
        })
    return {
        "schema_version": FEEDBACK_SCHEMA_VERSION, "case_id": settlement.get("case_id"),
        "freeze_id": settlement.get("freeze_id"), "settlement_id": settlement.get("settlement_id"),
        "experiment_id": settlement.get("experiment_id"), "company_cluster_id": settlement.get("company_cluster_id"),
        "cards": cards,
    }


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON payload must be an object: " + str(path))
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def event_output_paths(event_root: str | Path, settlement_id: str) -> dict[str, Path]:
    """Return the append-only location for one settled result event.

    A signal pair has more than one clock.  In particular R-05/R-06 can settle
    S1 before S2.  Fixed ``09``/``10`` filenames would make the second event
    replace the first; the settlement ID is therefore part of the path, not
    merely JSON metadata.
    """
    event_id = str(settlement_id or "").strip()
    if not event_id or not all(char.isalnum() or char in "._:-" for char in event_id):
        raise ValueError("settlement_id_invalid_for_event_path")
    event_dir = Path(event_root) / "outcome_events" / event_id
    return {
        "settlement": event_dir / "09_signal_settlement.json",
        "feedback": event_dir / "10_judgment_feedback.json",
    }


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError("event_output_already_exists:" + str(path))
    _write_json(path, value)


def main(argv: Iterable[str] | None = None) -> int:
    """Run only the already-frozen post-cutoff settlement projection."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    settle = commands.add_parser("settle")
    settle.add_argument("contract", type=Path)
    settle.add_argument("manifest", type=Path)
    settle.add_argument("package_root", type=Path)
    settle.add_argument("read_attestation", type=Path)
    settle.add_argument("exposure_attestation", type=Path)
    settle.add_argument("extraction", type=Path)
    settle.add_argument("--settlement-id", required=True)
    settle.add_argument("--settlement-as-of", required=True)
    settle.add_argument("--event-root", type=Path, required=True)
    feedback = commands.add_parser("feedback")
    feedback.add_argument("settlement", type=Path)
    feedback.add_argument("--event-root", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "settle":
        result = settle_live_forward_signals(
            _load_json(args.contract), manifest=_load_json(args.manifest), package_root=args.package_root,
            read_attestation=_load_json(args.read_attestation), exposure_attestation=_load_json(args.exposure_attestation), extraction=_load_json(args.extraction),
            settlement_id=args.settlement_id, settlement_as_of=args.settlement_as_of,
        )
        output = event_output_paths(args.event_root, args.settlement_id)["settlement"]
        _write_new_json(output, result)
        print(json.dumps({"written": str(output), "state": result["state"]}, ensure_ascii=False))
        return 0 if result["state"] == "REVIEWABLE" else 1
    settlement = _load_json(args.settlement)
    result = build_live_forward_judgment_feedback(settlement)
    output = event_output_paths(args.event_root, str(settlement.get("settlement_id") or ""))["feedback"]
    _write_new_json(output, result)
    print(json.dumps({"written": str(output), "cards": len(result["cards"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
