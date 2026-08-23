#!/usr/bin/env python3
"""Register and project Turtle's historical-first judgment training program.

The program is deliberately above the historical backtest and feedback engines.
It decides which episodes may change the method, which are frozen holdouts, and
which are live deployment sentinels. A live disclosure wait is therefore a
lane state, never a global training failure.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.historical_backtest import validate_case
    from scripts import judgment_feedback_control as feedback_control
except ModuleNotFoundError:
    from historical_backtest import validate_case
    import judgment_feedback_control as feedback_control


SCHEMA_VERSION = "judgment-training-program.v1"
STATUS_SCHEMA_VERSION = "judgment-training-program-status.v1"
PROGRAM_STATES = {"DRAFT", "ACTIVE"}
LANES = {
    "HISTORICAL_TRAINING",
    "HISTORICAL_HOLDOUT",
    "HISTORICAL_TEACHING",
    "LIVE_SENTINEL",
}
PROVENANCE_ROLES = {
    "HISTORICAL_SELF_REPLAY",
    "ARCHIVED_EX_ANTE_EXTERNAL",
    "RESULT_KNOWN_TEACHING",
    "REAL_FORWARD",
}
OUTCOME_ACCESS_STATES = {"PIT_OUTCOME_SEALED", "OUTCOME_EXPOSED", "NOT_YET_RELEASED"}
HOLDOUT_AXES = {"COMPANY", "TIME", "COMPANY_AND_TIME"}
ARTIFACT_FIELDS = {
    "freeze_ref",
    "case_ref",
}
ARTIFACT_ORDER = (
    "freeze_ref",
    "case_ref",
)
JSON_ARTIFACT_FIELDS = set(ARTIFACT_ORDER) - {"freeze_ref"}


class TrainingProgramError(ValueError):
    """A contract error callers can report without a traceback."""


def _parse_time(value: Any, field: str) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrainingProgramError(f"cannot read JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise TrainingProgramError(f"JSON artifact must be an object: {path}")
    return payload


def _artifact_path(reference: str, *, contract_path: Path | None) -> Path:
    path = Path(reference.split("#", 1)[0]).expanduser()
    if not path.is_absolute() and contract_path is not None:
        path = contract_path.parent / path
    return path.resolve()


def _required_text(value: Any, field: str, findings: list[str]) -> str:
    text = str(value or "").strip()
    if not text:
        findings.append(field + "_missing")
    return text


def _validate_episode(
    episode: Any, *, index: int, method_frozen_at: datetime | None,
    contract_path: Path | None, validate_artifacts: bool,
) -> tuple[list[str], dict[str, Any] | None]:
    findings: list[str] = []
    prefix = f"episodes[{index}]"
    if not isinstance(episode, dict):
        return [prefix + "_not_object"], None
    allowed = {
        "training_episode_id", "case_id", "company_id", "company_cluster_id",
        "industry_id", "decision_domain", "cutoff_at", "outcome_not_before",
        "lane", "provenance_role", "outcome_access", "holdout_axis", "artifacts",
    }
    unexpected = sorted(set(episode) - allowed)
    if unexpected:
        findings.append(prefix + ".unexpected_fields:" + ",".join(unexpected))
    for field in (
        "training_episode_id", "case_id", "company_id", "company_cluster_id",
        "industry_id", "decision_domain",
    ):
        _required_text(episode.get(field), prefix + "." + field, findings)
    episode_id = str(episode.get("training_episode_id") or "")
    if episode_id and not re.fullmatch(r"JTE:[A-Za-z0-9._:-]+", episode_id):
        findings.append(prefix + ".training_episode_id_invalid")
    cutoff = _parse_time(episode.get("cutoff_at"), prefix + ".cutoff_at")
    outcome_not_before = _parse_time(episode.get("outcome_not_before"), prefix + ".outcome_not_before")
    if cutoff is None:
        findings.append(prefix + ".cutoff_at_invalid")
    if outcome_not_before is None:
        findings.append(prefix + ".outcome_not_before_invalid")
    if cutoff is not None and outcome_not_before is not None and outcome_not_before <= cutoff:
        findings.append(prefix + ".outcome_not_after_cutoff")

    lane = str(episode.get("lane") or "").upper()
    provenance = str(episode.get("provenance_role") or "").upper()
    outcome_access = str(episode.get("outcome_access") or "").upper()
    if lane not in LANES:
        findings.append(prefix + ".lane_invalid")
    if provenance not in PROVENANCE_ROLES:
        findings.append(prefix + ".provenance_role_invalid")
    if outcome_access not in OUTCOME_ACCESS_STATES:
        findings.append(prefix + ".outcome_access_invalid")

    historical_blind_roles = {"HISTORICAL_SELF_REPLAY", "ARCHIVED_EX_ANTE_EXTERNAL"}
    if lane == "HISTORICAL_TRAINING":
        if provenance not in historical_blind_roles or outcome_access != "PIT_OUTCOME_SEALED":
            findings.append(prefix + ".historical_training_requires_sealed_pit_provenance")
        if episode.get("holdout_axis") is not None:
            findings.append(prefix + ".training_holdout_axis_forbidden")
    elif lane == "HISTORICAL_HOLDOUT":
        if provenance not in historical_blind_roles or outcome_access != "PIT_OUTCOME_SEALED":
            findings.append(prefix + ".historical_holdout_requires_sealed_pit_provenance")
        if episode.get("holdout_axis") not in HOLDOUT_AXES:
            findings.append(prefix + ".holdout_axis_invalid")
    elif lane == "HISTORICAL_TEACHING":
        if provenance != "RESULT_KNOWN_TEACHING" or outcome_access != "OUTCOME_EXPOSED":
            findings.append(prefix + ".teaching_requires_exposed_result_known_provenance")
        if episode.get("holdout_axis") is not None:
            findings.append(prefix + ".teaching_holdout_axis_forbidden")
    elif lane == "LIVE_SENTINEL":
        if provenance != "REAL_FORWARD" or outcome_access != "NOT_YET_RELEASED":
            findings.append(prefix + ".live_sentinel_requires_unreleased_forward_provenance")
        if episode.get("holdout_axis") is not None:
            findings.append(prefix + ".live_holdout_axis_forbidden")

    artifacts = episode.get("artifacts") or {}
    if not isinstance(artifacts, dict):
        findings.append(prefix + ".artifacts_not_object")
        artifacts = {}
    else:
        unexpected_artifacts = sorted(set(artifacts) - ARTIFACT_FIELDS)
        if unexpected_artifacts:
            findings.append(prefix + ".artifacts_unexpected_fields:" + ",".join(unexpected_artifacts))
    for field, value in artifacts.items():
        if not isinstance(value, str) or not value.strip():
            findings.append(prefix + ".artifacts." + field + "_invalid")
        elif validate_artifacts and not _artifact_path(value, contract_path=contract_path).is_file():
            findings.append(prefix + ".artifacts." + field + "_missing")
    return findings, episode


def validate_program(
    program: dict[str, Any], *, contract_path: str | Path | None = None,
    validate_artifacts: bool = True,
) -> dict[str, Any]:
    """Validate lane, leakage, sampling and holdout boundaries."""
    findings: list[str] = []
    if not isinstance(program, dict):
        return {"schema_version": "judgment-training-program-validation.v1", "state": "INVALID", "findings": ["program_not_object"]}
    allowed = {
        "schema_version", "program_state", "program_id", "method_version", "registered_at",
        "method_frozen_at", "sampling_policy", "episodes",
    }
    unexpected = sorted(set(program) - allowed)
    if unexpected:
        findings.append("unexpected_fields:" + ",".join(unexpected))
    if program.get("schema_version") != SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    program_state = str(program.get("program_state") or "").upper()
    if program_state not in PROGRAM_STATES:
        findings.append("program_state_invalid")
    program_id = _required_text(program.get("program_id"), "program_id", findings)
    if program_id and not re.fullmatch(r"JTP:[A-Za-z0-9._:-]+", program_id):
        findings.append("program_id_invalid")
    _required_text(program.get("method_version"), "method_version", findings)
    registered_at = _parse_time(program.get("registered_at"), "registered_at")
    if registered_at is None:
        findings.append("registered_at_invalid")
    frozen_raw = program.get("method_frozen_at")
    method_frozen_at = _parse_time(frozen_raw, "method_frozen_at") if frozen_raw else None
    if frozen_raw and method_frozen_at is None:
        findings.append("method_frozen_at_invalid")
    if registered_at is not None and method_frozen_at is not None and method_frozen_at < registered_at:
        findings.append("method_frozen_before_program_registration")

    contract = Path(contract_path).resolve() if contract_path else None
    sampling = program.get("sampling_policy")
    if not isinstance(sampling, dict):
        findings.append("sampling_policy_not_object")
    else:
        expected_sampling = {
            "universe_ref", "cohort_formed_as_of_cutoff", "outcome_used_for_selection",
            "terminal_status_coverage", "same_company_periods_count_as_independent",
        }
        unexpected_sampling = sorted(set(sampling) - expected_sampling)
        if unexpected_sampling:
            findings.append("sampling_policy_unexpected_fields:" + ",".join(unexpected_sampling))
        universe_ref = _required_text(sampling.get("universe_ref"), "sampling_policy.universe_ref", findings)
        if universe_ref and validate_artifacts and not _artifact_path(universe_ref, contract_path=contract).is_file():
            findings.append("sampling_policy.universe_ref_missing")
        if sampling.get("cohort_formed_as_of_cutoff") is not True:
            findings.append("sampling_policy.cohort_must_be_formed_as_of_cutoff")
        if sampling.get("outcome_used_for_selection") is not False:
            findings.append("sampling_policy.outcome_selection_forbidden")
        if sampling.get("terminal_status_coverage") != "ALL_CUTOFF_ELIGIBLE_STATES":
            findings.append("sampling_policy.survivor_only_sampling_forbidden")
        if sampling.get("same_company_periods_count_as_independent") is not False:
            findings.append("sampling_policy.same_company_periods_not_independent")

    episodes = program.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        findings.append("episodes_missing")
        episodes = []
    normalized: list[dict[str, Any]] = []
    for index, episode in enumerate(episodes):
        episode_findings, record = _validate_episode(
            episode, index=index, method_frozen_at=method_frozen_at,
            contract_path=contract, validate_artifacts=validate_artifacts,
        )
        findings.extend(episode_findings)
        if record is not None:
            normalized.append(record)
    for field in ("training_episode_id", "case_id"):
        values = [str(item.get(field) or "") for item in normalized]
        if len(values) != len(set(values)):
            findings.append("duplicate_" + field)
    if not any(item.get("lane") == "HISTORICAL_TRAINING" for item in normalized):
        findings.append("historical_training_lane_missing")
    if program_state == "ACTIVE" and not any(item.get("lane") == "HISTORICAL_HOLDOUT" for item in normalized):
        findings.append("active_program_requires_clean_holdout")

    training = [item for item in normalized if item.get("lane") == "HISTORICAL_TRAINING"]
    holdouts = [item for item in normalized if item.get("lane") == "HISTORICAL_HOLDOUT"]
    training_clusters = {str(item.get("company_cluster_id")) for item in training}
    training_cutoffs = [_parse_time(item.get("cutoff_at"), "cutoff_at") for item in training]
    latest_training_cutoff = max((item for item in training_cutoffs if item is not None), default=None)
    for item in holdouts:
        axis = item.get("holdout_axis")
        prefix = "episodes[" + str(episodes.index(item)) + "]"
        if axis in {"COMPANY", "COMPANY_AND_TIME"} and item.get("company_cluster_id") in training_clusters:
            findings.append(prefix + ".company_holdout_cluster_seen_in_training")
        cutoff = _parse_time(item.get("cutoff_at"), prefix + ".cutoff_at")
        if axis in {"TIME", "COMPANY_AND_TIME"} and latest_training_cutoff and cutoff and cutoff <= latest_training_cutoff:
            findings.append(prefix + ".time_holdout_not_after_training_cutoffs")

    return {
        "schema_version": "judgment-training-program-validation.v1",
        "state": "INVALID" if findings else "REVIEWABLE",
        "program_state": program_state,
        "findings": findings,
        "lane_counts": {lane: sum(1 for item in normalized if item.get("lane") == lane) for lane in sorted(LANES)},
    }


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS judgment_training_programs (
          program_id TEXT PRIMARY KEY,
          program_state TEXT NOT NULL DEFAULT 'ACTIVE',
          method_version TEXT NOT NULL,
          registered_at TEXT NOT NULL,
          method_frozen_at TEXT,
          sampling_policy_json TEXT NOT NULL,
          contract_ref TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS judgment_training_episodes (
          training_episode_id TEXT PRIMARY KEY,
          program_id TEXT NOT NULL,
          case_id TEXT NOT NULL UNIQUE,
          company_id TEXT NOT NULL,
          company_cluster_id TEXT NOT NULL,
          industry_id TEXT NOT NULL,
          decision_domain TEXT NOT NULL,
          cutoff_at TEXT NOT NULL,
          outcome_not_before TEXT NOT NULL,
          lane TEXT NOT NULL,
          provenance_role TEXT NOT NULL,
          outcome_access TEXT NOT NULL,
          holdout_axis TEXT,
          artifacts_json TEXT NOT NULL,
          FOREIGN KEY (program_id) REFERENCES judgment_training_programs(program_id)
        );
        CREATE INDEX IF NOT EXISTS idx_judgment_training_lane
          ON judgment_training_episodes(program_id, lane, cutoff_at);
        CREATE TABLE IF NOT EXISTS judgment_training_artifact_events (
          artifact_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
          training_episode_id TEXT NOT NULL,
          artifact_kind TEXT NOT NULL,
          artifact_ref TEXT NOT NULL,
          recorded_at TEXT NOT NULL,
          content_json TEXT,
          content_text TEXT,
          UNIQUE (training_episode_id, artifact_kind),
          FOREIGN KEY (training_episode_id) REFERENCES judgment_training_episodes(training_episode_id)
        );
        """
    )
    existing_program_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(judgment_training_programs)").fetchall()
    }
    if "program_state" not in existing_program_columns:
        conn.execute("ALTER TABLE judgment_training_programs ADD COLUMN program_state TEXT NOT NULL DEFAULT 'ACTIVE'")
    conn.commit()
    feedback_control.initialize(conn)


def _artifact_snapshot(kind: str, reference: str | Path, *, contract_path: Path | None = None) -> dict[str, Any]:
    if kind not in ARTIFACT_FIELDS:
        raise TrainingProgramError("unsupported artifact kind: " + kind)
    path = _artifact_path(str(reference), contract_path=contract_path)
    if not path.is_file():
        raise TrainingProgramError(f"artifact does not exist: {path}")
    if kind in JSON_ARTIFACT_FIELDS:
        payload = _read_json(path)
        return {
            "artifact_ref": str(path),
            "content_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            "content_text": None,
        }
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TrainingProgramError(f"cannot read artifact: {path}") from exc
    return {"artifact_ref": str(path), "content_json": None, "content_text": content}


def _event_snapshot(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_ref": row["artifact_ref"],
        "content_json": row["content_json"],
        "content_text": row["content_text"],
    }


def _artifact_events(conn: sqlite3.Connection, training_episode_id: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """SELECT artifact_kind, artifact_ref, content_json, content_text
             FROM judgment_training_artifact_events
            WHERE training_episode_id = ?""",
        (training_episode_id,),
    ).fetchall()
    return {row["artifact_kind"]: _event_snapshot(row) for row in rows}


def _insert_artifact_event(
    conn: sqlite3.Connection, *, training_episode_id: str, kind: str,
    snapshot: dict[str, Any], recorded_at: datetime,
) -> None:
    conn.execute(
        """INSERT INTO judgment_training_artifact_events
             (training_episode_id, artifact_kind, artifact_ref, recorded_at, content_json, content_text)
             VALUES (?, ?, ?, ?, ?, ?)""",
        (
            training_episode_id, kind, snapshot["artifact_ref"], _iso(recorded_at),
            snapshot["content_json"], snapshot["content_text"],
        ),
    )


def register_program(conn: sqlite3.Connection, contract_path: str | Path) -> dict[str, Any]:
    path = Path(contract_path).resolve()
    program = _read_json(path)
    validation = validate_program(program, contract_path=path)
    if validation["state"] != "REVIEWABLE":
        raise TrainingProgramError("invalid training program: " + "; ".join(validation["findings"]))
    program_row = {
        "program_id": program["program_id"],
        "program_state": program["program_state"],
        "method_version": program["method_version"],
        "registered_at": _iso(_parse_time(program["registered_at"], "registered_at")),
        "method_frozen_at": _iso(_parse_time(program["method_frozen_at"], "method_frozen_at")) if program.get("method_frozen_at") else None,
        "sampling_policy_json": json.dumps(program["sampling_policy"], ensure_ascii=False, sort_keys=True),
        "contract_ref": str(path),
    }
    episode_rows = []
    seed_events: dict[str, dict[str, dict[str, Any]]] = {}
    for episode in program["episodes"]:
        artifacts = {
            field: str(_artifact_path(value, contract_path=path))
            for field, value in (episode.get("artifacts") or {}).items()
        }
        seed_events[episode["training_episode_id"]] = {
            field: _artifact_snapshot(field, value, contract_path=path)
            for field, value in (episode.get("artifacts") or {}).items()
        }
        episode_rows.append({
            **{field: episode[field] for field in (
                "training_episode_id", "case_id", "company_id", "company_cluster_id",
                "industry_id", "decision_domain", "lane", "provenance_role", "outcome_access",
            )},
            "program_id": program["program_id"],
            "cutoff_at": _iso(_parse_time(episode["cutoff_at"], "cutoff_at")),
            "outcome_not_before": _iso(_parse_time(episode["outcome_not_before"], "outcome_not_before")),
            "holdout_axis": episode.get("holdout_axis"),
            "artifacts_json": json.dumps(artifacts, ensure_ascii=False, sort_keys=True),
        })
    with conn:
        existing = conn.execute("SELECT * FROM judgment_training_programs WHERE program_id = ?", (program_row["program_id"],)).fetchone()
        if existing:
            comparable = {key: existing[key] for key in program_row}
            comparable_without_freeze = {key: value for key, value in comparable.items() if key != "method_frozen_at"}
            intended_without_freeze = {key: value for key, value in program_row.items() if key != "method_frozen_at"}
            freeze_is_compatible = (
                comparable["method_frozen_at"] == program_row["method_frozen_at"]
                or (program_row["method_frozen_at"] is None and comparable["method_frozen_at"] is not None)
            )
            if comparable_without_freeze != intended_without_freeze or not freeze_is_compatible:
                raise TrainingProgramError("immutable training program differs: " + program_row["program_id"])
            existing_episodes = [dict(row) for row in conn.execute(
                "SELECT * FROM judgment_training_episodes WHERE program_id = ? ORDER BY training_episode_id",
                (program_row["program_id"],),
            ).fetchall()]
            intended_by_id = {row["training_episode_id"]: row for row in episode_rows}
            existing_by_id = {row["training_episode_id"]: row for row in existing_episodes}
            if any(existing_by_id.get(key) != value for key, value in intended_by_id.items()):
                raise TrainingProgramError("immutable training episode set differs: " + program_row["program_id"])
            if any(
                key not in intended_by_id and value["lane"] != "HISTORICAL_HOLDOUT"
                for key, value in existing_by_id.items()
            ):
                raise TrainingProgramError("only pre-exposure holdout reservations may extend a registered program")
            for episode_id, expected_events in seed_events.items():
                actual_events = _artifact_events(conn, episode_id)
                for kind, expected in expected_events.items():
                    if actual_events.get(kind) != expected:
                        raise TrainingProgramError(
                            f"immutable training artifact differs: {episode_id}:{kind}"
                        )
            return {"schema_version": SCHEMA_VERSION, "program_id": program_row["program_id"], "registered": False, "idempotent": True}
        columns = tuple(program_row)
        conn.execute(
            f"INSERT INTO judgment_training_programs ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            tuple(program_row[column] for column in columns),
        )
        for row in episode_rows:
            columns = tuple(row)
            conn.execute(
                f"INSERT INTO judgment_training_episodes ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                tuple(row[column] for column in columns),
            )
        registered_at = _parse_time(program["registered_at"], "registered_at")
        for episode_id, events in seed_events.items():
            for kind, snapshot in events.items():
                _insert_artifact_event(
                    conn, training_episode_id=episode_id, kind=kind,
                    snapshot=snapshot, recorded_at=registered_at,
                )
    return {"schema_version": SCHEMA_VERSION, "program_id": program_row["program_id"], "registered": True, "idempotent": False}


def _snapshot_payload(snapshot: dict[str, Any], *, kind: str) -> dict[str, Any]:
    content = snapshot.get("content_json")
    if not isinstance(content, str):
        raise TrainingProgramError(kind + " must be a JSON artifact")
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise TrainingProgramError(kind + " must contain a JSON object")
    return payload


def _validate_artifact_event(
    row: sqlite3.Row, *, kind: str, snapshot: dict[str, Any],
    existing: dict[str, dict[str, Any]], method_frozen_at: datetime | None,
    recorded_at: datetime,
) -> None:
    if kind == "freeze_ref":
        return

    payload = _snapshot_payload(snapshot, kind=kind)
    result = validate_case(payload, allow_test_fixtures=False)
    findings = result.get("invalid_findings", []) + result.get("incomplete_findings", [])
    if result.get("state") != "REVIEWABLE":
        raise TrainingProgramError("case_ref is not reviewable: " + "; ".join(findings))
    if payload.get("case_id") != row["case_id"]:
        raise TrainingProgramError("case_ref case_id does not match the registered episode")


def record_artifact(
    conn: sqlite3.Connection, *, training_episode_id: str, kind: str,
    artifact_path: str | Path, recorded_at: str,
) -> dict[str, Any]:
    """Append one validated progress artifact without changing the registered episode identity."""
    if kind not in ARTIFACT_FIELDS:
        raise TrainingProgramError("unsupported artifact kind: " + kind)
    at = _parse_time(recorded_at, "recorded_at")
    if at is None:
        raise TrainingProgramError("recorded_at must be a timezone-aware ISO-8601 timestamp")
    row = conn.execute(
        """SELECT episode.*, program.method_frozen_at
             FROM judgment_training_episodes AS episode
             JOIN judgment_training_programs AS program USING (program_id)
            WHERE episode.training_episode_id = ?""",
        (training_episode_id,),
    ).fetchone()
    if not row:
        raise TrainingProgramError("unknown training episode: " + training_episode_id)
    snapshot = _artifact_snapshot(kind, artifact_path)
    existing = _artifact_events(conn, training_episode_id)
    if kind in existing:
        if existing[kind] != snapshot:
            raise TrainingProgramError(f"artifact event is immutable once recorded: {training_episode_id}:{kind}")
        return {
            "schema_version": SCHEMA_VERSION,
            "training_episode_id": training_episode_id,
            "artifact_kind": kind,
            "recorded": False,
            "idempotent": True,
        }
    method_frozen_at = (
        _parse_time(row["method_frozen_at"], "method_frozen_at") if row["method_frozen_at"] else None
    )
    _validate_artifact_event(
        row, kind=kind, snapshot=snapshot, existing=existing,
        method_frozen_at=method_frozen_at, recorded_at=at,
    )
    with conn:
        _insert_artifact_event(
            conn, training_episode_id=training_episode_id, kind=kind,
            snapshot=snapshot, recorded_at=at,
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "training_episode_id": training_episode_id,
        "artifact_kind": kind,
        "recorded": True,
        "idempotent": False,
    }


def reserve_holdout(
    conn: sqlite3.Connection, *, program_id: str, episode: dict[str, Any],
    contract_path: str | Path, reserved_at: str,
) -> dict[str, Any]:
    """Append one holdout identity before any training outcome has entered the control plane."""
    at = _parse_time(reserved_at, "reserved_at")
    if at is None:
        raise TrainingProgramError("reserved_at must be a timezone-aware ISO-8601 timestamp")
    program = conn.execute(
        "SELECT * FROM judgment_training_programs WHERE program_id = ?", (program_id,),
    ).fetchone()
    if not program:
        raise TrainingProgramError("unknown training program: " + program_id)
    if program["method_frozen_at"]:
        raise TrainingProgramError("holdout must be reserved before method freeze")
    if episode.get("lane") != "HISTORICAL_HOLDOUT":
        raise TrainingProgramError("reserve-holdout accepts only a HISTORICAL_HOLDOUT episode")
    findings, normalized = _validate_episode(
        episode, index=0, method_frozen_at=None,
        contract_path=Path(contract_path).resolve(), validate_artifacts=True,
    )
    if findings or normalized is None:
        raise TrainingProgramError("invalid holdout reservation: " + "; ".join(findings))
    if not (episode.get("artifacts") or {}).get("freeze_ref"):
        raise TrainingProgramError("holdout reservation requires a frozen pre-outcome artifact")
    outcome_events = conn.execute(
        """SELECT COUNT(*) AS count
             FROM judgment_feedback_events AS event
             JOIN judgment_feedback_claims AS claim USING (feedback_item_id)
             JOIN judgment_training_episodes AS registered ON registered.case_id = claim.episode_id
            WHERE registered.program_id = ?
              AND registered.lane = 'HISTORICAL_TRAINING'
              AND event.event_type IN (
                'OUTCOME_PACKAGE_READY', 'READ_ATTESTED', 'OUTCOME_EXTRACTED',
                'CLAIM_SETTLED', 'MEASUREMENT_MISMATCH', 'OPERATING_OUTCOME_RECORDED',
                'DIAGNOSIS_ACCEPTED', 'LEARNING_NOTE_READY', 'LEARNING_APPLIED'
              )""",
        (program_id,),
    ).fetchone()["count"]
    if outcome_events:
        raise TrainingProgramError("holdout reservation must precede all training outcome exposure")
    training_clusters = {
        row["company_cluster_id"] for row in conn.execute(
            "SELECT company_cluster_id FROM judgment_training_episodes WHERE program_id = ? AND lane = 'HISTORICAL_TRAINING'",
            (program_id,),
        ).fetchall()
    }
    if episode["holdout_axis"] in {"COMPANY", "COMPANY_AND_TIME"} and episode["company_cluster_id"] in training_clusters:
        raise TrainingProgramError("company holdout cannot reuse a historical training company cluster")
    existing = conn.execute(
        "SELECT * FROM judgment_training_episodes WHERE training_episode_id = ? OR case_id = ?",
        (episode["training_episode_id"], episode["case_id"]),
    ).fetchone()
    if existing:
        if existing["program_id"] == program_id and existing["lane"] == "HISTORICAL_HOLDOUT":
            return {
                "schema_version": SCHEMA_VERSION, "program_id": program_id,
                "training_episode_id": episode["training_episode_id"], "reserved": False, "idempotent": True,
            }
        raise TrainingProgramError("holdout episode identity already exists")
    source_path = Path(contract_path).resolve()
    artifacts = {
        field: str(_artifact_path(value, contract_path=source_path))
        for field, value in (episode.get("artifacts") or {}).items()
    }
    row = {
        **{field: episode[field] for field in (
            "training_episode_id", "case_id", "company_id", "company_cluster_id",
            "industry_id", "decision_domain", "lane", "provenance_role", "outcome_access",
        )},
        "program_id": program_id,
        "cutoff_at": _iso(_parse_time(episode["cutoff_at"], "cutoff_at")),
        "outcome_not_before": _iso(_parse_time(episode["outcome_not_before"], "outcome_not_before")),
        "holdout_axis": episode["holdout_axis"],
        "artifacts_json": json.dumps(artifacts, ensure_ascii=False, sort_keys=True),
    }
    with conn:
        columns = tuple(row)
        conn.execute(
            f"INSERT INTO judgment_training_episodes ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            tuple(row[column] for column in columns),
        )
        for kind, value in (episode.get("artifacts") or {}).items():
            _insert_artifact_event(
                conn, training_episode_id=episode["training_episode_id"], kind=kind,
                snapshot=_artifact_snapshot(kind, value, contract_path=source_path), recorded_at=at,
            )
    return {
        "schema_version": SCHEMA_VERSION, "program_id": program_id,
        "training_episode_id": episode["training_episode_id"], "reserved": True, "idempotent": False,
    }


def _program_control_items(
    conn: sqlite3.Connection, *, contract_ref: str, as_of: datetime,
) -> dict[str, list[dict[str, Any]]]:
    projection = feedback_control.reconcile(conn, as_of=_iso(as_of))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in projection.get("items", []):
        if item.get("training_program_ref") != contract_ref:
            continue
        event_rows = conn.execute(
            "SELECT event_type FROM judgment_feedback_events WHERE feedback_item_id = ? ORDER BY event_id",
            (item["feedback_item_id"],),
        ).fetchall()
        item = {**item, "event_types": [row["event_type"] for row in event_rows]}
        grouped.setdefault(str(item.get("episode_id") or ""), []).append(item)
    return grouped


def _holdout_exposure_events(
    conn: sqlite3.Connection, *, program_id: str, contract_ref: str,
) -> list[sqlite3.Row]:
    event_types = sorted(
        feedback_control.OUTCOME_PIPELINE_EVENTS
        | feedback_control.OUTCOME_EVENTS
        | {"OUTCOME_EXPOSURE_BREACH"}
    )
    placeholders = ",".join("?" for _ in event_types)
    return conn.execute(
        f"""SELECT event.event_id, event.event_type, event.effective_at, event.recorded_at
               FROM judgment_feedback_events AS event
               JOIN judgment_feedback_claims AS claim USING (feedback_item_id)
               JOIN judgment_training_episodes AS episode ON episode.case_id = claim.episode_id
              WHERE episode.program_id = ?
                AND episode.lane = 'HISTORICAL_HOLDOUT'
                AND claim.program_lane = 'HISTORICAL_HOLDOUT'
                AND claim.training_program_ref = ?
                AND event.event_type IN ({placeholders})
              ORDER BY event.recorded_at, event.event_id""",
        (program_id, contract_ref, *event_types),
    ).fetchall()


def _accepted_application_times(
    conn: sqlite3.Connection, *, program_id: str, contract_ref: str,
) -> list[datetime]:
    rows = conn.execute(
        """SELECT event.effective_at, event.recorded_at
             FROM judgment_feedback_events AS event
             JOIN judgment_feedback_claims AS claim USING (feedback_item_id)
             JOIN judgment_training_episodes AS episode ON episode.case_id = claim.episode_id
            WHERE episode.program_id = ?
              AND episode.lane = 'HISTORICAL_TRAINING'
              AND claim.program_lane = 'HISTORICAL_TRAINING'
              AND claim.training_program_ref = ?
              AND claim.learning_eligibility = 'SELECTION_METHOD_ELIGIBLE'
              AND event.event_type = 'LEARNING_APPLIED'""",
        (program_id, contract_ref),
    ).fetchall()
    times: list[datetime] = []
    for row in rows:
        times.extend((
            _parse_time(row["effective_at"], "learning_application.effective_at"),
            _parse_time(row["recorded_at"], "learning_application.recorded_at"),
        ))
    return [value for value in times if value is not None]


def freeze_method(conn: sqlite3.Connection, *, program_id: str, method_version: str, frozen_at: str) -> dict[str, Any]:
    """Freeze the method once before any reserved holdout is revealed."""
    at = _parse_time(frozen_at, "frozen_at")
    if at is None:
        raise TrainingProgramError("frozen_at must be a timezone-aware ISO-8601 timestamp")
    program = conn.execute("SELECT * FROM judgment_training_programs WHERE program_id = ?", (program_id,)).fetchone()
    if not program:
        raise TrainingProgramError("unknown training program: " + program_id)
    if program["method_version"] != method_version:
        raise TrainingProgramError("method_version does not match the registered program")
    registered_at = _parse_time(program["registered_at"], "registered_at")
    if registered_at is not None and at < registered_at:
        raise TrainingProgramError("method freeze cannot predate program registration")
    if program["method_frozen_at"]:
        if program["method_frozen_at"] != _iso(at):
            raise TrainingProgramError("method freeze is immutable once recorded")
        return {"schema_version": SCHEMA_VERSION, "program_id": program_id, "method_frozen_at": program["method_frozen_at"], "idempotent": True}
    rows = [dict(row) for row in conn.execute(
        "SELECT * FROM judgment_training_episodes WHERE program_id = ? ORDER BY cutoff_at, training_episode_id",
        (program_id,),
    ).fetchall()]
    training_rows = [row for row in rows if row["lane"] == "HISTORICAL_TRAINING"]
    holdout_rows = [row for row in rows if row["lane"] == "HISTORICAL_HOLDOUT"]
    if not training_rows:
        raise TrainingProgramError("method freeze requires a historical training lane")
    if not holdout_rows:
        raise TrainingProgramError("method freeze requires a clean historical holdout reservation")
    exposures = _holdout_exposure_events(
        conn, program_id=program_id, contract_ref=program["contract_ref"],
    )
    if exposures:
        raise TrainingProgramError("holdout was exposed before method freeze")
    application_times = _accepted_application_times(
        conn, program_id=program_id, contract_ref=program["contract_ref"],
    )
    if not application_times:
        raise TrainingProgramError("method freeze requires an accepted cross-company learning application")
    if at < max(application_times):
        raise TrainingProgramError("method freeze cannot predate the accepted learning application")
    control_by_case = _program_control_items(conn, contract_ref=program["contract_ref"], as_of=at)
    training_states = [
        _episode_status(
            row, as_of=at, method_frozen_at=None,
            artifacts=_artifact_events(conn, row["training_episode_id"]),
            control_items=control_by_case.get(row["case_id"], []),
        )["state"]
        for row in training_rows
    ]
    if "TRANSFER_APPLIED" not in training_states:
        raise TrainingProgramError("method freeze requires a selection-eligible TRANSFER_APPLIED episode")
    permitted_training_terminal = {"TRANSFER_APPLIED", "MECHANISM_SETTLED"}
    if any(state not in permitted_training_terminal for state in training_states):
        raise TrainingProgramError("all historical training episodes must be terminal before method freeze")
    holdout_states = [
        _episode_status(
            row, as_of=at, method_frozen_at=None,
            artifacts=_artifact_events(conn, row["training_episode_id"]),
            control_items=control_by_case.get(row["case_id"], []),
        )["state"]
        for row in holdout_rows
    ]
    if any(state != "WAITING_FOR_METHOD_FREEZE" for state in holdout_states):
        raise TrainingProgramError("every historical holdout must be frozen and unexposed before method freeze")
    with conn:
        conn.execute(
            "UPDATE judgment_training_programs SET method_frozen_at = ? WHERE program_id = ?",
            (_iso(at), program_id),
        )
    return {"schema_version": SCHEMA_VERSION, "program_id": program_id, "method_frozen_at": _iso(at), "idempotent": False}


def feedback_control_identity(episode: dict[str, Any], *, selection_status: str, program_ref: str) -> dict[str, str]:
    """Project a program lane onto the existing feedback claim identity."""
    lane = str(episode.get("lane") or "").upper()
    outcome_access = str(episode.get("outcome_access") or "").upper()
    selection = str(selection_status or "").upper()
    if lane not in LANES or outcome_access not in OUTCOME_ACCESS_STATES:
        raise TrainingProgramError("episode must pass training-program validation before feedback projection")
    if selection not in {"SELECTION_ADMITTED", "NO_PRIMARY"}:
        raise TrainingProgramError("selection_status must be SELECTION_ADMITTED or NO_PRIMARY")
    if lane == "HISTORICAL_HOLDOUT":
        eligibility = "EVALUATION_ONLY"
    elif lane == "HISTORICAL_TEACHING":
        eligibility = "TEACHING_ONLY"
    elif selection == "SELECTION_ADMITTED":
        eligibility = "SELECTION_METHOD_ELIGIBLE"
    else:
        eligibility = "MECHANISM_SETTLEMENT_ONLY"
    return {
        "program_lane": lane,
        "outcome_access": outcome_access,
        "training_program_ref": str(Path(program_ref).resolve()),
        "learning_eligibility": eligibility,
    }


def _episode_status(
    row: dict[str, Any], *, as_of: datetime, method_frozen_at: datetime | None,
    artifacts: dict[str, dict[str, Any]], control_items: list[dict[str, Any]],
) -> dict[str, Any]:
    lane = row["lane"]
    findings: list[str] = []
    case_snapshot = artifacts.get("case_ref")
    case = _snapshot_payload(case_snapshot, kind="case_ref") if case_snapshot else None
    if case is not None:
        result = validate_case(case, allow_test_fixtures=False)
        if result.get("state") != "REVIEWABLE":
            findings.extend("case:" + item for item in result.get("invalid_findings", []) + result.get("incomplete_findings", []))
        if case.get("case_id") != row["case_id"]:
            findings.append("case_id_mismatch")
    if any(item.get("program_lane") != lane for item in control_items):
        findings.append("control_program_lane_mismatch")
    frozen = case is not None or "freeze_ref" in artifacts
    if control_items and not frozen:
        findings.append("control_registered_before_episode_freeze")
    if any(item.get("selection_status") == "SELECTION_ADMITTED" for item in control_items) and case is None:
        findings.append("selection_training_requires_structured_case_ref")
    if findings:
        return {"state": "NEEDS_REPAIR", "actionable": True, "findings": sorted(set(findings))}

    if not frozen:
        if lane == "HISTORICAL_TEACHING":
            return {"state": "READY_FOR_BOUNDARY_REVIEW", "actionable": True, "findings": []}
        if lane == "HISTORICAL_HOLDOUT" and method_frozen_at is None:
            return {"state": "HOLDOUT_RESERVATION_INCOMPLETE", "actionable": True, "findings": []}
        return {"state": "READY_TO_FREEZE", "actionable": True, "findings": []}

    event_types = {event for item in control_items for event in item.get("event_types", [])}
    settled_items = [
        item for item in control_items
        if item.get("settlement_state") not in {None, "UNSETTLED"}
    ]
    selection_items = [
        item for item in control_items
        if item.get("learning_eligibility") == "SELECTION_METHOD_ELIGIBLE"
    ]
    mechanism_items = [
        item for item in control_items
        if item.get("learning_eligibility") == "MECHANISM_SETTLEMENT_ONLY"
    ]

    if lane == "HISTORICAL_HOLDOUT" and method_frozen_at is None:
        if event_types & (feedback_control.OUTCOME_PIPELINE_EVENTS | feedback_control.OUTCOME_EVENTS | {"OUTCOME_EXPOSURE_BREACH"}):
            return {"state": "NEEDS_REPAIR", "actionable": True, "findings": ["holdout_revealed_before_method_freeze"]}
        return {"state": "WAITING_FOR_METHOD_FREEZE", "actionable": False, "findings": []}
    if lane == "HISTORICAL_HOLDOUT":
        if not control_items:
            return {"state": "READY_FOR_CONTROL_REGISTRATION", "actionable": True, "findings": []}
        if any(item.get("learning_eligibility") != "EVALUATION_ONLY" for item in control_items):
            return {"state": "NEEDS_REPAIR", "actionable": True, "findings": ["holdout_control_not_evaluation_only"]}
        if len(settled_items) == len(control_items):
            return {"state": "EVALUATED_HOLDOUT", "actionable": False, "findings": []}
        return {"state": "HOLDOUT_EVALUATION_ACTIVE", "actionable": True, "findings": []}
    if lane == "HISTORICAL_TEACHING":
        return {"state": "BOUNDARY_REVIEW_COMPLETE", "actionable": False, "findings": []}
    if lane == "LIVE_SENTINEL":
        if settled_items:
            return {"state": "LIVE_CALIBRATED", "actionable": False, "findings": []}
        due = as_of >= _parse_time(row["outcome_not_before"], "outcome_not_before")
        if not due:
            return {"state": "WAITING_EXTERNAL", "actionable": False, "findings": []}
        return {"state": "DUE_FOR_RESULT_ACQUISITION", "actionable": True, "findings": []}

    if not control_items:
        return {"state": "READY_FOR_CONTROL_REGISTRATION", "actionable": True, "findings": []}
    if "LEARNING_APPLIED" in event_types:
        return {"state": "TRANSFER_APPLIED", "actionable": False, "findings": []}
    if selection_items:
        learning_states = {item.get("learning_state") for item in selection_items}
        if "APPLICATION_PENDING" in learning_states:
            return {"state": "READY_FOR_TRANSFER", "actionable": True, "findings": []}
        if "NOTE_READY" in learning_states:
            return {"state": "READY_FOR_LEARNING_NOTE", "actionable": True, "findings": []}
        if "DIAGNOSIS_PENDING" in learning_states:
            return {"state": "READY_FOR_DIAGNOSIS", "actionable": True, "findings": []}
        return {"state": "HISTORICAL_SETTLEMENT_ACTIVE", "actionable": True, "findings": []}
    if mechanism_items and len(settled_items) == len(control_items):
        return {"state": "MECHANISM_SETTLED", "actionable": False, "findings": []}
    return {"state": "HISTORICAL_SETTLEMENT_ACTIVE", "actionable": True, "findings": []}


def reconcile(conn: sqlite3.Connection, *, program_id: str, as_of: str) -> dict[str, Any]:
    as_of_dt = _parse_time(as_of, "as_of")
    if as_of_dt is None:
        raise TrainingProgramError("as_of must be a timezone-aware ISO-8601 timestamp")
    program = conn.execute("SELECT * FROM judgment_training_programs WHERE program_id = ?", (program_id,)).fetchone()
    if not program:
        raise TrainingProgramError("unknown training program: " + program_id)
    rows = [dict(row) for row in conn.execute(
        "SELECT * FROM judgment_training_episodes WHERE program_id = ? ORDER BY cutoff_at, training_episode_id",
        (program_id,),
    ).fetchall()]
    method_frozen_at = _parse_time(program["method_frozen_at"], "method_frozen_at") if program["method_frozen_at"] else None
    control_by_case = _program_control_items(
        conn, contract_ref=program["contract_ref"], as_of=as_of_dt,
    )
    items = []
    for row in rows:
        status = _episode_status(
            row, as_of=as_of_dt, method_frozen_at=method_frozen_at,
            artifacts=_artifact_events(conn, row["training_episode_id"]),
            control_items=control_by_case.get(row["case_id"], []),
        )
        items.append({
            "training_episode_id": row["training_episode_id"],
            "case_id": row["case_id"],
            "company_id": row["company_id"],
            "company_cluster_id": row["company_cluster_id"],
            "industry_id": row["industry_id"],
            "decision_domain": row["decision_domain"],
            "lane": row["lane"],
            "provenance_role": row["provenance_role"],
            "outcome_access": row["outcome_access"],
            "cutoff_at": row["cutoff_at"],
            "outcome_not_before": row["outcome_not_before"],
            **status,
        })
    lane_summary = {}
    for lane in sorted(LANES):
        lane_items = [item for item in items if item["lane"] == lane]
        lane_summary[lane] = {
            "count": len(lane_items),
            "states": {state: sum(1 for item in lane_items if item["state"] == state) for state in sorted({item["state"] for item in lane_items})},
            "actionable": sum(1 for item in lane_items if item["actionable"]),
        }
    historical_items = [item for item in items if item["lane"] != "LIVE_SENTINEL"]
    training_items = [item for item in items if item["lane"] == "HISTORICAL_TRAINING"]
    holdout_items = [item for item in items if item["lane"] == "HISTORICAL_HOLDOUT"]
    live_items = [item for item in items if item["lane"] == "LIVE_SENTINEL"]
    needs_repair = any(item["state"] == "NEEDS_REPAIR" for item in historical_items)
    transfer_applied = any(item["state"] == "TRANSFER_APPLIED" for item in training_items)
    training_terminal = bool(training_items) and all(
        item["state"] in {"TRANSFER_APPLIED", "MECHANISM_SETTLED"} for item in training_items
    )
    holdout_complete = bool(holdout_items) and all(
        item["state"] == "EVALUATED_HOLDOUT" for item in holdout_items
    )
    if needs_repair:
        historical_method_state = "NEEDS_REPAIR"
    elif method_frozen_at is not None and holdout_complete:
        historical_method_state = "HISTORICAL_EVALUATION_COMPLETE"
    elif method_frozen_at is not None:
        historical_method_state = "HOLDOUT_EVALUATION_ACTIVE"
    elif transfer_applied and not holdout_items:
        historical_method_state = "HOLDOUT_RESERVATION_REQUIRED"
    elif transfer_applied and all(item["state"] == "WAITING_FOR_METHOD_FREEZE" for item in holdout_items):
        historical_method_state = "READY_TO_FREEZE_METHOD"
    elif training_terminal and not transfer_applied:
        historical_method_state = "SELECTION_TRAINING_REQUIRED"
    else:
        historical_method_state = "TRAINING_ACTIVE"

    if not live_items:
        deployment_calibration_state = "NOT_CONFIGURED"
    elif all(item["state"] == "LIVE_CALIBRATED" for item in live_items):
        deployment_calibration_state = "CALIBRATION_OBSERVED"
    elif any(item["actionable"] for item in live_items):
        deployment_calibration_state = "ACTIVE"
    else:
        deployment_calibration_state = "WAITING_EXTERNAL"

    if historical_method_state == "NEEDS_REPAIR":
        system_state = "NEEDS_REPAIR"
    elif historical_method_state == "HISTORICAL_EVALUATION_COMPLETE":
        system_state = "HISTORICAL_EVALUATION_COMPLETE"
    else:
        system_state = "ACTIVE"
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "program_id": program_id,
        "method_version": program["method_version"],
        "method_frozen_at": program["method_frozen_at"],
        "as_of": _iso(as_of_dt),
        "system_state": system_state,
        "historical_method_state": historical_method_state,
        "deployment_calibration_state": deployment_calibration_state,
        "lane_summary": lane_summary,
        "items": items,
        "claim_boundary": (
            "Historical training may change the method; holdout is evaluation-only; "
            "live sentinels provide deployment calibration. No lane alone proves investment advantage."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate a training program contract")
    validate.add_argument("contract", type=Path)
    register = sub.add_parser("register", help="register an immutable training program")
    register.add_argument("contract", type=Path)
    register.add_argument("--db", type=Path, default=Path("stock_analysis.db"))
    attach = sub.add_parser("attach-artifact", help="append a freeze or structured case artifact")
    attach.add_argument("training_episode_id")
    attach.add_argument("kind", choices=sorted(ARTIFACT_FIELDS))
    attach.add_argument("artifact", type=Path)
    attach.add_argument("--recorded-at", required=True)
    attach.add_argument("--db", type=Path, default=Path("stock_analysis.db"))
    reserve = sub.add_parser("reserve-holdout", help="append a clean holdout before training outcome exposure")
    reserve.add_argument("program_id")
    reserve.add_argument("episode", type=Path)
    reserve.add_argument("--reserved-at", required=True)
    reserve.add_argument("--db", type=Path, default=Path("stock_analysis.db"))
    freeze = sub.add_parser("freeze-method", help="freeze the method before revealing holdouts")
    freeze.add_argument("program_id")
    freeze.add_argument("--method-version", required=True)
    freeze.add_argument("--frozen-at", required=True)
    freeze.add_argument("--db", type=Path, default=Path("stock_analysis.db"))
    status = sub.add_parser("status", help="project independent lane states")
    status.add_argument("program_id")
    status.add_argument("--db", type=Path, default=Path("stock_analysis.db"))
    status.add_argument("--as-of", required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            payload = _read_json(args.contract.resolve())
            result = validate_program(payload, contract_path=args.contract.resolve())
        else:
            conn = connect(args.db)
            initialize(conn)
            if args.command == "register":
                result = register_program(conn, args.contract)
            elif args.command == "attach-artifact":
                result = record_artifact(
                    conn, training_episode_id=args.training_episode_id, kind=args.kind,
                    artifact_path=args.artifact, recorded_at=args.recorded_at,
                )
            elif args.command == "reserve-holdout":
                result = reserve_holdout(
                    conn, program_id=args.program_id, episode=_read_json(args.episode.resolve()),
                    contract_path=args.episode, reserved_at=args.reserved_at,
                )
            elif args.command == "freeze-method":
                result = freeze_method(
                    conn, program_id=args.program_id, method_version=args.method_version, frozen_at=args.frozen_at,
                )
            else:
                result = reconcile(conn, program_id=args.program_id, as_of=args.as_of)
    except TrainingProgramError as exc:
        print(json.dumps({"schema_version": STATUS_SCHEMA_VERSION, "state": "INVALID", "findings": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("state", "REVIEWABLE") != "INVALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
