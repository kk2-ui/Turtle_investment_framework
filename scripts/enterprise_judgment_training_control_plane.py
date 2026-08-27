#!/usr/bin/env python3
"""Canonical shared registry for immutable training selection inputs.

This is a small control-plane registry, not a settlement engine.  It stores
the immutable roster bundle and formal completion/adjudication receipts in the
shared canonical database so production selection can resolve identities by
ID instead of trusting caller-supplied JSON or paths.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sqlite3
from typing import Any

try:
    from scripts import enterprise_judgment_reconstruction as reconstruction
except ModuleNotFoundError:  # pragma: no cover
    import enterprise_judgment_reconstruction as reconstruction


SCHEMA_VERSION = "enterprise-judgment-training-control-plane.v1"
ROSTER_TABLE = "enterprise_judgment_training_roster_freezes"
RECEIPT_TABLE = "enterprise_judgment_training_selection_receipts"
MEASUREMENT_CONTRACT_TABLE = "enterprise_judgment_training_measurement_contracts"
ENTERPRISE_OBSERVATION_TABLE = "enterprise_judgment_training_enterprise_observation_receipts"
ENTERPRISE_SETTLEMENT_TABLE = "enterprise_judgment_training_enterprise_settlements"
ROUND5_ROUTE_TABLE = "enterprise_judgment_training_round5_routes"
ROUND5_ROUTE_ARTIFACT_DIR = (
    Path(__file__).resolve().parents[1]
    / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018"
)
ROUND5_ROUTE_ARTIFACTS = {
    "package": "29_round5_v3_preoutcome_mechanism_package.json",
    "control": "31_round5_v3_preoutcome_control_plane_receipt.json",
    "adapter": "32_round5_v3_adapter_acceptance_receipt.json",
}
ROSTER_OBJECT_CLASS = "ENTERPRISE_JUDGMENT_PRE_OUTCOME_FREEZE"
RECEIPT_SCHEMAS = {
    "enterprise-judgment-feedback-settlement.v1",
    "enterprise-judgment-continuation-feedback-settlement.v1",
    "enterprise-judgment-round3-feedback-settlement.v1",
    "enterprise-mechanism-feedback-superseding-adjudication.v1",
}


class TrainingControlPlaneError(ValueError):
    """A canonical training input cannot be registered or resolved."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _canonical_source_type(value: Any) -> Any:
    if value in {"OFFICIAL_ANNUAL_REPORT", "OFFICIAL_AUDITED_ANNUAL_REPORT"}:
        return "OFFICIAL_ANNUAL_REPORT"
    return value


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load(value: str, *, code: str) -> dict[str, Any]:
    try:
        item = json.loads(value)
    except json.JSONDecodeError as exc:
        raise TrainingControlPlaneError(code, "stored payload is not valid JSON") from exc
    if not isinstance(item, dict):
        raise TrainingControlPlaneError(code, "stored payload must be an object")
    return item


def _instant(value: Any, *, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise TrainingControlPlaneError(f"{field}_invalid", f"{field} must be timezone-aware ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TrainingControlPlaneError(f"{field}_invalid", f"{field} must be timezone-aware ISO-8601")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _ref(value: Any, *, field: str) -> tuple[str, int]:
    if not isinstance(value, dict) or not isinstance(value.get("receipt_id"), str) or not value["receipt_id"].strip():
        raise TrainingControlPlaneError(f"{field}_invalid", f"{field}.receipt_id is required")
    if set(value) != {"receipt_id", "receipt_version"}:
        raise TrainingControlPlaneError(f"{field}_invalid", f"{field} accepts receipt identity only")
    version = value.get("receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise TrainingControlPlaneError(f"{field}_invalid", f"{field}.receipt_version must be a positive integer")
    return value["receipt_id"], version


def _canonical_conn(*, readonly: bool = False) -> sqlite3.Connection:
    path = reconstruction.CANONICAL_REGISTRY_PATH.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if readonly:
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.OperationalError as exc:
            raise TrainingControlPlaneError("canonical_control_plane_unavailable", str(exc)) from exc
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {ROSTER_TABLE} (
                freeze_id TEXT PRIMARY KEY,
                block_id TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {RECEIPT_TABLE} (
                receipt_id TEXT NOT NULL,
                receipt_version INTEGER NOT NULL,
                schema_version TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                freeze_id TEXT,
                block_id TEXT,
                company_id TEXT,
                transition_id TEXT,
                PRIMARY KEY (receipt_id, receipt_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {MEASUREMENT_CONTRACT_TABLE} (
                contract_set_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                company_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {ENTERPRISE_OBSERVATION_TABLE} (
                receipt_id TEXT PRIMARY KEY,
                settlement_id TEXT NOT NULL,
                contract_set_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {ENTERPRISE_SETTLEMENT_TABLE} (
                settlement_id TEXT PRIMARY KEY,
                contract_set_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {ROUND5_ROUTE_TABLE} (
                package_id TEXT PRIMARY KEY,
                control_receipt_id TEXT NOT NULL UNIQUE,
                adapter_acceptance_receipt_id TEXT NOT NULL UNIQUE,
                contract_set_id TEXT NOT NULL UNIQUE,
                accepted_at TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )"""
        )
        receipt_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({RECEIPT_TABLE})")}
        for column in ("freeze_id", "block_id", "company_id", "transition_id"):
            if column not in receipt_columns:
                conn.execute(f"ALTER TABLE {RECEIPT_TABLE} ADD COLUMN {column} TEXT")


def _validate_roster_bundle(bundle: Any) -> dict[str, Any]:
    item = bundle if isinstance(bundle, dict) else {}
    block = item.get("block") if isinstance(item.get("block"), dict) else {}
    freeze = item.get("roster_freeze") if isinstance(item.get("roster_freeze"), dict) else {}
    if freeze.get("schema_version") != "enterprise-judgment-pre-outcome-freeze.v1":
        raise TrainingControlPlaneError("roster_freeze_schema_invalid", "canonical roster must be the formal immutable freeze")
    if freeze.get("object_class") != ROSTER_OBJECT_CLASS or freeze.get("claim_class") != "ROSTER_IMMUTABILITY_BINDING":
        raise TrainingControlPlaneError("roster_freeze_identity_invalid", "canonical roster identity is invalid")
    freeze_id = freeze.get("freeze_id")
    block_id = freeze.get("block_id")
    rows = block.get("company_cutoff_transition_roster")
    ids = freeze.get("company_cutoff_transition_ids")
    if not isinstance(freeze_id, str) or not freeze_id or not isinstance(block_id, str) or not block_id:
        raise TrainingControlPlaneError("roster_freeze_identity_missing", "freeze_id and block_id are required")
    if not isinstance(rows, list) or not rows or not isinstance(ids, list) or [row.get("transition_id") for row in rows] != ids:
        raise TrainingControlPlaneError("roster_freeze_order_invalid", "canonical roster must preserve the immutable row order")
    if [row.get("rank") for row in rows] != list(range(1, len(rows) + 1)):
        raise TrainingControlPlaneError("roster_freeze_rank_invalid", "canonical roster ranks must be contiguous")
    return {"freeze_id": freeze_id, "block_id": block_id, "block": deepcopy(block), "roster_freeze": deepcopy(freeze)}


def register_roster_freeze(bundle: dict[str, Any], *, registered_at: str) -> dict[str, Any]:
    """Register the exact block + immutable freeze bundle in shared storage."""
    canonical = _validate_roster_bundle(bundle)
    timestamp = _instant(registered_at, field="registered_at")
    conn = _canonical_conn()
    try:
        initialize(conn)
        encoded = _json(canonical)
        existing = conn.execute(
            f"SELECT payload_json, registered_at FROM {ROSTER_TABLE} WHERE freeze_id = ?",
            (canonical["freeze_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["registered_at"] != timestamp:
                raise TrainingControlPlaneError("roster_freeze_identity_conflict", "registered roster identity has different content")
            return {"registered": True, "freeze_id": canonical["freeze_id"], "idempotent": True}
        conflict = conn.execute(f"SELECT freeze_id FROM {ROSTER_TABLE} WHERE block_id = ?", (canonical["block_id"],)).fetchone()
        if conflict is not None:
            raise TrainingControlPlaneError("block_has_different_registered_roster", "one block cannot have two canonical roster freezes")
        with conn:
            conn.execute(
                f"INSERT INTO {ROSTER_TABLE} (freeze_id, block_id, payload_json, registered_at) VALUES (?, ?, ?, ?)",
                (canonical["freeze_id"], canonical["block_id"], encoded, timestamp),
            )
        return {"registered": True, "freeze_id": canonical["freeze_id"], "idempotent": False}
    finally:
        conn.close()


def _receipt_identity(receipt: dict[str, Any]) -> tuple[str, int]:
    schema = receipt.get("schema_version")
    if schema not in RECEIPT_SCHEMAS:
        raise TrainingControlPlaneError("receipt_schema_unsupported", "only formal completion/adjudication receipts may be registered")
    if schema == "enterprise-mechanism-feedback-superseding-adjudication.v1":
        receipt_id, version = receipt.get("adjudication_id"), 1
    else:
        receipt_id, version = receipt.get("settlement_id"), 1
    if not isinstance(receipt_id, str) or not receipt_id:
        raise TrainingControlPlaneError("receipt_identity_missing", "formal receipt identity is missing")
    return receipt_id, version


def _receipt_validation_and_binding(
    receipt: dict[str, Any], *, bundle: dict[str, Any], validation_context: dict[str, Any],
) -> dict[str, Any]:
    try:
        from scripts import enterprise_judgment_real_mechanism_training as real_training
        from scripts import enterprise_judgment_v2_training as v2
    except ModuleNotFoundError:  # pragma: no cover
        import enterprise_judgment_real_mechanism_training as real_training
        import enterprise_judgment_v2_training as v2
    block = bundle["block"]
    freeze = bundle["roster_freeze"]
    context = validation_context if isinstance(validation_context, dict) else {}
    schema = receipt.get("schema_version")
    common = {
        "block": block,
        "pre_outcome_roster_freeze": freeze,
        "history_series": context.get("history_series"),
        "h1_package": context.get("h1_package"),
        "source_block_episodes": context.get("source_block_episodes"),
        "source_models": context.get("source_models"),
    }
    if schema == "enterprise-judgment-feedback-settlement.v1":
        validation = v2.validate_feedback_settlement(
            receipt,
            block=block,
            pre_outcome_roster_freeze=freeze,
            history_series=context.get("history_series"),
            h1_package=context.get("h1_package"),
            episodes=context.get("source_block_episodes"),
            enterprise_models=context.get("source_models"),
        )
    elif schema == "enterprise-judgment-continuation-feedback-settlement.v1":
        validation = v2.validate_continuation_feedback_settlement(
            receipt,
            application=context.get("round2_application"),
            selection=context.get("round2_selection"),
            eligibility_register=context.get("round2_eligibility_register"),
            target_episode=context.get("round2_target_episode"),
            target_models=context.get("round2_target_models"),
            source_feedback_settlement=context.get("source_feedback_settlement"),
            completed_feedback_settlements=context.get("completed_feedback_settlements"),
            **common,
        )
    elif schema == "enterprise-judgment-round3-feedback-settlement.v1":
        validation = v2.validate_round3_feedback_settlement(
            receipt,
            application=context.get("round3_application"),
            selection=context.get("round3_selection"),
            round2_chain=context.get("round2_chain"),
            target_episode=context.get("round3_target_episode"),
            target_models=context.get("round3_target_models"),
            completed_feedback_settlements=context.get("completed_feedback_settlements"),
            **common,
        )
    elif schema == "enterprise-mechanism-feedback-superseding-adjudication.v1":
        validation = real_training.validate_superseding_adjudication(
            receipt, block=block, roster_freeze=freeze,
        )
    else:  # guarded by _receipt_identity
        raise TrainingControlPlaneError("receipt_schema_unsupported", "no production validator for receipt schema")
    if not validation["valid"]:
        raise TrainingControlPlaneError(
            "selection_receipt_production_validation_failed", "; ".join(validation["findings"]),
        )
    roster = bundle["block"]["company_cutoff_transition_roster"]
    if schema == "enterprise-mechanism-feedback-superseding-adjudication.v1":
        transition_id = receipt["supersedes"]["transition_id"]
        matches = [row for row in roster if row.get("transition_id") == transition_id]
    else:
        matches = [
            row for row in roster
            if row.get("company_id") == receipt.get("company_id") and row.get("cutoff_at") == receipt.get("cutoff_at")
        ]
    if len(matches) != 1:
        raise TrainingControlPlaneError(
            "selection_receipt_roster_binding_not_unique",
            "validated receipt must bind exactly one immutable company-cutoff transition",
        )
    transition = matches[0]
    return {
        "freeze_id": freeze["freeze_id"],
        "block_id": block["block_id"],
        "company_id": transition["company_id"],
        "transition_id": transition["transition_id"],
    }


def register_selection_receipt(
    receipt: dict[str, Any], *, roster_freeze_ref: dict[str, Any], validation_context: dict[str, Any], registered_at: str,
) -> dict[str, Any]:
    receipt_id, version = _receipt_identity(receipt)
    timestamp = _instant(registered_at, field="registered_at")
    encoded = _json(receipt)
    bundle, _ = resolve_canonical_selection_inputs(roster_freeze_ref, [])
    binding = _receipt_validation_and_binding(
        receipt, bundle=bundle, validation_context=validation_context,
    )
    conn = _canonical_conn()
    try:
        initialize(conn)
        existing = conn.execute(
            f"""SELECT payload_json, schema_version, registered_at, freeze_id, block_id, company_id, transition_id
                FROM {RECEIPT_TABLE} WHERE receipt_id = ? AND receipt_version = ?""",
            (receipt_id, version),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["schema_version"] != receipt["schema_version"] or existing["registered_at"] != timestamp:
                raise TrainingControlPlaneError("selection_receipt_identity_conflict", "registered receipt identity has different content")
            stored_binding = {key: existing[key] for key in binding}
            if any(stored_binding.values()) and stored_binding != binding:
                raise TrainingControlPlaneError("selection_receipt_binding_conflict", "registered receipt has a different immutable roster binding")
            if stored_binding != binding:
                with conn:
                    conn.execute(
                        f"""UPDATE {RECEIPT_TABLE}
                            SET freeze_id = ?, block_id = ?, company_id = ?, transition_id = ?
                            WHERE receipt_id = ? AND receipt_version = ?""",
                        (*binding.values(), receipt_id, version),
                    )
            return {
                "registered": True, "receipt_id": receipt_id, "receipt_version": version,
                "idempotent": True, "binding": binding,
            }
        with conn:
            conn.execute(
                f"""INSERT INTO {RECEIPT_TABLE}
                    (receipt_id, receipt_version, schema_version, payload_json, registered_at, freeze_id, block_id, company_id, transition_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (receipt_id, version, receipt["schema_version"], encoded, timestamp, *binding.values()),
            )
        return {
            "registered": True, "receipt_id": receipt_id, "receipt_version": version,
            "idempotent": False, "binding": binding,
        }
    finally:
        conn.close()


def resolve_canonical_selection_inputs(
    roster_freeze_ref: dict[str, Any], receipt_refs: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Resolve only registered IDs from the shared read-only control plane."""
    freeze_id = roster_freeze_ref.get("freeze_id") if isinstance(roster_freeze_ref, dict) else None
    if not isinstance(freeze_id, str) or not freeze_id or set(roster_freeze_ref) != {"freeze_id"}:
        raise TrainingControlPlaneError("roster_freeze_ref_invalid", "production selection requires freeze_id only")
    if not isinstance(receipt_refs, list) or any(not isinstance(ref, dict) for ref in receipt_refs):
        raise TrainingControlPlaneError("receipt_refs_invalid", "production selection requires receipt references, not payloads")
    conn = _canonical_conn(readonly=True)
    try:
        row = conn.execute(f"SELECT payload_json FROM {ROSTER_TABLE} WHERE freeze_id = ?", (freeze_id,)).fetchone()
        if row is None:
            raise TrainingControlPlaneError("roster_freeze_not_registered", "requested roster freeze is not canonical")
        bundle = _load(row["payload_json"], code="canonical_roster_payload_invalid")
        roster_by_id = {
            item.get("transition_id"): item
            for item in bundle["block"]["company_cutoff_transition_roster"]
        }
        resolved: list[dict[str, Any]] = []
        for index, ref in enumerate(receipt_refs):
            receipt_id, version = _ref(ref, field=f"receipt_refs[{index}]")
            receipt_row = conn.execute(
                f"""SELECT payload_json, freeze_id, block_id, company_id, transition_id
                    FROM {RECEIPT_TABLE} WHERE receipt_id = ? AND receipt_version = ?""",
                (receipt_id, version),
            ).fetchone()
            if receipt_row is None:
                raise TrainingControlPlaneError("selection_receipt_not_registered", f"receipt {receipt_id}@{version} is not canonical")
            transition = roster_by_id.get(receipt_row["transition_id"])
            if (
                receipt_row["freeze_id"] != freeze_id
                or receipt_row["block_id"] != bundle["block"]["block_id"]
                or not isinstance(transition, dict)
                or transition.get("company_id") != receipt_row["company_id"]
            ):
                raise TrainingControlPlaneError(
                    "selection_receipt_canonical_binding_invalid",
                    f"receipt {receipt_id}@{version} lacks a valid immutable roster binding",
                )
            resolved.append(_load(receipt_row["payload_json"], code="canonical_receipt_payload_invalid"))
        return bundle, resolved
    finally:
        conn.close()


def register_measurement_contract(contract: dict[str, Any], *, frozen_at: str) -> dict[str, Any]:
    """Freeze a validated v3 contract; the same ID can never be mutated."""
    try:
        from scripts import enterprise_judgment_real_mechanism_training as training
    except ModuleNotFoundError:  # pragma: no cover
        import enterprise_judgment_real_mechanism_training as training
    validation = training.validate_outcome_measurement_contract(contract)
    if not validation["valid"] or contract.get("schema_version") != training.CONTRACT_SCHEMA_VERSION_V3:
        raise TrainingControlPlaneError(
            "measurement_contract_invalid",
            "; ".join(validation["findings"] or ["only v3 contracts may enter this registry"]),
        )
    timestamp = _instant(frozen_at, field="frozen_at")
    contract_timestamp = _instant(
        contract.get("contract_frozen_at"), field="contract_frozen_at",
    )
    if contract_timestamp != timestamp:
        raise TrainingControlPlaneError("measurement_contract_freeze_time_mismatch", "payload freeze time must equal registry freeze time")
    encoded = _json(contract)
    contract_id = contract["contract_set_id"]
    conn = _canonical_conn()
    try:
        initialize(conn)
        existing = conn.execute(
            f"SELECT payload_json, frozen_at FROM {MEASUREMENT_CONTRACT_TABLE} WHERE contract_set_id = ?",
            (contract_id,),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise TrainingControlPlaneError(
                    "measurement_contract_post_freeze_mutation",
                    "registered measurement contract identity cannot be changed after pre-outcome freeze",
                )
            return {"registered": True, "contract_set_id": contract_id, "idempotent": True}
        with conn:
            conn.execute(
                f"""INSERT INTO {MEASUREMENT_CONTRACT_TABLE}
                    (contract_set_id, schema_version, company_id, cutoff_at, payload_json, frozen_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                (contract_id, contract["schema_version"], contract["company_id"], contract["cutoff_at"], encoded, timestamp),
            )
        return {"registered": True, "contract_set_id": contract_id, "idempotent": False}
    finally:
        conn.close()


def resolve_measurement_contract(contract_set_id: str) -> dict[str, Any]:
    if not isinstance(contract_set_id, str) or not contract_set_id:
        raise TrainingControlPlaneError("measurement_contract_ref_invalid", "contract_set_id is required")
    conn = _canonical_conn(readonly=True)
    try:
        row = conn.execute(
            f"SELECT payload_json FROM {MEASUREMENT_CONTRACT_TABLE} WHERE contract_set_id = ?",
            (contract_set_id,),
        ).fetchone()
        if row is None:
            raise TrainingControlPlaneError("measurement_contract_not_registered", "measurement contract is not canonical")
        return _load(row["payload_json"], code="canonical_measurement_contract_payload_invalid")
    finally:
        conn.close()


def _round5_route_from_artifacts(
    *,
    package: Any,
    control_receipt: Any,
    adapter_acceptance_receipt: Any,
) -> tuple[dict[str, str], dict[str, Any]]:
    package_item = package if isinstance(package, dict) else {}
    control_item = control_receipt if isinstance(control_receipt, dict) else {}
    adapter_item = adapter_acceptance_receipt if isinstance(adapter_acceptance_receipt, dict) else {}
    if package_item.get("schema_version") != "enterprise-real-mechanism-preoutcome-package.v3":
        raise TrainingControlPlaneError("round5_route_package_invalid", "Round 5 route requires the canonical v3 package")
    if control_item.get("schema_version") != "enterprise-real-mechanism-preoutcome-control-plane-receipt.v3":
        raise TrainingControlPlaneError("round5_route_control_receipt_invalid", "Round 5 route requires the canonical v3 control receipt")
    if adapter_item.get("schema_version") != "enterprise-round5-v3-adapter-acceptance-receipt.v1":
        raise TrainingControlPlaneError("round5_route_adapter_receipt_invalid", "Round 5 route requires the canonical adapter acceptance receipt")
    package_id = package_item.get("package_id")
    control_receipt_id = control_item.get("receipt_id")
    adapter_receipt_id = adapter_item.get("receipt_id")
    contract = _mapping(package_item.get("outcome_measurement_contract"))
    contract_set_id = contract.get("contract_set_id")
    identities = (package_id, control_receipt_id, adapter_receipt_id, contract_set_id)
    if any(not isinstance(value, str) or not value for value in identities):
        raise TrainingControlPlaneError("round5_route_identity_missing", "Round 5 route identities are required")
    package_ref = _mapping(control_item.get("preoutcome_package_ref"))
    contract_registration = _mapping(control_item.get("canonical_measurement_contract_registration"))
    adapter_contract = _mapping(adapter_item.get("enterprise_v3_adapter"))
    active_refs = _mapping(adapter_item.get("active_artifact_refs"))
    if (
        package_ref.get("package_id") != package_id
        or package_ref.get("schema_version") != package_item.get("schema_version")
        or contract.get("package_ref") != package_id
        or contract_registration.get("contract_set_id") != contract_set_id
        or adapter_contract.get("contract_set_id") != contract_set_id
        or active_refs.get("package") != package_ref.get("artifact")
        or not isinstance(active_refs.get("preoutcome_control_receipt"), str)
        or not active_refs["preoutcome_control_receipt"]
    ):
        raise TrainingControlPlaneError(
            "round5_route_artifact_binding_invalid",
            "Round 5 package, control receipt, adapter receipt and contract do not form one route",
        )
    canonical_contract = resolve_measurement_contract(contract_set_id)
    if canonical_contract != contract:
        raise TrainingControlPlaneError(
            "round5_route_contract_not_canonical",
            "Round 5 route contract differs from the canonical frozen contract",
        )
    return {
        "package_id": package_id,
        "control_receipt_id": control_receipt_id,
        "adapter_acceptance_receipt_id": adapter_receipt_id,
        "contract_set_id": contract_set_id,
    }, contract


def _read_round5_route_artifact(name: str) -> dict[str, Any]:
    filename = ROUND5_ROUTE_ARTIFACTS[name]
    path = ROUND5_ROUTE_ARTIFACT_DIR / filename
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrainingControlPlaneError(
            "round5_route_canonical_artifact_unavailable",
            f"cannot read canonical Round 5 route artifact {filename}",
        ) from exc
    if not isinstance(value, dict):
        raise TrainingControlPlaneError(
            "round5_route_canonical_artifact_invalid",
            f"canonical Round 5 route artifact {filename} must be an object",
        )
    return value


def bootstrap_round5_route() -> dict[str, Any]:
    """Project the fixed pre-outcome 29/31/32 artifact route into canonical storage."""
    package = _read_round5_route_artifact("package")
    control_receipt = _read_round5_route_artifact("control")
    adapter_acceptance_receipt = _read_round5_route_artifact("adapter")
    route, _contract = _round5_route_from_artifacts(
        package=package,
        control_receipt=control_receipt,
        adapter_acceptance_receipt=adapter_acceptance_receipt,
    )
    package_ref = _mapping(control_receipt.get("preoutcome_package_ref"))
    active_refs = _mapping(adapter_acceptance_receipt.get("active_artifact_refs"))
    if (
        package_ref.get("artifact") != ROUND5_ROUTE_ARTIFACTS["package"]
        or active_refs.get("package") != ROUND5_ROUTE_ARTIFACTS["package"]
        or active_refs.get("preoutcome_control_receipt") != ROUND5_ROUTE_ARTIFACTS["control"]
    ):
        raise TrainingControlPlaneError(
            "round5_route_canonical_artifact_binding_invalid",
            "fixed Round 5 artifacts do not identify the canonical 29/31/32 route",
        )
    accepted_at = _instant(adapter_acceptance_receipt.get("recorded_at"), field="accepted_at")
    registered_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = _canonical_conn()
    try:
        initialize(conn)
        existing = conn.execute(
            f"""SELECT package_id, control_receipt_id, adapter_acceptance_receipt_id,
                       contract_set_id, accepted_at, registered_at
                FROM {ROUND5_ROUTE_TABLE}
                WHERE package_id = ? OR control_receipt_id = ?
                   OR adapter_acceptance_receipt_id = ? OR contract_set_id = ?""",
            (
                route["package_id"], route["control_receipt_id"],
                route["adapter_acceptance_receipt_id"], route["contract_set_id"],
            ),
        ).fetchall()
        if existing:
            if len(existing) != 1 or any(
                row[key] != value for row in existing for key, value in route.items()
            ) or existing[0]["accepted_at"] != accepted_at:
                raise TrainingControlPlaneError(
                    "round5_route_identity_conflict",
                    "a registered Round 5 route identity is bound to different artifacts",
                )
            return {
                "registered": True, "idempotent": True, "accepted_at": accepted_at,
                "registered_at": existing[0]["registered_at"], **deepcopy(route),
            }
        with conn:
            conn.execute(
                f"""INSERT INTO {ROUND5_ROUTE_TABLE}
                    (package_id, control_receipt_id, adapter_acceptance_receipt_id,
                     contract_set_id, accepted_at, registered_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    route["package_id"], route["control_receipt_id"],
                    route["adapter_acceptance_receipt_id"], route["contract_set_id"],
                    accepted_at, registered_at,
                ),
            )
        return {
            "registered": True, "idempotent": False, "accepted_at": accepted_at,
            "registered_at": registered_at, **deepcopy(route),
        }
    finally:
        conn.close()


def resolve_round5_route(package_id: str) -> dict[str, str]:
    if not isinstance(package_id, str) or not package_id:
        raise TrainingControlPlaneError("round5_route_package_id_invalid", "package_id is required")
    conn = _canonical_conn(readonly=True)
    try:
        row = conn.execute(
            f"""SELECT package_id, control_receipt_id, adapter_acceptance_receipt_id,
                       contract_set_id
                FROM {ROUND5_ROUTE_TABLE} WHERE package_id = ?""",
            (package_id,),
        ).fetchone()
        if row is None:
            raise TrainingControlPlaneError("round5_route_not_registered", "Round 5 route is not canonical")
        return {
            "package_id": row["package_id"],
            "control_receipt_id": row["control_receipt_id"],
            "adapter_acceptance_receipt_id": row["adapter_acceptance_receipt_id"],
            "contract_set_id": row["contract_set_id"],
        }
    finally:
        conn.close()


def _enterprise_contract_ref(value: Any) -> tuple[str, int]:
    if not isinstance(value, dict) or set(value) != {"measurement_contract_id", "measurement_contract_version"}:
        raise TrainingControlPlaneError(
            "enterprise_contract_ref_invalid",
            "enterprise receipt must carry a closed measurement contract reference",
        )
    contract_id = value.get("measurement_contract_id")
    version = value.get("measurement_contract_version")
    if not isinstance(contract_id, str) or not contract_id or version != 3:
        raise TrainingControlPlaneError(
            "enterprise_contract_ref_invalid",
            "enterprise receipt must reference a frozen v3 measurement contract",
        )
    return contract_id, version


def _enterprise_contract_cell(contract: dict[str, Any], cell_id: str) -> dict[str, Any]:
    cells = [cell for cell in contract.get("atomic_cells", []) if cell.get("cell_id") == cell_id]
    if len(cells) != 1:
        raise TrainingControlPlaneError(
            "enterprise_cell_not_in_canonical_contract",
            f"cell {cell_id} is not uniquely present in the canonical contract",
        )
    return cells[0]


def _enterprise_observation_shape(receipt: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    item = receipt if isinstance(receipt, dict) else {}
    required = {
        "schema_version", "receipt_id", "settlement_id", "measurement_contract_ref",
        "company_id", "cutoff_at", "custodian_id", "authorization_receipt_id",
        "cell_id", "field_id", "status", "measurement_clock",
        "responsibility_boundary", "unit",
    }
    if set(item).difference(required | {"raw_value", "source", "reason", "sources_considered"}):
        raise TrainingControlPlaneError(
            "enterprise_observation_shape_invalid",
            "enterprise observation receipt contains an unapproved field",
        )
    missing = required - set(item)
    if missing:
        raise TrainingControlPlaneError(
            "enterprise_observation_shape_invalid",
            "enterprise observation receipt is missing " + ",".join(sorted(missing)),
        )
    if item.get("schema_version") != "enterprise-observation-receipt.v1":
        raise TrainingControlPlaneError("enterprise_observation_schema_invalid", "enterprise observation schema is invalid")
    if item.get("status") not in {"OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH"}:
        raise TrainingControlPlaneError("enterprise_observation_status_invalid", "enterprise observation status is invalid")
    contract_id, _ = _enterprise_contract_ref(item.get("measurement_contract_ref"))
    contract = resolve_measurement_contract(contract_id)
    cell = _enterprise_contract_cell(contract, item["cell_id"])
    raw_ids = {raw.get("field_id") for raw in cell.get("raw_input_fields", [])}
    if item["field_id"] not in raw_ids:
        raise TrainingControlPlaneError(
            "enterprise_observation_field_not_in_cell",
            "enterprise observation field is not one of the frozen cell inputs",
        )
    raw = next(raw for raw in cell["raw_input_fields"] if raw["field_id"] == item["field_id"])
    if item["company_id"] != contract.get("company_id") or item["cutoff_at"] != contract.get("cutoff_at"):
        raise TrainingControlPlaneError("enterprise_observation_contract_binding_invalid", "company or cutoff does not match contract")
    if item["measurement_clock"] != raw.get("measurement_clock") or item["responsibility_boundary"] != cell.get("responsibility_boundary"):
        raise TrainingControlPlaneError("enterprise_observation_frozen_identity_mismatch", "clock or responsibility boundary differs from contract")
    if item["unit"] != raw.get("unit"):
        raise TrainingControlPlaneError("enterprise_observation_unit_mismatch", "raw observation unit differs from contract")
    if item["status"] in {"OBSERVED", "MEASUREMENT_MISMATCH"}:
        source = item.get("source")
        if not isinstance(source, dict):
            raise TrainingControlPlaneError("enterprise_observation_source_required", "source evidence is required for sourced observations")
        required_source = {
            "source_id", "source_url", "official_source_type", "issuer_id", "report_period_end",
            "availability_precision", "field_identity", "measurement_clock",
            "responsibility_boundary", "unit", "pdf_page", "field_ref",
            "table_or_note", "line_item", "period_column", "custodian_locator",
        }
        if not required_source.issubset(source):
            raise TrainingControlPlaneError("enterprise_observation_source_incomplete", "source evidence is not page-level complete")
        if source["field_identity"] != item["field_id"] or source["measurement_clock"] != item["measurement_clock"]:
            raise TrainingControlPlaneError("enterprise_observation_source_field_binding_invalid", "source field or clock binding is invalid")
        if source["responsibility_boundary"] != item["responsibility_boundary"] or source["unit"] != item["unit"]:
            raise TrainingControlPlaneError("enterprise_observation_source_boundary_or_unit_invalid", "source boundary or unit binding is invalid")
        if not isinstance(source["pdf_page"], int) or source["pdf_page"] < 1 or source["field_ref"] != f"PDF p.{source['pdf_page']}":
            raise TrainingControlPlaneError("enterprise_observation_page_binding_invalid", "source must identify a PDF page")
        authorized = _mapping(contract.get("source_access"))
        expected_source = {
            "source_id": authorized.get("source_id"),
            "source_url": authorized.get("official_url"),
            "official_source_type": authorized.get("source_type"),
            "issuer_id": authorized.get("issuer_id"),
            "report_period_end": authorized.get("report_period_end"),
            "availability_precision": authorized.get("availability_precision"),
            "source_available_at": authorized.get("source_available_at"),
            "source_available_date": authorized.get("source_available_date"),
        }
        if any(
            (
                _canonical_source_type(source.get(key)) != _canonical_source_type(expected)
                if key == "official_source_type"
                else source.get(key) != expected
            )
            for key, expected in expected_source.items()
        ):
            raise TrainingControlPlaneError("enterprise_observation_authorized_source_mismatch", "source is not the canonical authorized source identity")
        if source.get("availability_precision") == "TIMESTAMP":
            if not isinstance(source.get("source_available_at"), str) or source.get("source_available_date") is not None:
                raise TrainingControlPlaneError("enterprise_observation_source_availability_invalid", "timestamp source availability is invalid")
        elif source.get("availability_precision") == "DATE_ONLY":
            if not isinstance(source.get("source_available_date"), str) or source.get("source_available_at") is not None:
                raise TrainingControlPlaneError("enterprise_observation_source_availability_invalid", "date-only source availability is invalid")
        else:
            raise TrainingControlPlaneError("enterprise_observation_source_availability_invalid", "source availability precision is invalid")
        locator = _mapping(raw.get("locator"))
        if any(source.get(key) != locator.get(key) for key in ("table_or_note", "line_item", "period_column")):
            raise TrainingControlPlaneError("enterprise_observation_locator_mismatch", "source locator differs from frozen raw field locator")
        actual_locator = _mapping(source.get("custodian_locator"))
        if set(actual_locator) != {"table_or_note", "line_item", "period_column"} or any(
            not isinstance(actual_locator.get(key), str) or not actual_locator[key].strip()
            for key in ("table_or_note", "line_item", "period_column")
        ):
            raise TrainingControlPlaneError(
                "enterprise_observation_custodian_locator_invalid",
                "source must preserve the custodian's actual table, line and period locator",
            )
    elif not isinstance(item.get("reason"), str) or not item["reason"]:
        raise TrainingControlPlaneError("enterprise_observation_unknown_reason_required", "unknown observation needs a reason")
    return item, contract


def register_enterprise_observation_receipt(receipt: dict[str, Any], *, registered_at: str) -> dict[str, Any]:
    """Append one canonical raw-field observation receipt.

    The payload is stored as supplied after closed contract validation.  A
    repeated receipt ID is idempotent only when its complete payload is equal;
    there is no update path for an existing observation.
    """
    item, contract = _enterprise_observation_shape(receipt)
    timestamp = _instant(registered_at, field="registered_at")
    encoded = _json(item)
    conn = _canonical_conn()
    try:
        initialize(conn)
        existing = conn.execute(
            f"SELECT payload_json FROM {ENTERPRISE_OBSERVATION_TABLE} WHERE receipt_id = ?",
            (item["receipt_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded:
                raise TrainingControlPlaneError(
                    "enterprise_observation_identity_conflict",
                    "registered observation ID has different content",
                )
            return {
                "registered": True, "receipt_id": item["receipt_id"], "idempotent": True,
                "contract_set_id": contract["contract_set_id"],
            }
        with conn:
            conn.execute(
                f"""INSERT INTO {ENTERPRISE_OBSERVATION_TABLE}
                    (receipt_id, settlement_id, contract_set_id, company_id, cutoff_at, payload_json, registered_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    item["receipt_id"], item["settlement_id"], contract["contract_set_id"],
                    item["company_id"], item["cutoff_at"], encoded, timestamp,
                ),
            )
        return {
            "registered": True, "receipt_id": item["receipt_id"], "idempotent": False,
            "contract_set_id": contract["contract_set_id"],
        }
    finally:
        conn.close()


def _enterprise_decimal(value: Any, *, code: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(code)
    try:
        numeric = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(code) from exc
    if not numeric.is_finite():
        raise ValueError(code)
    return numeric


def _execute_enterprise_formula(
    cell: dict[str, Any], raw_receipts: list[dict[str, Any]],
) -> bool | float:
    formula = cell["formula"]
    input_ids = formula["input_field_ids"]
    by_id = {receipt["field_id"]: receipt for receipt in raw_receipts}
    if list(by_id) != input_ids or len(by_id) != len(input_ids):
        raise ValueError("enterprise_formula_raw_input_coverage_invalid")
    conversions = formula["unit_conversions"]
    if [conversion.get("field_id") for conversion in conversions] != input_ids:
        raise ValueError("enterprise_formula_unit_conversion_order_invalid")
    converted: list[Decimal | bool] = []
    for field_id, conversion in zip(input_ids, conversions, strict=True):
        receipt = by_id[field_id]
        value = receipt.get("raw_value")
        if isinstance(value, bool):
            if conversion.get("from_unit") != receipt.get("unit") or conversion.get("scale") != "1":
                raise ValueError("enterprise_event_unit_conversion_invalid")
            converted.append(value)
            continue
        if conversion.get("from_unit") != receipt.get("unit"):
            raise ValueError("enterprise_formula_source_unit_mismatch")
        try:
            scale = Decimal(str(conversion.get("scale")))
        except InvalidOperation as exc:
            raise ValueError("enterprise_formula_unit_scale_invalid") from exc
        if not scale.is_finite():
            raise ValueError("enterprise_formula_unit_scale_invalid")
        converted.append(_enterprise_decimal(value, code="enterprise_formula_raw_value_invalid") * scale)

    operator = formula["operator"]
    if operator == "EVENT_BOOLEAN":
        if len(converted) != 1 or not isinstance(converted[0], bool):
            raise ValueError("enterprise_event_formula_requires_one_boolean")
        return converted[0]
    if any(isinstance(value, bool) for value in converted):
        raise ValueError("enterprise_numeric_formula_cannot_use_boolean")
    numeric = [value for value in converted if isinstance(value, Decimal)]
    if operator == "RAW_VALUE":
        if len(numeric) != 1:
            raise ValueError("enterprise_raw_value_formula_requires_one_input")
        result = numeric[0]
    elif operator == "PERCENT_CHANGE":
        if len(numeric) != 2 or numeric[0] == 0:
            raise ValueError("enterprise_percent_change_zero_or_invalid_baseline")
        result = (numeric[1] - numeric[0]) / abs(numeric[0])
    elif operator == "RATIO_CHANGE":
        if len(numeric) != 4 or numeric[1] == 0 or numeric[3] == 0:
            raise ValueError("enterprise_ratio_change_zero_or_invalid_denominator")
        baseline_ratio = numeric[0] / numeric[1]
        if baseline_ratio == 0:
            raise ValueError("enterprise_ratio_change_zero_baseline_ratio")
        result = ((numeric[2] / numeric[3]) - baseline_ratio) / abs(baseline_ratio)
    elif operator == "DIFFERENCE":
        if len(numeric) == 2:
            result = numeric[1] - numeric[0]
        elif len(numeric) == 4:
            if numeric[0] == 0 or numeric[2] == 0:
                raise ValueError("enterprise_difference_zero_revenue_denominator")
            result = ((numeric[2] - numeric[3]) / numeric[2]) - ((numeric[0] - numeric[1]) / numeric[0])
        else:
            raise ValueError("enterprise_difference_input_count_invalid")
    else:
        raise ValueError("enterprise_formula_operator_unsupported")
    if not result.is_finite():
        raise ValueError("enterprise_formula_result_not_finite")
    return float(result)


def _enterprise_label(cell: dict[str, Any], value: bool | float) -> str:
    rule = cell["label_rule"]
    if rule["type"] == "EVENT_PRESENCE":
        if not isinstance(value, bool):
            raise ValueError("enterprise_event_label_requires_boolean")
        return "OBSERVED_YES" if value else "OBSERVED_NO"
    if isinstance(value, bool):
        raise ValueError("enterprise_numeric_label_requires_number")
    if value <= float(rule["decrease_lte"]):
        return "OBSERVED_DECREASE"
    if value >= float(rule["increase_gte"]):
        return "OBSERVED_INCREASE"
    return "OBSERVED_STABLE"


def _derive_enterprise_settlement_semantics(
    contract: dict[str, Any], raw_receipts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    expected_pairs = [
        (cell["cell_id"], raw["field_id"])
        for cell in contract["atomic_cells"]
        for raw in cell["raw_input_fields"]
    ]
    supplied_pairs = [
        (receipt.get("cell_id"), receipt.get("field_id"))
        for receipt in raw_receipts
        if isinstance(receipt, dict)
    ]
    if supplied_pairs != expected_pairs or len(set(supplied_pairs)) != len(expected_pairs):
        raise TrainingControlPlaneError(
            "enterprise_settlement_raw_field_coverage_invalid",
            "settlement must preserve the exact frozen cell and raw-field order",
        )
    offset = 0
    cell_results: list[dict[str, Any]] = []
    for cell in contract["atomic_cells"]:
        count = len(cell["raw_input_fields"])
        cell_receipts = raw_receipts[offset:offset + count]
        offset += count
        statuses = {receipt.get("status") for receipt in cell_receipts}
        computed_value: bool | float | None = None
        formula_finding: str | None = None
        if "MEASUREMENT_MISMATCH" in statuses:
            status, label = "MEASUREMENT_MISMATCH", "MEASUREMENT_MISMATCH"
        elif "UNKNOWN" in statuses:
            status, label = "UNKNOWN", "UNKNOWN"
        elif statuses == {"OBSERVED"}:
            try:
                computed_value = _execute_enterprise_formula(cell, cell_receipts)
                label = _enterprise_label(cell, computed_value)
                status = "OBSERVED"
            except ValueError as exc:
                status, label = "MEASUREMENT_MISMATCH", "MEASUREMENT_MISMATCH"
                formula_finding = str(exc)
        else:
            raise TrainingControlPlaneError(
                "enterprise_settlement_raw_status_invalid",
                "raw observation statuses cannot derive a frozen cell result",
            )
        row: dict[str, Any] = {
            "cell_id": cell["cell_id"],
            "status": status,
            "label": label,
            "computed_value": computed_value,
            "mismatch_propagation": "LOCAL_ONLY",
        }
        if formula_finding is not None:
            row["formula_finding"] = formula_finding
        cell_results.append(row)
    counts = {
        status: sum(row["status"] == status for row in cell_results)
        for status in ("OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH")
    }
    coverage = {
        "frozen_cells": len(contract["atomic_cells"]),
        "settled_cells": len(cell_results),
        "observed_cells": counts["OBSERVED"],
        "unknown_cells": counts["UNKNOWN"],
        "measurement_mismatch_cells": counts["MEASUREMENT_MISMATCH"],
    }
    return cell_results, coverage


def _enterprise_settlement_shape(settlement: Any) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    item = settlement if isinstance(settlement, dict) else {}
    required = {
        "schema_version", "settled", "settlement_id", "measurement_contract_ref", "authorization_receipt_id",
        "custodian_id", "company_id", "cutoff_at", "observed_at", "settled_at", "cell_results",
        "raw_observation_receipts", "observation_receipt_ids", "coverage", "rights", "allowed_outputs",
    }
    allowed = required | {"canonical_round5_binding"}
    if required.difference(item) or set(item).difference(allowed):
        raise TrainingControlPlaneError("enterprise_settlement_shape_invalid", "enterprise settlement shape is not closed")
    if item.get("schema_version") != "enterprise-outcome-measurement-settlement.v1" or item.get("settled") is not True:
        raise TrainingControlPlaneError("enterprise_settlement_identity_invalid", "enterprise settlement identity is invalid")
    contract_id, _ = _enterprise_contract_ref(item.get("measurement_contract_ref"))
    contract = resolve_measurement_contract(contract_id)
    package_ref = contract.get("package_ref")
    route_binding = item.get("canonical_round5_binding")
    if isinstance(package_ref, str) and package_ref.startswith("EMFP:"):
        expected_route_keys = {"package_id", "control_receipt_id", "adapter_acceptance_receipt_id"}
        if not isinstance(route_binding, dict) or set(route_binding) != expected_route_keys:
            raise TrainingControlPlaneError(
                "enterprise_settlement_round5_route_binding_required",
                "Round 5 settlement must retain the canonical package/control/adapter route identity",
            )
        if route_binding.get("package_id") != package_ref or any(
            not isinstance(value, str) or not value for value in route_binding.values()
        ):
            raise TrainingControlPlaneError(
                "enterprise_settlement_round5_route_binding_invalid",
                "Round 5 settlement route identity is invalid",
            )
        registered_route = resolve_round5_route(package_ref)
        expected_route = {**route_binding, "contract_set_id": contract_id}
        if registered_route != expected_route:
            raise TrainingControlPlaneError(
                "enterprise_settlement_round5_route_binding_invalid",
                "Round 5 settlement route does not match the canonical registered route",
            )
    elif route_binding is not None:
        raise TrainingControlPlaneError(
            "enterprise_settlement_route_binding_not_allowed",
            "non-Round-5 Enterprise settlement cannot claim a Round 5 route",
        )
    if item.get("company_id") != contract.get("company_id") or item.get("cutoff_at") != contract.get("cutoff_at"):
        raise TrainingControlPlaneError("enterprise_settlement_contract_binding_invalid", "settlement company or cutoff differs from contract")
    cells = item.get("cell_results")
    if not isinstance(cells, list) or len(cells) != len(contract.get("atomic_cells", [])):
        raise TrainingControlPlaneError("enterprise_settlement_cell_coverage_invalid", "settlement must cover every frozen cell")
    expected_cells = [cell["cell_id"] for cell in contract["atomic_cells"]]
    supplied_cells = [row.get("cell_id") for row in cells if isinstance(row, dict)]
    if supplied_cells != expected_cells or len(set(supplied_cells)) != len(expected_cells):
        raise TrainingControlPlaneError("enterprise_settlement_cell_order_invalid", "settlement cell order must equal frozen contract order")
    for row in cells:
        if set(row) != {"cell_id", "status", "label", "computed_value", "mismatch_propagation"} and set(row) != {"cell_id", "status", "label", "computed_value", "mismatch_propagation", "formula_finding"}:
            raise TrainingControlPlaneError("enterprise_settlement_cell_shape_invalid", "settlement cell contains unapproved fields")
        if row["status"] not in {"OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH"} or row["mismatch_propagation"] != "LOCAL_ONLY":
            raise TrainingControlPlaneError("enterprise_settlement_cell_status_invalid", "settlement cell status or propagation is invalid")
    raw_receipts = item.get("raw_observation_receipts")
    if not isinstance(raw_receipts, list):
        raise TrainingControlPlaneError("enterprise_settlement_raw_receipts_invalid", "raw observation receipts are required")
    expected_raw_count = sum(len(cell["raw_input_fields"]) for cell in contract["atomic_cells"])
    if len(raw_receipts) != expected_raw_count or len(item.get("observation_receipt_ids", [])) != expected_raw_count:
        raise TrainingControlPlaneError("enterprise_settlement_raw_coverage_invalid", "settlement must reference every frozen raw input once")
    raw_ids = [row.get("receipt_id") for row in raw_receipts if isinstance(row, dict)]
    if raw_ids != item.get("observation_receipt_ids") or len(set(raw_ids)) != expected_raw_count:
        raise TrainingControlPlaneError("enterprise_settlement_raw_receipt_order_invalid", "settlement raw receipt references are not exact")
    expected_cells, expected_coverage = _derive_enterprise_settlement_semantics(contract, raw_receipts)
    if _json(cells) != _json(expected_cells):
        raise TrainingControlPlaneError(
            "enterprise_settlement_semantics_invalid",
            "cell status, computed value or label differs from the frozen contract and raw observations",
        )
    if _json(item.get("coverage")) != _json(expected_coverage):
        raise TrainingControlPlaneError(
            "enterprise_settlement_coverage_invalid",
            "settlement coverage differs from the derived cell statuses",
        )
    if _json(item.get("rights")) != _json(contract.get("rights")):
        raise TrainingControlPlaneError(
            "enterprise_settlement_rights_invalid",
            "settlement rights must equal the frozen measurement contract rights",
        )
    if item.get("allowed_outputs") != ["ENTERPRISE_OUTCOME_SETTLEMENT_ONLY", "RESEARCH_AGENDA"]:
        raise TrainingControlPlaneError(
            "enterprise_settlement_allowed_outputs_invalid",
            "enterprise settlement outputs are fixed and cannot grant downstream authority",
        )
    return item, contract, raw_receipts


def register_enterprise_settlement(settlement: dict[str, Any], *, registered_at: str) -> dict[str, Any]:
    """Append a canonical Enterprise settlement after raw receipts exist."""
    item, contract, raw_receipts = _enterprise_settlement_shape(settlement)
    timestamp = _instant(registered_at, field="registered_at")
    observed = _instant(item["observed_at"], field="observed_at")
    settled = _instant(item["settled_at"], field="settled_at")
    cutoff = _instant(contract["cutoff_at"], field="cutoff_at")
    if observed <= cutoff:
        raise TrainingControlPlaneError("enterprise_observed_at_must_follow_cutoff", "observed_at must follow cutoff")
    if settled < observed:
        raise TrainingControlPlaneError("enterprise_settled_at_must_follow_observed_at", "settled_at must not precede observed_at")
    authorized = _mapping(contract.get("source_access"))
    for receipt in raw_receipts:
        if receipt.get("status") not in {"OBSERVED", "MEASUREMENT_MISMATCH"}:
            continue
        source = _mapping(receipt.get("source"))
        precision = source.get("availability_precision")
        if precision == "TIMESTAMP":
            available = _instant(source.get("source_available_at"), field="source_available_at")
            if observed < available:
                raise TrainingControlPlaneError("enterprise_observed_at_must_follow_source_availability", "observed_at precedes source availability")
        elif precision == "DATE_ONLY":
            try:
                available_day = datetime.fromisoformat(str(source.get("source_available_date"))).date()
                observed_day = datetime.fromisoformat(observed).date()
            except (TypeError, ValueError) as exc:
                raise TrainingControlPlaneError("enterprise_source_available_date_invalid", "source availability date is invalid") from exc
            if observed_day < available_day:
                raise TrainingControlPlaneError("enterprise_observed_at_must_follow_source_availability", "observed_at precedes source availability")
        else:
            raise TrainingControlPlaneError("enterprise_source_availability_invalid", "source availability precision is invalid")
        if any(
            (
                _canonical_source_type(source.get(key)) != _canonical_source_type(authorized.get(expected))
                if key == "official_source_type"
                else source.get(key) != authorized.get(expected)
            )
            for key, expected in {
            "source_id": "source_id", "source_url": "official_url", "official_source_type": "source_type",
            "issuer_id": "issuer_id", "report_period_end": "report_period_end",
            "availability_precision": "availability_precision", "source_available_at": "source_available_at",
            "source_available_date": "source_available_date",
            }.items()
        ):
            raise TrainingControlPlaneError("enterprise_settlement_authorized_source_mismatch", "settlement source is not canonical")
    encoded = _json(item)
    conn = _canonical_conn()
    try:
        initialize(conn)
        for receipt in raw_receipts:
            row = conn.execute(
                f"SELECT payload_json, settlement_id, contract_set_id FROM {ENTERPRISE_OBSERVATION_TABLE} WHERE receipt_id = ?",
                (receipt.get("receipt_id"),),
            ).fetchone()
            if row is None or row["payload_json"] != _json(receipt) or row["settlement_id"] != item["settlement_id"] or row["contract_set_id"] != contract["contract_set_id"]:
                raise TrainingControlPlaneError("enterprise_settlement_observation_reference_invalid", "settlement does not reference canonical raw receipts")
        existing = conn.execute(
            f"SELECT payload_json FROM {ENTERPRISE_SETTLEMENT_TABLE} WHERE settlement_id = ?",
            (item["settlement_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded:
                raise TrainingControlPlaneError("enterprise_settlement_identity_conflict", "registered settlement identity_conflict: ID has different content")
            return {"registered": True, "settlement_id": item["settlement_id"], "idempotent": True, "coverage": deepcopy(item["coverage"])}
        with conn:
            conn.execute(
                f"""INSERT INTO {ENTERPRISE_SETTLEMENT_TABLE}
                    (settlement_id, contract_set_id, company_id, cutoff_at, payload_json, registered_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                (item["settlement_id"], contract["contract_set_id"], item["company_id"], item["cutoff_at"], encoded, timestamp),
            )
        return {"registered": True, "settlement_id": item["settlement_id"], "idempotent": False, "coverage": deepcopy(item["coverage"])}
    finally:
        conn.close()


def resolve_enterprise_settlement(settlement_id: str) -> dict[str, Any]:
    """Read one immutable Enterprise settlement from the canonical plane."""
    if not isinstance(settlement_id, str) or not settlement_id:
        raise TrainingControlPlaneError("enterprise_settlement_id_invalid", "settlement_id is required")
    conn = _canonical_conn(readonly=True)
    try:
        row = conn.execute(
            f"SELECT payload_json FROM {ENTERPRISE_SETTLEMENT_TABLE} WHERE settlement_id = ?",
            (settlement_id,),
        ).fetchone()
        if row is None:
            raise TrainingControlPlaneError("enterprise_settlement_not_registered", "enterprise settlement is not canonical")
        return _load(row["payload_json"], code="canonical_enterprise_settlement_payload_invalid")
    finally:
        conn.close()


def replay_enterprise_settlement(settlement_id: str) -> dict[str, Any]:
    """Replay the persisted settlement and its canonical raw observation set."""
    settlement = resolve_enterprise_settlement(settlement_id)
    conn = _canonical_conn(readonly=True)
    try:
        rows = conn.execute(
            f"""SELECT payload_json FROM {ENTERPRISE_OBSERVATION_TABLE}
                WHERE settlement_id = ? ORDER BY rowid""",
            (settlement_id,),
        ).fetchall()
        receipts = [_load(row["payload_json"], code="canonical_enterprise_observation_payload_invalid") for row in rows]
    finally:
        conn.close()
    replay = deepcopy(settlement)
    replay["raw_observation_receipts"] = receipts
    replay["observation_receipt_ids"] = [receipt["receipt_id"] for receipt in receipts]
    if replay["raw_observation_receipts"] != settlement["raw_observation_receipts"]:
        raise TrainingControlPlaneError("enterprise_settlement_replay_mismatch", "canonical raw receipts do not replay the settlement")
    return replay


def canonical_control_plane_path() -> str:
    return str(reconstruction.CANONICAL_REGISTRY_PATH.resolve())
