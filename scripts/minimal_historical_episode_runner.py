#!/usr/bin/env python3
"""Controller-owned persistence for one Minimal Historical Episode.

The sealed SQLite database is never a custodian input.  A custodian receives
only the measurement contract and an authorization, then returns one official
observation.  This runner alone records that observation and mechanically
settles the sealed database.  All persistence times come from the runner's
execution clock rather than caller-authored timestamps.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
from typing import Any, Callable, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from scripts import minimal_historical_episode as episode
    from scripts import minimal_historical_episode_control_plane as control
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import minimal_historical_episode as episode
    import minimal_historical_episode_control_plane as control


RUNTIME_RECEIPT_SCHEMA_VERSION = "turtle-minimal-historical-episode-runtime-receipt.v1"
SOURCE_RECEIPT_SCHEMA_VERSION = "turtle-minimal-historical-episode-official-source-receipt.v1"
SOURCE_VERIFICATION_INPUT_SCHEMA_VERSION = "turtle-minimal-historical-episode-source-verification-input.v1"
_WHITESPACE = re.compile(r"\s+")
SourceVerifier = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _read_object(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _connect(path: str | Path) -> sqlite3.Connection:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    control.initialize(conn)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized_text(value: str) -> str:
    return _WHITESPACE.sub("", value).replace(",", "").replace("，", "")


def _verification_input(
    path: str | Path, source: dict[str, Any], *, expected_subject_ref: dict[str, Any],
) -> dict[str, Any]:
    verification = _read_object(path)
    required = {
        "schema_version", "subject_ref", "source_id", "source_url", "exact_quote",
        "numeric_value", "unit", "allowed_outputs", "method_transfer_rights",
    }
    if set(verification) != required:
        raise ValueError("source verification input must have the closed v1 shape")
    if verification.get("schema_version") != SOURCE_VERIFICATION_INPUT_SCHEMA_VERSION:
        raise ValueError("source verification input schema is invalid")
    for field in ("source_id", "source_url", "numeric_value", "unit"):
        if verification.get(field) != source.get(field):
            raise ValueError(f"source verification input {field} must match the frozen source")
    if verification.get("allowed_outputs") != episode.ALLOWED_OUTPUTS:
        raise ValueError("source verification input must remain mechanical-settlement-only")
    if verification.get("method_transfer_rights") != episode.NO_METHOD_TRANSFER_RIGHTS:
        raise ValueError("source verification input cannot grant method transfer rights")
    if verification.get("subject_ref") != expected_subject_ref:
        raise ValueError("source verification input subject_ref must match the frozen object identity")
    if not isinstance(verification.get("exact_quote"), str) or not verification["exact_quote"].strip():
        raise ValueError("source verification input exact_quote is required")
    return verification


def _decision_contract_from_measurement(contract: dict[str, Any]) -> dict[str, Any]:
    """Build the legacy synthetic decision object when no separate file is supplied.

    Real runs should pass the independently frozen Decision Contract file.  The
    fallback keeps the original fixture-only runner API usable while still
    forcing the controller to persist and validate the decision object first.
    """
    reference = contract.get("decision_contract_ref")
    if not isinstance(reference, dict):
        raise ValueError("measurement contract must include decision_contract_ref")
    return {
        "schema_version": episode.DECISION_CONTRACT_SCHEMA_VERSION,
        "decision_contract_id": reference.get("decision_contract_id"),
        "decision_contract_version": reference.get("decision_contract_version"),
        "company_id": contract.get("company_id"),
        "issuer_id": contract.get("issuer_id"),
        "cutoff_at": contract.get("cutoff_at"),
        "metric_id": contract.get("metric_id"),
        "window_id": contract.get("window_id"),
        "decision_purpose": episode.DECISION_PURPOSE,
        "roles": deepcopy(contract.get("roles")),
        "object_class": "MINIMAL_HISTORICAL_DECISION_CONTRACT",
        "claim_class": "ONE_METRIC_DIRECTIONAL_DECISION_SCOPE",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _verify_quote_value(verification: dict[str, Any]) -> None:
    if verification.get("unit") != "tonnes":
        raise ValueError("real source verifier currently supports the frozen tonnes metric only")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)亿吨", _normalized_text(verification["exact_quote"]))
    if match is None:
        raise ValueError("official source quote must contain the disclosed value in 亿吨")
    quoted_tonnes = float(match.group(1)) * 100_000_000
    if quoted_tonnes != float(verification.get("numeric_value")):
        raise ValueError("official source quote and declared numeric_value do not match")


def verify_official_pdf_source(
    source: dict[str, Any], verification: dict[str, Any],
) -> dict[str, Any]:
    """Open a CNINFO PDF and match the exact cited field and numeric value."""
    url = source.get("source_url")
    parsed = urlparse(url if isinstance(url, str) else "")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "static.cninfo.com.cn"
        or not parsed.path.startswith("/finalpage/")
        or not parsed.path.lower().endswith(".pdf")
    ):
        raise ValueError("real runner requires an official static.cninfo.com.cn/finalpage PDF")
    quote = verification["exact_quote"]
    _verify_quote_value(verification)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        final_url = response.geturl()
        final_host = urlparse(final_url).hostname
        payload = response.read()
    if final_host != "static.cninfo.com.cn" or not payload.startswith(b"%PDF"):
        raise ValueError("official source retrieval did not return a CNINFO PDF")
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(payload)
        handle.flush()
        extracted = subprocess.run(
            ["pdftotext", "-layout", handle.name, "-"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    if _normalized_text(quote) not in _normalized_text(extracted):
        raise ValueError("official PDF does not contain the exact cited field quote")
    return {
        "schema_version": SOURCE_RECEIPT_SCHEMA_VERSION,
        "verification_state": "OPENED_OFFICIAL_PDF_FIELD_MATCHED",
        "retrieved_at": _now(),
        "subject_ref": deepcopy(verification["subject_ref"]),
        "source_id": source.get("source_id"),
        "source_url": url,
        "field_ref": source.get("field_ref"),
        "exact_quote": quote,
        "numeric_value": source.get("numeric_value"),
        "unit": source.get("unit"),
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def freeze_preoutcome(
    database: str | Path,
    *,
    contract_path: str | Path,
    evidence_path: str | Path,
    prediction_path: str | Path,
    source_verification_path: str | Path,
    decision_contract_path: str | Path | None = None,
    source_verifier: SourceVerifier = verify_official_pdf_source,
    source_receipt_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Freeze the only controller phase allowed to read a prediction payload."""
    contract = _read_object(contract_path)
    decision_contract = (
        _read_object(decision_contract_path)
        if decision_contract_path is not None
        else _decision_contract_from_measurement(contract)
    )
    evidence = _read_object(evidence_path)
    prediction = _read_object(prediction_path)
    verification = _verification_input(
        source_verification_path,
        evidence.get("source", {}),
        expected_subject_ref={
            "object_type": "STATIC_EVIDENCE",
            "object_id": evidence.get("evidence_receipt_id"),
            "object_version": evidence.get("evidence_receipt_version"),
        },
    )
    source_receipt = source_verifier(evidence.get("source", {}), verification)
    conn = _connect(database)
    try:
        decision_frozen_at = _now()
        decision_result = control.register_decision_contract(
            conn, decision_contract, frozen_at=decision_frozen_at,
        )
        contract_frozen_at = _now()
        contract_result = control.register_measurement_contract(
            conn, contract, frozen_at=contract_frozen_at,
        )
        evidence_frozen_at = _now()
        evidence_result = control.register_static_evidence(
            conn, evidence, frozen_at=evidence_frozen_at,
        )
        prediction_frozen_at = _now()
        prediction_result = control.register_prediction(
            conn, prediction, frozen_at=prediction_frozen_at,
        )
    finally:
        conn.close()
    if source_receipt_output_path is not None:
        _write_json(source_receipt_output_path, source_receipt)
    return {
        "stage": "PRE_OUTCOME_FROZEN",
        "decision_contract_id": decision_result["decision_contract_id"],
        "measurement_contract_id": contract_result["measurement_contract_id"],
        "evidence_receipt_id": evidence_result["evidence_receipt_id"],
        "prediction_id": prediction_result["prediction_id"],
        "recorded_chronology": {
            "decision_contract_frozen_at": decision_frozen_at,
            "contract_frozen_at": contract_frozen_at,
            "evidence_frozen_at": evidence_frozen_at,
            "prediction_frozen_at": prediction_frozen_at,
        },
        "source_acquisition": source_receipt,
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def controller_authorize_outcome(
    database: str | Path, *, access_path: str | Path, output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Record controller time and emit the contract-only custodian authorization."""
    access = _read_object(access_path)
    forbidden = {"prediction_id", "predicted_direction", "realised_direction"}.intersection(access)
    if forbidden:
        raise ValueError(f"custodian access contains forbidden fields: {sorted(forbidden)}")
    access["authorized_at"] = _now()
    conn = _connect(database)
    try:
        result = control.authorize_outcome_access(conn, access)
    finally:
        conn.close()
    if output_path is not None:
        _write_json(output_path, access)
    return {**result, "outcome_access": access}


def controller_record_and_settle(
    database: str | Path,
    *,
    observation_path: str | Path,
    source_verification_path: str | Path,
    settlement_id: str,
    observation_output_path: str | Path | None = None,
    settlement_output_path: str | Path | None = None,
    source_receipt_output_path: str | Path | None = None,
    source_verifier: SourceVerifier = verify_official_pdf_source,
) -> dict[str, Any]:
    """Record a custodian observation and create the blank request internally."""
    observation = _read_object(observation_path)
    forbidden = {"prediction_id", "predicted_direction", "realised_direction", "status"}.intersection(observation)
    if forbidden:
        raise ValueError(f"observation contains forbidden caller-authored fields: {sorted(forbidden)}")
    verification = _verification_input(
        source_verification_path,
        observation.get("source", {}),
        expected_subject_ref={
            "object_type": "OUTCOME_OBSERVATION",
            "object_id": observation.get("observation_id"),
        },
    )
    source_receipt = source_verifier(observation.get("source", {}), verification)
    observation["observed_at"] = _now()
    request = {
        "schema_version": episode.SETTLEMENT_REQUEST_SCHEMA_VERSION,
        "settlement_id": settlement_id,
        "measurement_contract_ref": deepcopy(observation["measurement_contract_ref"]),
        "custodian_id": observation["custodian_id"],
        "settled_at": "",
        "object_class": "MINIMAL_HISTORICAL_SETTLEMENT_REQUEST",
        "claim_class": "CUSTODIAN_MECHANICAL_SETTLEMENT_REQUEST",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }
    conn = _connect(database)
    try:
        observation_result = control.register_observation(conn, observation)
        request["settled_at"] = _now()
        settlement_result = control.settle(conn, request)
    finally:
        conn.close()
    if observation_output_path is not None:
        _write_json(observation_output_path, observation)
    if settlement_output_path is not None:
        _write_json(settlement_output_path, settlement_result["settlement"])
    if source_receipt_output_path is not None:
        _write_json(source_receipt_output_path, source_receipt)
    return {
        "stage": "MECHANICALLY_SETTLED",
        "observation_id": observation_result["observation_id"],
        "settlement": settlement_result["settlement"],
        "source_acquisition": source_receipt,
    }


def _identity(row: sqlite3.Row | None, *, id_field: str, at_field: str) -> dict[str, Any] | None:
    if row is None:
        return None
    return {id_field: row[id_field], at_field: row[at_field]}


def public_receipt(
    database: str | Path, *, measurement_contract_id: str, measurement_contract_version: int,
) -> dict[str, Any]:
    """Return chronology and rights without disclosing the prediction direction."""
    conn = _connect(database)
    try:
        contract_row = conn.execute(
            f"""SELECT * FROM {control.CONTRACT_TABLE}
                WHERE measurement_contract_id = ? AND measurement_contract_version = ?""",
            (measurement_contract_id, measurement_contract_version),
        ).fetchone()
        if contract_row is None:
            raise ValueError("measurement contract is not present in the persistent database")
        key = (measurement_contract_id, measurement_contract_version)
        evidence_row = conn.execute(
            f"SELECT * FROM {control.EVIDENCE_TABLE} WHERE measurement_contract_id = ? AND measurement_contract_version = ?",
            key,
        ).fetchone()
        prediction_row = conn.execute(
            f"SELECT * FROM {control.PREDICTION_TABLE} WHERE measurement_contract_id = ? AND measurement_contract_version = ?",
            key,
        ).fetchone()
        access_row = conn.execute(
            f"SELECT * FROM {control.ACCESS_TABLE} WHERE measurement_contract_id = ? AND measurement_contract_version = ?",
            key,
        ).fetchone()
        observation_row = conn.execute(
            f"SELECT * FROM {control.OBSERVATION_TABLE} WHERE measurement_contract_id = ? AND measurement_contract_version = ?",
            key,
        ).fetchone()
        settlement_row = conn.execute(
            f"SELECT * FROM {control.SETTLEMENT_TABLE} WHERE measurement_contract_id = ? AND measurement_contract_version = ?",
            key,
        ).fetchone()
        contract = json.loads(contract_row["payload_json"])
        settlement = json.loads(settlement_row["payload_json"]) if settlement_row is not None else None
        receipt = {
            "schema_version": RUNTIME_RECEIPT_SCHEMA_VERSION,
            "measurement_contract_ref": {
                "measurement_contract_id": measurement_contract_id,
                "measurement_contract_version": measurement_contract_version,
            },
            "company_id": contract["company_id"],
            "metric_id": contract["metric_id"],
            "window_id": contract["window_id"],
            "roles": deepcopy(contract["roles"]),
            "chronology": {
                "measurement_contract": _identity(
                    contract_row, id_field="measurement_contract_id", at_field="frozen_at",
                ),
                "static_evidence": _identity(
                    evidence_row, id_field="evidence_receipt_id", at_field="frozen_at",
                ),
                "prediction": _identity(
                    prediction_row, id_field="prediction_id", at_field="frozen_at",
                ),
                "outcome_access": _identity(
                    access_row, id_field="authorization_id", at_field="authorized_at",
                ),
                "observation": _identity(
                    observation_row, id_field="observation_id", at_field="observed_at",
                ),
                "settlement": _identity(
                    settlement_row, id_field="settlement_id", at_field="settled_at",
                ),
            },
            "settlement": settlement,
            "prediction_visibility_policy": "SEALED_FROM_CUSTODIAN_UNTIL_OBSERVATION_RECORDED; REVIEWER_VISIBLE_AFTER_SETTLEMENT",
            "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
            "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
        }
    finally:
        conn.close()
    return receipt


def verify_source_object(
    object_path: str | Path, *, source_verification_path: str | Path,
) -> dict[str, Any]:
    value = _read_object(object_path)
    source = value.get("source")
    if not isinstance(source, dict):
        raise ValueError("source object is required")
    if value.get("schema_version") == episode.STATIC_EVIDENCE_SCHEMA_VERSION:
        subject_ref = {
            "object_type": "STATIC_EVIDENCE",
            "object_id": value.get("evidence_receipt_id"),
            "object_version": value.get("evidence_receipt_version"),
        }
    elif value.get("schema_version") == episode.OBSERVATION_SCHEMA_VERSION:
        subject_ref = {
            "object_type": "OUTCOME_OBSERVATION",
            "object_id": value.get("observation_id"),
        }
    else:
        raise ValueError("source verification supports only static evidence or outcome observation")
    verification = _verification_input(
        source_verification_path, source, expected_subject_ref=subject_ref,
    )
    return verify_official_pdf_source(source, verification)


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    freeze = commands.add_parser("freeze-preoutcome")
    freeze.add_argument("--database", required=True)
    freeze.add_argument("--contract", required=True)
    freeze.add_argument("--decision-contract")
    freeze.add_argument("--evidence", required=True)
    freeze.add_argument("--prediction", required=True)
    freeze.add_argument("--source-verification", required=True)
    freeze.add_argument("--source-receipt-output", required=True)

    authorize = commands.add_parser("controller-authorize-outcome")
    authorize.add_argument("--database", required=True)
    authorize.add_argument("--access", required=True)
    authorize.add_argument("--output", required=True)

    settle = commands.add_parser("controller-record-and-settle")
    settle.add_argument("--database", required=True)
    settle.add_argument("--observation", required=True)
    settle.add_argument("--source-verification", required=True)
    settle.add_argument("--settlement-id", required=True)
    settle.add_argument("--observation-output", required=True)
    settle.add_argument("--settlement-output", required=True)
    settle.add_argument("--source-receipt-output", required=True)

    verify = commands.add_parser("verify-source")
    verify.add_argument("--object", required=True)
    verify.add_argument("--source-verification", required=True)
    verify.add_argument("--output", required=True)

    receipt = commands.add_parser("export-public-receipt")
    receipt.add_argument("--database", required=True)
    receipt.add_argument("--measurement-contract-id", required=True)
    receipt.add_argument("--measurement-contract-version", type=int, default=1)
    receipt.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "freeze-preoutcome":
        result = freeze_preoutcome(
            args.database,
            contract_path=args.contract,
            decision_contract_path=args.decision_contract,
            evidence_path=args.evidence,
            prediction_path=args.prediction,
            source_verification_path=args.source_verification,
            source_receipt_output_path=args.source_receipt_output,
        )
    elif args.command == "controller-authorize-outcome":
        result = controller_authorize_outcome(
            args.database, access_path=args.access, output_path=args.output,
        )
    elif args.command == "controller-record-and-settle":
        result = controller_record_and_settle(
            args.database,
            observation_path=args.observation,
            source_verification_path=args.source_verification,
            settlement_id=args.settlement_id,
            observation_output_path=args.observation_output,
            settlement_output_path=args.settlement_output,
            source_receipt_output_path=args.source_receipt_output,
        )
    elif args.command == "verify-source":
        result = verify_source_object(
            args.object, source_verification_path=args.source_verification,
        )
        _write_json(args.output, result)
    else:
        result = public_receipt(
            args.database,
            measurement_contract_id=args.measurement_contract_id,
            measurement_contract_version=args.measurement_contract_version,
        )
        _write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
