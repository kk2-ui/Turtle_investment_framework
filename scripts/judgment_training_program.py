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
    from scripts.judgment_boundary_case import validate_boundary_case
    from scripts.judgment_selection_candidate import (
        CANDIDATE_SCHEMA_VERSION,
        CASH_TRANSMISSION_ADMISSION_VERSION,
        PEER_PANEL_ADMISSION_VERSION,
        validate_selection_candidate,
        validate_selection_review,
    )
except ModuleNotFoundError:
    from historical_backtest import validate_case
    import judgment_feedback_control as feedback_control
    from judgment_boundary_case import validate_boundary_case
    from judgment_selection_candidate import (
        CANDIDATE_SCHEMA_VERSION,
        CASH_TRANSMISSION_ADMISSION_VERSION,
        PEER_PANEL_ADMISSION_VERSION,
        validate_selection_candidate,
        validate_selection_review,
    )


SCHEMA_VERSION = "judgment-training-program.v1"
STATUS_SCHEMA_VERSION = "judgment-training-program-status.v1"
METHOD_REPORT_RELEASE_SCHEMA_VERSION = "judgment-method-report-release.v1"
PROGRAM_STATES = {"DRAFT", "ACTIVE"}
METHOD_SCOPES = {"BOUNDARY_ONLY", "SELECTION_AND_BOUNDARY"}
SELECTION_ADMISSION_VERSIONS = {
    CASH_TRANSMISSION_ADMISSION_VERSION,
    PEER_PANEL_ADMISSION_VERSION,
}
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
HOLDOUT_LINK_ROLE = "HISTORICAL_HOLDOUT"
ARTIFACT_FIELDS = {
    "freeze_ref",
    "case_ref",
    "selection_review_ref",
}
ARTIFACT_ORDER = (
    "freeze_ref",
    "case_ref",
    "selection_review_ref",
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


def _outcome_windows_overlap(
    left_opens: datetime | None, left_closes: datetime | None,
    right_opens: datetime | None, right_closes: datetime | None,
) -> bool:
    """Return whether two frozen outcome-resolution spans intersect.

    Resolution windows are half-open: a later window may open at the instant an
    earlier one closes without sharing an observable outcome period.
    """
    if None in {left_opens, left_closes, right_opens, right_closes}:
        return False
    return left_opens < right_closes and right_opens < left_closes


def _now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


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
        "industry_id", "decision_domain", "cutoff_at", "outcome_not_before", "outcome_window_ends_at",
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
    outcome_window_ends_at = None
    if cutoff is None:
        findings.append(prefix + ".cutoff_at_invalid")
    if outcome_not_before is None:
        findings.append(prefix + ".outcome_not_before_invalid")
    if episode.get("outcome_window_ends_at") is not None:
        outcome_window_ends_at = _parse_time(
            episode.get("outcome_window_ends_at"), prefix + ".outcome_window_ends_at",
        )
        if outcome_window_ends_at is None:
            findings.append(prefix + ".outcome_window_ends_at_invalid")
        elif outcome_not_before is not None and outcome_window_ends_at <= outcome_not_before:
            findings.append(prefix + ".outcome_window_must_end_after_open")
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
    if "selection_review_ref" in artifacts and "case_ref" not in artifacts:
        findings.append(prefix + ".selection_review_requires_case_ref")
    if "selection_review_ref" in artifacts and lane != "HISTORICAL_TRAINING":
        findings.append(prefix + ".selection_review_requires_historical_training")
    return findings, episode


def _validate_holdout_link(
    link: Any, *, index: int, contract_path: Path | None,
    validate_artifacts: bool,
) -> tuple[list[str], dict[str, Any] | None]:
    findings: list[str] = []
    prefix = f"holdout_links[{index}]"
    if not isinstance(link, dict):
        return [prefix + "_not_object"], None
    allowed = {
        "source_program_id", "source_training_episode_id", "source_case_id",
        "source_freeze_ref", "link_role",
    }
    unexpected = sorted(set(link) - allowed)
    if unexpected:
        findings.append(prefix + ".unexpected_fields:" + ",".join(unexpected))
    for field in (
        "source_program_id", "source_training_episode_id", "source_case_id",
        "source_freeze_ref", "link_role",
    ):
        _required_text(link.get(field), prefix + "." + field, findings)
    if link.get("source_program_id") and not re.fullmatch(
        r"JTP:[A-Za-z0-9._:-]+", str(link["source_program_id"]),
    ):
        findings.append(prefix + ".source_program_id_invalid")
    if link.get("source_training_episode_id") and not re.fullmatch(
        r"JTE:[A-Za-z0-9._:-]+", str(link["source_training_episode_id"]),
    ):
        findings.append(prefix + ".source_training_episode_id_invalid")
    if link.get("link_role") != HOLDOUT_LINK_ROLE:
        findings.append(prefix + ".link_role_invalid")
    freeze_ref = str(link.get("source_freeze_ref") or "").strip()
    if (
        freeze_ref
        and validate_artifacts
        and not _artifact_path(freeze_ref, contract_path=contract_path).is_file()
    ):
        findings.append(prefix + ".source_freeze_ref_missing")
    return findings, link


def validate_program(
    program: dict[str, Any], *, contract_path: str | Path | None = None,
    validate_artifacts: bool = True,
) -> dict[str, Any]:
    """Validate lane, leakage, sampling and holdout boundaries."""
    findings: list[str] = []
    if not isinstance(program, dict):
        return {"schema_version": "judgment-training-program-validation.v1", "state": "INVALID", "findings": ["program_not_object"]}
    allowed = {
        "schema_version", "program_state", "program_id", "method_version", "method_scope", "required_selection_admission_version", "registered_at",
        "method_frozen_at", "sampling_policy", "episodes", "holdout_links",
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
    method_scope = str(program.get("method_scope") or "SELECTION_AND_BOUNDARY").upper()
    if method_scope not in METHOD_SCOPES:
        findings.append("method_scope_invalid")
    required_selection_admission_version = program.get("required_selection_admission_version")
    if required_selection_admission_version is not None \
            and required_selection_admission_version not in SELECTION_ADMISSION_VERSIONS:
        findings.append("required_selection_admission_version_invalid")
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
    holdout_links_raw = program.get("holdout_links")
    holdout_links = holdout_links_raw or []
    if holdout_links_raw is not None and not isinstance(holdout_links_raw, list):
        findings.append("holdout_links_not_array")
        holdout_links = []
    elif holdout_links_raw == []:
        findings.append("holdout_links_empty")
    normalized_links: list[dict[str, Any]] = []
    for index, link in enumerate(holdout_links):
        link_findings, record = _validate_holdout_link(
            link, index=index, contract_path=contract,
            validate_artifacts=validate_artifacts,
        )
        findings.extend(link_findings)
        if record is not None:
            normalized_links.append(record)
    linked_episode_ids = [str(item.get("source_training_episode_id") or "") for item in normalized_links]
    if len(linked_episode_ids) != len(set(linked_episode_ids)):
        findings.append("duplicate_linked_holdout_episode")
    for field in ("training_episode_id", "case_id"):
        values = [str(item.get(field) or "") for item in normalized]
        if len(values) != len(set(values)):
            findings.append("duplicate_" + field)
    if program_state == "ACTIVE" and not any(item.get("lane") == "HISTORICAL_TRAINING" for item in normalized):
        findings.append("historical_training_lane_missing")
    if (
        program_state == "ACTIVE"
        and not any(item.get("lane") == "HISTORICAL_HOLDOUT" for item in normalized)
        and not normalized_links
    ):
        findings.append("active_program_requires_clean_holdout")

    training = [item for item in normalized if item.get("lane") == "HISTORICAL_TRAINING"]
    holdouts = [item for item in normalized if item.get("lane") == "HISTORICAL_HOLDOUT"]
    training_clusters = {str(item.get("company_cluster_id")) for item in training}
    for item in holdouts:
        axis = item.get("holdout_axis")
        prefix = "episodes[" + str(episodes.index(item)) + "]"
        if axis in {"COMPANY", "COMPANY_AND_TIME"} and item.get("company_cluster_id") in training_clusters:
            findings.append(prefix + ".company_holdout_cluster_seen_in_training")
        if axis in {"TIME", "COMPANY_AND_TIME"} and item.get("outcome_window_ends_at") is not None:
            holdout_opens = _parse_time(item.get("outcome_not_before"), prefix + ".outcome_not_before")
            holdout_closes = _parse_time(item.get("outcome_window_ends_at"), prefix + ".outcome_window_ends_at")
            missing_training_span = any(
                training_item.get("outcome_window_ends_at") is None for training_item in training
            )
            if missing_training_span or holdout_opens is None or holdout_closes is None:
                findings.append(prefix + ".time_holdout_requires_frozen_outcome_windows")
            elif any(
                _outcome_windows_overlap(
                    _parse_time(training_item.get("outcome_not_before"), "training.outcome_not_before"),
                    _parse_time(training_item.get("outcome_window_ends_at"), "training.outcome_window_ends_at"),
                    holdout_opens,
                    holdout_closes,
                )
                for training_item in training
            ):
                findings.append(prefix + ".time_holdout_outcome_window_overlaps_training")

    return {
        "schema_version": "judgment-training-program-validation.v1",
        "state": "INVALID" if findings else "REVIEWABLE",
        "program_state": program_state,
        "findings": findings,
        "lane_counts": {
            lane: sum(1 for item in normalized if item.get("lane") == lane)
            + (len(normalized_links) if lane == "HISTORICAL_HOLDOUT" else 0)
            for lane in sorted(LANES)
        },
        "linked_holdout_count": len(normalized_links),
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
          method_scope TEXT NOT NULL DEFAULT 'SELECTION_AND_BOUNDARY',
          required_selection_admission_version TEXT,
          registered_at TEXT NOT NULL,
          method_frozen_at TEXT,
          method_freeze_recorded_at TEXT,
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
          outcome_window_ends_at TEXT,
          lane TEXT NOT NULL,
          provenance_role TEXT NOT NULL,
          outcome_access TEXT NOT NULL,
          holdout_axis TEXT,
          artifacts_json TEXT NOT NULL,
          FOREIGN KEY (program_id) REFERENCES judgment_training_programs(program_id)
        );
        CREATE INDEX IF NOT EXISTS idx_judgment_training_lane
          ON judgment_training_episodes(program_id, lane, cutoff_at);
        CREATE TABLE IF NOT EXISTS judgment_training_holdout_links (
          program_id TEXT NOT NULL,
          source_program_id TEXT NOT NULL,
          source_training_episode_id TEXT NOT NULL,
          source_case_id TEXT NOT NULL,
          source_freeze_ref TEXT NOT NULL,
          link_role TEXT NOT NULL,
          PRIMARY KEY (program_id, source_training_episode_id),
          FOREIGN KEY (program_id) REFERENCES judgment_training_programs(program_id),
          FOREIGN KEY (source_program_id) REFERENCES judgment_training_programs(program_id),
          FOREIGN KEY (source_training_episode_id) REFERENCES judgment_training_episodes(training_episode_id)
        );
        CREATE INDEX IF NOT EXISTS idx_judgment_training_holdout_link_source
          ON judgment_training_holdout_links(source_program_id, source_training_episode_id);
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
        CREATE TABLE IF NOT EXISTS judgment_training_method_releases (
          program_id TEXT PRIMARY KEY,
          release_id TEXT NOT NULL UNIQUE,
          method_version TEXT NOT NULL,
          method_scope TEXT NOT NULL,
          method_frozen_at TEXT NOT NULL,
          released_at TEXT NOT NULL,
          recorded_at TEXT NOT NULL,
          released_by TEXT NOT NULL,
          release_decision TEXT NOT NULL,
          receipt_ref TEXT NOT NULL,
          receipt_json TEXT NOT NULL,
          FOREIGN KEY (program_id) REFERENCES judgment_training_programs(program_id)
        );
        """
    )
    existing_program_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(judgment_training_programs)").fetchall()
    }
    if "program_state" not in existing_program_columns:
        conn.execute("ALTER TABLE judgment_training_programs ADD COLUMN program_state TEXT NOT NULL DEFAULT 'ACTIVE'")
    if "method_scope" not in existing_program_columns:
        conn.execute("ALTER TABLE judgment_training_programs ADD COLUMN method_scope TEXT NOT NULL DEFAULT 'SELECTION_AND_BOUNDARY'")
    if "required_selection_admission_version" not in existing_program_columns:
        conn.execute("ALTER TABLE judgment_training_programs ADD COLUMN required_selection_admission_version TEXT")
    if "method_freeze_recorded_at" not in existing_program_columns:
        conn.execute("ALTER TABLE judgment_training_programs ADD COLUMN method_freeze_recorded_at TEXT")
    existing_episode_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(judgment_training_episodes)").fetchall()
    }
    if "outcome_window_ends_at" not in existing_episode_columns:
        conn.execute("ALTER TABLE judgment_training_episodes ADD COLUMN outcome_window_ends_at TEXT")
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


def _artifact_event_records(
    conn: sqlite3.Connection, training_episode_id: str,
) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """SELECT artifact_kind, artifact_ref, recorded_at, content_json, content_text
             FROM judgment_training_artifact_events
            WHERE training_episode_id = ?""",
        (training_episode_id,),
    ).fetchall()
    return {
        row["artifact_kind"]: {
            **_event_snapshot(row),
            "recorded_at": row["recorded_at"],
        }
        for row in rows
    }


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


def _validation_findings(result: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(
        result.get("invalid_findings", [])
        + result.get("incomplete_findings", [])
        + result.get("findings", [])
    ))


def _validate_case_identity(row: sqlite3.Row | dict[str, Any], case: dict[str, Any]) -> None:
    if case.get("case_id") != row["case_id"]:
        raise TrainingProgramError("case_ref case_id does not match the registered episode")
    if case.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        return
    for field in ("company_id", "company_cluster_id", "industry_id"):
        if case.get(field) != row[field]:
            raise TrainingProgramError(f"selection candidate {field} does not match the registered episode")
    case_cutoff = _parse_time(case.get("cutoff_at"), "selection_candidate.cutoff_at")
    episode_cutoff = _parse_time(row["cutoff_at"], "episode.cutoff_at")
    if case_cutoff is None or episode_cutoff is None or case_cutoff != episode_cutoff:
        raise TrainingProgramError("selection candidate cutoff_at does not match the registered episode")


def _validate_case_payload(row: sqlite3.Row | dict[str, Any], case: dict[str, Any]) -> None:
    if case.get("schema_version") == CANDIDATE_SCHEMA_VERSION:
        result = validate_selection_candidate(case)
    elif case.get("schema_version") == "judgment-boundary-case.v1":
        result = validate_boundary_case(case)
    else:
        result = validate_case(case, allow_test_fixtures=False)
    findings = _validation_findings(result)
    if result.get("state") != "REVIEWABLE":
        raise TrainingProgramError("case_ref is not reviewable: " + "; ".join(findings))
    _validate_case_identity(row, case)
    _validate_program_selection_admission_version(row, case)


def _row_value(row: sqlite3.Row | dict[str, Any], field: str) -> Any:
    if isinstance(row, dict):
        return row.get(field)
    return row[field] if field in row.keys() else None


def _validate_program_selection_admission_version(
    row: sqlite3.Row | dict[str, Any], case: dict[str, Any],
    *, required_version: str | None = None,
) -> None:
    """Bind every newly registered selection case to its program admission version.

    Registered legacy programs have a null requirement and remain auditable,
    but may not receive a new selection candidate.  A new selection program
    must declare V3 or V4 immutably; V3 is preserved only for the existing
    historical packet while the next program can demand V4.
    """
    if case.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        return
    required = required_version if required_version is not None else _row_value(
        row, "required_selection_admission_version",
    )
    admission = case.get("selection_admission_contract")
    version = admission.get("version") if isinstance(admission, dict) else None
    if required is None and version is None:
        # Sealed pre-admission R-102/R-104 receipts remain readable but the
        # null program requirement cannot authorize a new contracted case.
        return
    if required not in SELECTION_ADMISSION_VERSIONS:
        raise TrainingProgramError("selection candidate requires an explicit immutable program admission version")
    if version != required:
        raise TrainingProgramError(
            "selection candidate admission version does not match program requirement: "
            + str(required)
        )


def _validate_selection_review_payload(
    row: sqlite3.Row | dict[str, Any], *, review: dict[str, Any],
    case_snapshot: dict[str, Any], receipt_recorded_at: datetime,
) -> None:
    case = _snapshot_payload(case_snapshot, kind="case_ref")
    if case.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        raise TrainingProgramError("selection_review_ref requires a judgment-selection-candidate.v1 case_ref")
    _validate_case_payload(row, case)
    result = validate_selection_review(
        review,
        candidate=case,
        case_artifact_ref=case_snapshot.get("artifact_ref"),
        receipt_recorded_at=_iso(receipt_recorded_at),
    )
    if result.get("state") != "REVIEWABLE":
        raise TrainingProgramError(
            "selection_review_ref is not reviewable: " + "; ".join(_validation_findings(result))
        )


def _validate_seed_artifacts(
    episode: dict[str, Any], *, snapshots: dict[str, dict[str, Any]],
    recorded_at: datetime, required_selection_admission_version: str | None,
    review_recorded_at: datetime | None = None, skip_selection_review: bool = False,
) -> None:
    case_snapshot = snapshots.get("case_ref")
    if case_snapshot is None:
        if "selection_review_ref" in snapshots:
            raise TrainingProgramError("selection_review_ref requires case_ref")
        return
    case = _snapshot_payload(case_snapshot, kind="case_ref")
    if case.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        if "selection_review_ref" in snapshots:
            raise TrainingProgramError("selection_review_ref requires a judgment-selection-candidate.v1 case_ref")
        return
    _validate_case_payload(episode, case)
    _validate_program_selection_admission_version(
        episode, case, required_version=required_selection_admission_version,
    )
    review_snapshot = snapshots.get("selection_review_ref")
    if review_snapshot is not None and not skip_selection_review:
        _validate_selection_review_payload(
            episode,
            review=_snapshot_payload(review_snapshot, kind="selection_review_ref"),
            case_snapshot=case_snapshot,
            receipt_recorded_at=review_recorded_at or recorded_at,
        )


def _resolve_holdout_link_rows(
    conn: sqlite3.Connection, *, program: dict[str, Any], contract_path: Path,
    episode_rows: list[dict[str, Any]], registered_at: datetime,
    require_unexposed: bool,
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    training_rows = [row for row in episode_rows if row["lane"] == "HISTORICAL_TRAINING"]
    training_clusters = {row["company_cluster_id"] for row in training_rows}
    outcome_event_types = sorted(
        feedback_control.OUTCOME_PIPELINE_EVENTS
        | feedback_control.OUTCOME_EVENTS
        | {"OUTCOME_EXPOSURE_BREACH"}
    )
    placeholders = ",".join("?" for _ in outcome_event_types)
    for link in program.get("holdout_links") or []:
        if link["source_program_id"] == program["program_id"]:
            raise TrainingProgramError("linked holdout must belong to a predecessor program")
        source = conn.execute(
            """SELECT episode.*, source_program.program_state AS source_program_state,
                      source_program.contract_ref AS source_contract_ref,
                      source_program.registered_at AS source_program_registered_at
                 FROM judgment_training_episodes AS episode
                 JOIN judgment_training_programs AS source_program
                   ON source_program.program_id = episode.program_id
                WHERE episode.training_episode_id = ?""",
            (link["source_training_episode_id"],),
        ).fetchone()
        if source is None:
            raise TrainingProgramError(
                "linked holdout source episode is not registered: "
                + link["source_training_episode_id"]
            )
        source = dict(source)
        expected_identity = {
            "program_id": link["source_program_id"],
            "case_id": link["source_case_id"],
            "lane": HOLDOUT_LINK_ROLE,
            "outcome_access": "PIT_OUTCOME_SEALED",
        }
        if any(source[field] != value for field, value in expected_identity.items()):
            raise TrainingProgramError(
                "linked holdout source identity differs: "
                + link["source_training_episode_id"]
            )
        if source["source_program_state"] != "ACTIVE":
            raise TrainingProgramError("linked holdout source program must be ACTIVE")
        source_registered_at = _parse_time(
            source["source_program_registered_at"], "source_program.registered_at",
        )
        if source_registered_at is None or source_registered_at > registered_at:
            raise TrainingProgramError("linked holdout source must be registered before its successor")
        if source["provenance_role"] not in {
            "HISTORICAL_SELF_REPLAY", "ARCHIVED_EX_ANTE_EXTERNAL",
        }:
            raise TrainingProgramError("linked holdout source provenance is not historical PIT")
        if source["holdout_axis"] not in HOLDOUT_AXES:
            raise TrainingProgramError("linked holdout source has no valid holdout axis")
        if (
            source["holdout_axis"] in {"COMPANY", "COMPANY_AND_TIME"}
            and source["company_cluster_id"] in training_clusters
        ):
            raise TrainingProgramError(
                "linked company holdout cannot reuse a successor training company cluster"
            )
        # Outcome-window metadata was added after the original linked-program
        # contract. Preserve linked legacy programs; a V3 Forecast pairing is
        # the operation that requires a complete window proof.
        if (
            source["holdout_axis"] in {"TIME", "COMPANY_AND_TIME"}
            and source.get("outcome_window_ends_at") is not None
        ):
            source_opens = _parse_time(source["outcome_not_before"], "source_holdout.outcome_not_before")
            source_closes = _parse_time(
                source.get("outcome_window_ends_at"), "source_holdout.outcome_window_ends_at",
            )
            training_windows = [
                (
                    _parse_time(item["outcome_not_before"], "training.outcome_not_before"),
                    _parse_time(item.get("outcome_window_ends_at"), "training.outcome_window_ends_at"),
                )
                for item in training_rows
            ]
            if source_opens is None or source_closes is None or any(None in window for window in training_windows):
                raise TrainingProgramError(
                    "linked time holdout requires frozen outcome-window ends for itself and every successor training episode"
                )
            if any(
                _outcome_windows_overlap(training_opens, training_closes, source_opens, source_closes)
                for training_opens, training_closes in training_windows
            ):
                raise TrainingProgramError(
                    "linked time holdout outcome window overlaps a successor training outcome window"
                )
        freeze_event = conn.execute(
            """SELECT artifact_ref, recorded_at, content_json, content_text
                 FROM judgment_training_artifact_events
                WHERE training_episode_id = ? AND artifact_kind = 'freeze_ref'""",
            (source["training_episode_id"],),
        ).fetchone()
        if freeze_event is None:
            raise TrainingProgramError("linked holdout source has no immutable freeze receipt")
        intended_freeze = _artifact_snapshot(
            "freeze_ref", link["source_freeze_ref"], contract_path=contract_path,
        )
        if _event_snapshot(freeze_event) != intended_freeze:
            raise TrainingProgramError("linked holdout source freeze differs from its immutable snapshot")
        freeze_recorded_at = _parse_time(freeze_event["recorded_at"], "source_freeze.recorded_at")
        if freeze_recorded_at is None or freeze_recorded_at > registered_at:
            raise TrainingProgramError("linked holdout freeze must predate successor registration")
        if require_unexposed:
            exposure = conn.execute(
                f"""SELECT event.event_id
                       FROM judgment_feedback_events AS event
                       JOIN judgment_feedback_claims AS claim USING (feedback_item_id)
                      WHERE claim.episode_id = ?
                        AND claim.training_program_ref = ?
                        AND claim.program_lane = 'HISTORICAL_HOLDOUT'
                        AND event.event_type IN ({placeholders})
                      LIMIT 1""",
                (source["case_id"], source["source_contract_ref"], *outcome_event_types),
            ).fetchone()
            if exposure is not None:
                raise TrainingProgramError("linked holdout was exposed before successor registration")
        links.append({
            "program_id": program["program_id"],
            "source_program_id": source["program_id"],
            "source_training_episode_id": source["training_episode_id"],
            "source_case_id": source["case_id"],
            "source_freeze_ref": intended_freeze["artifact_ref"],
            "link_role": HOLDOUT_LINK_ROLE,
        })
    return links


def register_program(conn: sqlite3.Connection, contract_path: str | Path) -> dict[str, Any]:
    path = Path(contract_path).resolve()
    program = _read_json(path)
    validation = validate_program(program, contract_path=path)
    if validation["state"] != "REVIEWABLE":
        raise TrainingProgramError("invalid training program: " + "; ".join(validation["findings"]))
    registered_at = _parse_time(program["registered_at"], "registered_at")
    if registered_at is None:
        raise TrainingProgramError("registered_at must be a timezone-aware ISO-8601 timestamp")
    if registered_at > _now_dt():
        raise TrainingProgramError("program registered_at cannot be later than the real current time")
    program_row = {
        "program_id": program["program_id"],
        "program_state": program["program_state"],
        "method_version": program["method_version"],
        "method_scope": str(program.get("method_scope") or "SELECTION_AND_BOUNDARY").upper(),
        "required_selection_admission_version": program.get("required_selection_admission_version"),
        "registered_at": _iso(registered_at),
        "method_frozen_at": _iso(_parse_time(program["method_frozen_at"], "method_frozen_at")) if program.get("method_frozen_at") else None,
        "method_freeze_recorded_at": None,
        "sampling_policy_json": json.dumps(program["sampling_policy"], ensure_ascii=False, sort_keys=True),
        "contract_ref": str(path),
    }
    existing_program = conn.execute(
        "SELECT program_state FROM judgment_training_programs WHERE program_id = ?",
        (program["program_id"],),
    ).fetchone()
    activation_from_draft = bool(
        existing_program
        and existing_program["program_state"] == "DRAFT"
        and program["program_state"] == "ACTIVE"
    )
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
        review_recorded_at = None
        skip_selection_review = False
        if activation_from_draft and "selection_review_ref" in seed_events[episode["training_episode_id"]]:
            existing_review = _artifact_event_records(conn, episode["training_episode_id"]).get(
                "selection_review_ref"
            )
            if existing_review is None:
                # The later exact-set comparison produces the stable activation
                # error; a proposed review cannot be evaluated at the original
                # DRAFT registration timestamp.
                skip_selection_review = True
            else:
                review_recorded_at = _parse_time(
                    existing_review.get("recorded_at"), "selection_review_ref.recorded_at"
                )
                if review_recorded_at is None:
                    raise TrainingProgramError("selection review event recorded_at is invalid")
        _validate_seed_artifacts(
            episode,
            snapshots=seed_events[episode["training_episode_id"]],
            recorded_at=registered_at,
            required_selection_admission_version=program.get("required_selection_admission_version"),
            review_recorded_at=review_recorded_at,
            skip_selection_review=skip_selection_review,
        )
        episode_rows.append({
            **{field: episode[field] for field in (
                "training_episode_id", "case_id", "company_id", "company_cluster_id",
                "industry_id", "decision_domain", "lane", "provenance_role", "outcome_access",
            )},
            "program_id": program["program_id"],
            "cutoff_at": _iso(_parse_time(episode["cutoff_at"], "cutoff_at")),
            "outcome_not_before": _iso(_parse_time(episode["outcome_not_before"], "outcome_not_before")),
            "outcome_window_ends_at": (
                _iso(_parse_time(episode["outcome_window_ends_at"], "outcome_window_ends_at"))
                if episode.get("outcome_window_ends_at") is not None else None
            ),
            "holdout_axis": episode.get("holdout_axis"),
            "artifacts_json": json.dumps(artifacts, ensure_ascii=False, sort_keys=True),
        })
    program_already_registered = conn.execute(
        "SELECT 1 FROM judgment_training_programs WHERE program_id = ?",
        (program["program_id"],),
    ).fetchone() is not None
    link_rows = _resolve_holdout_link_rows(
        conn, program=program, contract_path=path,
        episode_rows=episode_rows, registered_at=registered_at,
        require_unexposed=not program_already_registered,
    )
    with conn:
        existing = conn.execute("SELECT * FROM judgment_training_programs WHERE program_id = ?", (program_row["program_id"],)).fetchone()
        if existing:
            comparable = {key: existing[key] for key in program_row}
            comparable_without_freeze = {
                key: value for key, value in comparable.items()
                if key not in {"method_frozen_at", "method_freeze_recorded_at"}
            }
            intended_without_freeze = {
                key: value for key, value in program_row.items()
                if key not in {"method_frozen_at", "method_freeze_recorded_at"}
            }
            state_upgrade = existing["program_state"] == "DRAFT" and program_row["program_state"] == "ACTIVE"
            scope_upgrade = (
                existing["method_scope"] == "SELECTION_AND_BOUNDARY"
                and program_row["method_scope"] == "BOUNDARY_ONLY"
                and existing["method_frozen_at"] is None
            )
            if state_upgrade or scope_upgrade:
                mutable_fields = set()
                if state_upgrade:
                    mutable_fields.add("program_state")
                if scope_upgrade:
                    mutable_fields.add("method_scope")
                comparable_without_freeze = {
                    key: value for key, value in comparable_without_freeze.items()
                    if key not in mutable_fields
                }
                intended_without_freeze = {
                    key: value for key, value in intended_without_freeze.items()
                    if key not in mutable_fields
                }
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
            if any(
                {
                    field: existing_by_id.get(key, {}).get(field)
                    for field in value
                    if field != "artifacts_json"
                }
                != {
                    field: field_value
                    for field, field_value in value.items()
                    if field != "artifacts_json"
                }
                for key, value in intended_by_id.items()
            ):
                raise TrainingProgramError("immutable training episode set differs: " + program_row["program_id"])
            if any(
                key not in intended_by_id and value["lane"] != "HISTORICAL_HOLDOUT"
                for key, value in existing_by_id.items()
            ):
                raise TrainingProgramError("only pre-exposure holdout reservations may extend a registered program")
            existing_links = [dict(row) for row in conn.execute(
                """SELECT * FROM judgment_training_holdout_links
                    WHERE program_id = ? ORDER BY source_training_episode_id""",
                (program_row["program_id"],),
            ).fetchall()]
            if existing_links != sorted(
                link_rows, key=lambda row: row["source_training_episode_id"],
            ):
                raise TrainingProgramError(
                    "immutable linked holdout set differs: " + program_row["program_id"]
                )
            for episode_id, expected_events in seed_events.items():
                actual_events = _artifact_events(conn, episode_id)
                if state_upgrade and set(actual_events) != set(expected_events):
                    raise TrainingProgramError(
                        f"activation training artifact set differs: {episode_id}"
                    )
                for kind, expected in expected_events.items():
                    if actual_events.get(kind) != expected:
                        raise TrainingProgramError(
                            f"immutable training artifact differs: {episode_id}:{kind}"
                        )
            if state_upgrade or scope_upgrade:
                with conn:
                    conn.execute(
                        "UPDATE judgment_training_programs SET program_state = ?, method_scope = ? WHERE program_id = ?",
                        (program_row["program_state"], program_row["method_scope"], program_row["program_id"]),
                    )
                return {
                    "schema_version": SCHEMA_VERSION,
                    "program_id": program_row["program_id"],
                    "registered": False,
                    "activated": True,
                    "method_scope_updated": scope_upgrade,
                    "idempotent": False,
                }
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
        for row in link_rows:
            columns = tuple(row)
            conn.execute(
                f"INSERT INTO judgment_training_holdout_links ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                tuple(row[column] for column in columns),
            )
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
    if kind == "case_ref":
        _validate_case_payload(row, payload)
        return
    if kind == "selection_review_ref":
        case_snapshot = existing.get("case_ref")
        if case_snapshot is None:
            raise TrainingProgramError("selection_review_ref requires a recorded case_ref")
        if method_frozen_at is not None:
            raise TrainingProgramError("selection review must be recorded before method freeze")
        _validate_selection_review_payload(
            row,
            review=payload,
            case_snapshot=case_snapshot,
            receipt_recorded_at=recorded_at,
        )
        return
    raise TrainingProgramError("unsupported artifact kind: " + kind)


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
    if at > _now_dt():
        raise TrainingProgramError("artifact recorded_at cannot be later than the real current time")
    row = conn.execute(
        """SELECT episode.*, program.method_frozen_at, program.method_freeze_recorded_at
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
    if kind == "freeze_ref" and row["lane"] == "HISTORICAL_HOLDOUT":
        if row["method_frozen_at"]:
            raise TrainingProgramError("holdout freeze cannot be recorded after method freeze")
        registered_claims = conn.execute(
            "SELECT COUNT(*) AS count FROM judgment_feedback_claims WHERE episode_id = ?",
            (row["case_id"],),
        ).fetchone()["count"]
        if registered_claims:
            raise TrainingProgramError("holdout freeze must precede control registration")
        exposed_training_events = conn.execute(
            """SELECT COUNT(*) AS count
                 FROM judgment_feedback_events AS event
                 JOIN judgment_feedback_claims AS claim USING (feedback_item_id)
                 JOIN judgment_training_episodes AS episode ON episode.case_id = claim.episode_id
                WHERE episode.program_id = ?
                  AND episode.lane = 'HISTORICAL_TRAINING'
                  AND event.event_type IN (
                    'OUTCOME_PACKAGE_READY', 'READ_ATTESTED', 'OUTCOME_EXTRACTED',
                    'CLAIM_SETTLED', 'MEASUREMENT_MISMATCH', 'OPERATING_OUTCOME_RECORDED',
                    'DIAGNOSIS_ACCEPTED', 'LEARNING_NOTE_READY', 'LEARNING_APPLIED'
                  )""",
            (row["program_id"],),
        ).fetchone()["count"]
        if exposed_training_events:
            raise TrainingProgramError("holdout freeze must precede all training outcome exposure")
    if kind == "selection_review_ref":
        registered_claims = conn.execute(
            "SELECT COUNT(*) AS count FROM judgment_feedback_claims WHERE episode_id = ?",
            (row["case_id"],),
        ).fetchone()["count"]
        if registered_claims:
            raise TrainingProgramError("selection review must precede feedback control registration")
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
    if at > _now_dt():
        raise TrainingProgramError("holdout reserved_at cannot be later than the real current time")
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
        "outcome_window_ends_at": (
            _iso(_parse_time(episode["outcome_window_ends_at"], "outcome_window_ends_at"))
            if episode.get("outcome_window_ends_at") is not None else None
        ),
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


def _program_episode_rows(
    conn: sqlite3.Connection, *, program_id: str, contract_ref: str,
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in conn.execute(
        "SELECT * FROM judgment_training_episodes WHERE program_id = ?",
        (program_id,),
    ).fetchall()]
    for row in rows:
        row["holdout_relation"] = "OWN"
        row["source_program_id"] = row["program_id"]
        row["control_contract_ref"] = contract_ref
    linked = [dict(row) for row in conn.execute(
        """SELECT episode.*, link.source_program_id,
                  source_program.contract_ref AS control_contract_ref
             FROM judgment_training_holdout_links AS link
             JOIN judgment_training_episodes AS episode
               ON episode.training_episode_id = link.source_training_episode_id
             JOIN judgment_training_programs AS source_program
               ON source_program.program_id = link.source_program_id
            WHERE link.program_id = ?""",
        (program_id,),
    ).fetchall()]
    for row in linked:
        row["holdout_relation"] = "LINKED"
    return sorted(rows + linked, key=lambda row: (row["cutoff_at"], row["training_episode_id"]))


def _control_items_by_binding(
    conn: sqlite3.Connection, *, program_id: str, rows: list[dict[str, Any]],
    as_of: datetime,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    by_binding: dict[tuple[str, str], list[dict[str, Any]]] = {}
    grouped_by_ref: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for contract_ref in sorted({row["control_contract_ref"] for row in rows}):
        grouped_by_ref[contract_ref] = _program_control_items(
            conn, contract_ref=contract_ref, as_of=as_of,
        )
    for row in rows:
        contract_ref = row["control_contract_ref"]
        case_id = row["case_id"]
        items = grouped_by_ref[contract_ref].get(case_id, [])
        if row["holdout_relation"] == "LINKED":
            filtered_items: list[dict[str, Any]] = []
            for item in items:
                records = [
                    event for event in item.get("event_records", [])
                    if event.get("event_type") != "HOLDOUT_EVALUATION_ACCEPTED"
                    or (event.get("payload") or {}).get("program_id") == program_id
                ]
                filtered_items.append({
                    **item,
                    "event_records": records,
                    "event_types": [event["event_type"] for event in records],
                })
            items = filtered_items
        by_binding[(contract_ref, case_id)] = items
    return by_binding


def _program_control_items(
    conn: sqlite3.Connection, *, contract_ref: str, as_of: datetime,
) -> dict[str, list[dict[str, Any]]]:
    projection = feedback_control.reconcile(conn, as_of=_iso(as_of))
    grouped: dict[str, list[dict[str, Any]]] = {}
    now = feedback_control._now_dt()
    for item in projection.get("items", []):
        if item.get("training_program_ref") != contract_ref:
            continue
        registered_at = _parse_time(item.get("registered_at"), "claim.registered_at")
        if registered_at is not None and registered_at > as_of and registered_at <= now:
            continue
        event_rows = conn.execute(
            """SELECT event_id, event_type, effective_at, recorded_at, payload_json
                 FROM judgment_feedback_events
                WHERE feedback_item_id = ?
                ORDER BY recorded_at, effective_at, event_id""",
            (item["feedback_item_id"],),
        ).fetchall()
        visible_event_rows = []
        for event in event_rows:
            effective_at = _parse_time(event["effective_at"], "event.effective_at")
            recorded_at = _parse_time(event["recorded_at"], "event.recorded_at")
            invalid_or_future = (
                effective_at is None
                or recorded_at is None
                or (recorded_at is not None and recorded_at > now)
                or (
                    effective_at is not None
                    and recorded_at is not None
                    and effective_at > recorded_at
                )
            )
            if invalid_or_future or (
                effective_at is not None
                and recorded_at is not None
                and effective_at <= as_of
                and recorded_at <= as_of
            ):
                visible_event_rows.append(event)
        item = {
            **item,
            "event_types": [event["event_type"] for event in visible_event_rows],
            "event_records": [
                {
                    "event_id": event["event_id"],
                    "event_type": event["event_type"],
                    "effective_at": event["effective_at"],
                    "recorded_at": event["recorded_at"],
                    "payload": json.loads(event["payload_json"]),
                }
                for event in visible_event_rows
            ],
        }
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
    rows: list[sqlite3.Row] = []
    for episode in _program_episode_rows(
        conn, program_id=program_id, contract_ref=contract_ref,
    ):
        if episode["lane"] != "HISTORICAL_HOLDOUT":
            continue
        rows.extend(conn.execute(
            f"""SELECT event.event_id, event.event_type, event.effective_at, event.recorded_at
                   FROM judgment_feedback_events AS event
                   JOIN judgment_feedback_claims AS claim USING (feedback_item_id)
                  WHERE claim.episode_id = ?
                    AND claim.program_lane = 'HISTORICAL_HOLDOUT'
                    AND claim.training_program_ref = ?
                    AND event.event_type IN ({placeholders})""",
            (episode["case_id"], episode["control_contract_ref"], *event_types),
        ).fetchall())
    return sorted(rows, key=lambda row: (row["recorded_at"], row["event_id"]))


def _accepted_application_times(
    conn: sqlite3.Connection, *, program_id: str, contract_ref: str, method_scope: str,
) -> list[datetime]:
    rows = conn.execute(
        """SELECT event.effective_at, event.recorded_at, event.payload_json,
                  claim.feedback_item_id, claim.episode_id, claim.company_id,
                  claim.training_program_ref
             FROM judgment_feedback_events AS event
             JOIN judgment_feedback_claims AS claim USING (feedback_item_id)
             JOIN judgment_training_episodes AS episode ON episode.case_id = claim.episode_id
            WHERE episode.program_id = ?
              AND episode.lane = 'HISTORICAL_TRAINING'
              AND claim.program_lane = 'HISTORICAL_TRAINING'
              AND claim.training_program_ref = ?
              AND claim.learning_eligibility = ?
              AND event.event_type = 'LEARNING_APPLIED'""",
        (
            program_id,
            contract_ref,
            "BOUNDARY_METHOD_ELIGIBLE" if method_scope == "BOUNDARY_ONLY" else "SELECTION_METHOD_ELIGIBLE",
        ),
    ).fetchall()
    times: list[datetime] = []
    now = _now_dt()
    for row in rows:
        effective_at = _parse_time(row["effective_at"], "learning_application.effective_at")
        recorded_at = _parse_time(row["recorded_at"], "learning_application.recorded_at")
        if (
            effective_at is None
            or recorded_at is None
            or effective_at > recorded_at
            or recorded_at > now
        ):
            continue
        try:
            payload = json.loads(row["payload_json"])
            note_id = str(payload.get("learning_note_event_id") or "")
            note = conn.execute(
                """SELECT effective_at
                     FROM judgment_feedback_events
                    WHERE event_id = ? AND feedback_item_id = ?
                      AND event_type = 'LEARNING_NOTE_READY'""",
                (note_id, row["feedback_item_id"]),
            ).fetchone()
            if note is None:
                continue
            feedback_control._validate_registered_v4_transfer_target(
                conn,
                {
                    "episode_id": row["episode_id"],
                    "company_id": row["company_id"],
                    "training_program_ref": row["training_program_ref"],
                },
                payload,
                source_note_effective_at=_parse_time(note["effective_at"], "learning_note.effective_at"),
                effective_at=effective_at,
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            # A method freeze must not recover an old malformed or unbound
            # transfer event merely because it has a plausible timestamp.
            continue
        times.extend((effective_at, recorded_at))
    return times


def _learning_chain_temporal_findings(
    control_items: list[dict[str, Any]],
) -> list[str]:
    learning_event_types = feedback_control.OUTCOME_EVENTS | {
        "DIAGNOSIS_ACCEPTED", "LEARNING_NOTE_READY", "LEARNING_APPLIED",
    }
    findings: list[str] = []
    now = _now_dt()
    for item in control_items:
        if item.get("learning_eligibility") not in {
            "SELECTION_METHOD_ELIGIBLE", "BOUNDARY_METHOD_ELIGIBLE",
        }:
            continue
        for event in item.get("event_records", []):
            if event.get("event_type") not in learning_event_types:
                continue
            event_id = str(event.get("event_id") or "UNKNOWN")
            effective_at = _parse_time(event.get("effective_at"), "learning_chain.effective_at")
            recorded_at = _parse_time(event.get("recorded_at"), "learning_chain.recorded_at")
            if effective_at is None or recorded_at is None:
                findings.append(f"learning_chain_event_time_invalid:{event_id}")
                continue
            if effective_at > recorded_at:
                findings.append(f"learning_chain_event_effective_after_recorded:{event_id}")
            if recorded_at > now:
                findings.append(f"learning_chain_event_recorded_in_future:{event_id}")
    return sorted(set(findings))


def _selection_bundle_joint_feedback(
    control_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Read the one immutable joint outcome once its whole selection bundle settles.

    Per-claim D3/D4 diagnostics remain visible below, but selection rights are
    governed by the pre-registered joint mapping.  A missing or mismatched
    shared feedback artifact is a repair condition, never a license to fall
    back to a directional per-claim state.
    """
    items = [
        item for item in control_items
        if item.get("selection_status") == "SELECTION_ADMITTED"
        and item.get("learning_eligibility") == "SELECTION_METHOD_ELIGIBLE"
    ]
    if not items:
        return None
    stage_ids = [str(item.get("stage_id") or "") for item in items]
    if (
        len(items) not in {5, 6}
        # ``feedback_control.reconcile`` orders rows by current operating
        # priority, not the registration contract order.  The topology is
        # exact, but its projection order is intentionally not meaningful.
        or frozenset(stage_ids) not in {
            frozenset(order) for order in feedback_control.SELECTION_STAGE_ORDERS
        }
    ):
        return {
            "state": "INVALID",
            "findings": ["selection_bundle_stage_identity_invalid"],
        }
    settlements = []
    for item in items:
        event = next(
            (
                row for row in reversed(item.get("event_records", []))
                if row.get("event_type") in feedback_control.OUTCOME_EVENTS
            ),
            None,
        )
        if event is None:
            return None
        settlements.append(event)
    refs = {
        str((event.get("payload") or {}).get("feedback_ref") or "").strip()
        for event in settlements
    }
    # Legacy/unit projections that do not carry a selection feedback artifact
    # are not a joint settlement.  Preserve their existing per-claim status;
    # a partially bound real bundle is still a repair condition below.
    if refs == {""}:
        return None
    if len(refs) != 1 or not next(iter(refs)):
        return {
            "state": "INVALID",
            "findings": ["selection_joint_feedback_binding_invalid"],
        }
    try:
        feedback = _read_json(Path(next(iter(refs))).expanduser().resolve())
    except TrainingProgramError:
        return {
            "state": "INVALID",
            "findings": ["selection_joint_feedback_unreadable"],
        }
    case_ids = {str(item.get("episode_id") or "") for item in items}
    if (
        feedback.get("schema_version") != "judgment-selection-feedback-card.v1"
        or len(case_ids) != 1
        or feedback.get("case_id") != next(iter(case_ids))
    ):
        return {
            "state": "INVALID",
            "findings": ["selection_joint_feedback_identity_invalid"],
        }
    cards = feedback.get("cards")
    expected_cards = {
        str(item.get("claim_id") or ""): str(item.get("stage_id") or "")
        for item in items
    }
    actual_cards = {
        str(card.get("claim_id") or ""): str(card.get("stage_id") or "")
        for card in cards if isinstance(card, dict)
    } if isinstance(cards, list) else {}
    if len(actual_cards) != len(cards or []) or actual_cards != expected_cards:
        return {
            "state": "INVALID",
            "findings": ["selection_joint_feedback_cards_invalid"],
        }
    joint = feedback.get("joint_comparison")
    verdict = str(joint.get("overall_verdict") or "").upper() if isinstance(joint, dict) else ""
    if verdict not in {"A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC"}:
        return {
            "state": "INVALID",
            "findings": ["selection_joint_feedback_verdict_invalid"],
        }
    return {"state": "SETTLED", "overall_verdict": verdict, "feedback_ref": next(iter(refs))}


def freeze_method(conn: sqlite3.Connection, *, program_id: str, method_version: str, frozen_at: str) -> dict[str, Any]:
    """Freeze the method once before any reserved holdout is revealed."""
    at = _parse_time(frozen_at, "frozen_at")
    if at is None:
        raise TrainingProgramError("frozen_at must be a timezone-aware ISO-8601 timestamp")
    recorded_at = _now_dt()
    if at > recorded_at:
        raise TrainingProgramError("method freeze cannot be effective in the future")
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
        if not program["method_freeze_recorded_at"]:
            raise TrainingProgramError(
                "existing method freeze has no recorded-at receipt and cannot be backfilled"
            )
        existing_recorded_at = _parse_time(
            program["method_freeze_recorded_at"], "method_freeze_recorded_at",
        )
        if existing_recorded_at is None or existing_recorded_at > recorded_at or at > existing_recorded_at:
            raise TrainingProgramError("existing method freeze receipt has an invalid time order")
        return {
            "schema_version": SCHEMA_VERSION,
            "program_id": program_id,
            "method_scope": program["method_scope"],
            "method_frozen_at": program["method_frozen_at"],
            "method_freeze_recorded_at": program["method_freeze_recorded_at"],
            "idempotent": True,
        }
    rows = _program_episode_rows(
        conn, program_id=program_id, contract_ref=program["contract_ref"],
    )
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
        conn, program_id=program_id, contract_ref=program["contract_ref"], method_scope=program["method_scope"],
    )
    if not application_times:
        raise TrainingProgramError("method freeze requires an accepted cross-company learning application")
    if at < max(application_times):
        raise TrainingProgramError("method freeze cannot predate the accepted learning application")
    control_by_binding = _control_items_by_binding(
        conn, program_id=program_id, rows=rows, as_of=at,
    )
    training_states = [
        _episode_status(
            row, as_of=at, method_frozen_at=None,
            method_freeze_recorded_at=None,
            artifacts=_artifact_event_records(conn, row["training_episode_id"]),
            control_items=control_by_binding.get(
                (row["control_contract_ref"], row["case_id"]), [],
            ),
            program_id=program_id, conn=conn,
        )["state"]
        for row in training_rows
    ]
    if "TRANSFER_APPLIED" not in training_states:
        scope_label = "boundary" if program["method_scope"] == "BOUNDARY_ONLY" else "selection"
        raise TrainingProgramError(f"method freeze requires a {scope_label}-eligible TRANSFER_APPLIED episode")
    permitted_training_terminal = {"TRANSFER_APPLIED", "MECHANISM_SETTLED"}
    if any(state not in permitted_training_terminal for state in training_states):
        raise TrainingProgramError("all historical training episodes must be terminal before method freeze")
    holdout_states = [
        _episode_status(
            row, as_of=at, method_frozen_at=None,
            method_freeze_recorded_at=None,
            artifacts=_artifact_event_records(conn, row["training_episode_id"]),
            control_items=control_by_binding.get(
                (row["control_contract_ref"], row["case_id"]), [],
            ),
            program_id=program_id, conn=conn,
        )["state"]
        for row in holdout_rows
    ]
    if any(state != "WAITING_FOR_METHOD_FREEZE" for state in holdout_states):
        raise TrainingProgramError("every historical holdout must be frozen and unexposed before method freeze")
    with conn:
        conn.execute(
            """UPDATE judgment_training_programs
                  SET method_frozen_at = ?, method_freeze_recorded_at = ?
                WHERE program_id = ?""",
            (_iso(at), _iso(recorded_at), program_id),
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "program_id": program_id,
        "method_scope": program["method_scope"],
        "method_frozen_at": _iso(at),
        "method_freeze_recorded_at": _iso(recorded_at),
        "idempotent": False,
    }


def resolve_frozen_company_time_holdout(
    conn: sqlite3.Connection, *, program_id: str, training_episode_id: str, as_of: str,
    require_outcome_window: bool = False,
) -> dict[str, Any]:
    """Return the canonical pre-outcome holdout identity for Forecast pairing.

    This is intentionally a metadata resolver: it reads no result, feedback
    payload, source material or forecast probability.  Forecast controls use
    it instead of accepting a caller-authored ticker/cutoff holdout claim.
    """
    as_of_at = _parse_time(as_of, "as_of")
    if as_of_at is None:
        raise TrainingProgramError("as_of must be a timezone-aware ISO-8601 timestamp")
    row = conn.execute(
        """SELECT episode.*, program.program_state, program.method_version,
                  program.method_frozen_at, program.method_freeze_recorded_at
             FROM judgment_training_episodes AS episode
             JOIN judgment_training_programs AS program ON program.program_id = episode.program_id
             WHERE episode.program_id = ? AND episode.training_episode_id = ?""",
        (program_id, training_episode_id),
    ).fetchone()
    if row is None:
        raise TrainingProgramError("unknown company-and-time holdout episode")
    if row["program_state"] != "ACTIVE":
        raise TrainingProgramError("company-and-time holdout program must be ACTIVE")
    if row["lane"] != "HISTORICAL_HOLDOUT" or row["holdout_axis"] != "COMPANY_AND_TIME":
        raise TrainingProgramError("episode is not a COMPANY_AND_TIME historical holdout")
    if row["provenance_role"] not in {"HISTORICAL_SELF_REPLAY", "ARCHIVED_EX_ANTE_EXTERNAL"}:
        raise TrainingProgramError("company-and-time holdout lacks historical PIT provenance")
    if row["outcome_access"] != "PIT_OUTCOME_SEALED":
        raise TrainingProgramError("company-and-time holdout outcome access is not PIT_OUTCOME_SEALED")
    method_frozen_at = _parse_time(row["method_frozen_at"], "method_frozen_at")
    receipt_at = _parse_time(row["method_freeze_recorded_at"], "method_freeze_recorded_at")
    if method_frozen_at is None or receipt_at is None:
        raise TrainingProgramError("company-and-time holdout requires an immutable recorded method freeze")
    if method_frozen_at > receipt_at or receipt_at >= as_of_at:
        raise TrainingProgramError("company-and-time holdout method freeze must precede pairing")
    cutoff_at = _parse_time(row["cutoff_at"], "holdout.cutoff_at")
    outcome_not_before = _parse_time(row["outcome_not_before"], "holdout.outcome_not_before")
    if cutoff_at is None or outcome_not_before is None or cutoff_at >= outcome_not_before:
        raise TrainingProgramError("company-and-time holdout has invalid frozen time metadata")
    resolved = {
        "program_id": row["program_id"],
        "method_version": row["method_version"],
        "holdout_training_episode_id": row["training_episode_id"],
        "company_id": row["company_id"],
        "company_cluster_id": row["company_cluster_id"],
        "cutoff_at": _iso(cutoff_at),
        "outcome_not_before": _iso(outcome_not_before),
        "method_frozen_at": _iso(method_frozen_at),
        "method_freeze_recorded_at": _iso(receipt_at),
    }
    if not require_outcome_window:
        return resolved

    training_rows = [dict(item) for item in conn.execute(
        """SELECT training_episode_id, company_cluster_id, outcome_not_before, outcome_window_ends_at
             FROM judgment_training_episodes
            WHERE program_id = ? AND lane = 'HISTORICAL_TRAINING'
            ORDER BY training_episode_id""",
        (program_id,),
    ).fetchall()]
    if not training_rows:
        raise TrainingProgramError("company-and-time holdout program has no historical training truth")
    training_clusters = {str(item["company_cluster_id"]) for item in training_rows}
    if row["company_cluster_id"] in training_clusters:
        raise TrainingProgramError("company-and-time holdout reuses a historical training company cluster")

    holdout_closes = _parse_time(row["outcome_window_ends_at"], "holdout.outcome_window_ends_at")
    if holdout_closes is None or holdout_closes <= outcome_not_before:
        raise TrainingProgramError("company-and-time holdout requires a valid frozen outcome-window end")
    training_windows: list[dict[str, str]] = []
    for training in training_rows:
        training_opens = _parse_time(training["outcome_not_before"], "training.outcome_not_before")
        training_closes = _parse_time(
            training["outcome_window_ends_at"], "training.outcome_window_ends_at",
        )
        if training_opens is None or training_closes is None or training_closes <= training_opens:
            raise TrainingProgramError(
                "company-and-time holdout requires a valid frozen outcome window for every historical training episode"
            )
        if _outcome_windows_overlap(training_opens, training_closes, outcome_not_before, holdout_closes):
            raise TrainingProgramError(
                "company-and-time holdout outcome window overlaps a historical training outcome window"
            )
        training_windows.append({
            "training_episode_id": training["training_episode_id"],
            "company_cluster_id": training["company_cluster_id"],
            "opens_after": _iso(training_opens),
            "closes_at": _iso(training_closes),
        })
    return {
        **resolved,
        "outcome_window_ends_at": _iso(holdout_closes),
        "training_company_cluster_ids": sorted(training_clusters),
        "training_outcome_windows": training_windows,
    }


def resolve_frozen_method(
    conn: sqlite3.Connection, *, program_id: str, method_version: str, as_of: str,
) -> dict[str, Any]:
    """Resolve one recorded method identity without reading cases or outcomes."""
    as_of_at = _parse_time(as_of, "as_of")
    if as_of_at is None:
        raise TrainingProgramError("as_of must be a timezone-aware ISO-8601 timestamp")
    program = conn.execute(
        "SELECT * FROM judgment_training_programs WHERE program_id = ?", (program_id,),
    ).fetchone()
    if program is None:
        raise TrainingProgramError("unknown frozen method program")
    if program["program_state"] != "ACTIVE" or program["method_version"] != method_version:
        raise TrainingProgramError("program is not the requested active method version")
    method_frozen_at = _parse_time(program["method_frozen_at"], "method_frozen_at")
    receipt_at = _parse_time(program["method_freeze_recorded_at"], "method_freeze_recorded_at")
    if method_frozen_at is None or receipt_at is None:
        raise TrainingProgramError("method identity requires an immutable recorded freeze receipt")
    if method_frozen_at > receipt_at or receipt_at >= as_of_at:
        raise TrainingProgramError("method freeze must precede the forecast freeze")
    return {
        "program_id": program["program_id"],
        "method_version": program["method_version"],
        "method_frozen_at": _iso(method_frozen_at),
        "method_freeze_recorded_at": _iso(receipt_at),
    }


def release_method_for_report_use(
    conn: sqlite3.Connection, *, receipt_ref: str | Path,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Release a frozen method only after every reserved holdout supports it."""
    path = Path(receipt_ref).expanduser().resolve()
    receipt = _read_json(path)
    if receipt.get("schema_version") != METHOD_REPORT_RELEASE_SCHEMA_VERSION:
        raise TrainingProgramError(
            f"release receipt must use {METHOD_REPORT_RELEASE_SCHEMA_VERSION}"
        )
    required_text = (
        "release_id", "program_id", "method_version", "method_scope",
        "method_frozen_at", "released_at", "released_by", "release_decision",
    )
    missing = [field for field in required_text if not isinstance(receipt.get(field), str) or not receipt[field].strip()]
    if missing:
        raise TrainingProgramError("release receipt fields missing: " + ", ".join(missing))
    if receipt["release_decision"] != "METHOD_RELEASED_FOR_REPORT_USE":
        raise TrainingProgramError("release_decision must be METHOD_RELEASED_FOR_REPORT_USE")
    now = _now_dt()
    recorded = _parse_time(recorded_at, "recorded_at") if recorded_at is not None else now
    released = _parse_time(receipt.get("released_at"), "released_at")
    receipt_frozen = _parse_time(receipt.get("method_frozen_at"), "method_frozen_at")
    if recorded is None or released is None or receipt_frozen is None:
        raise TrainingProgramError("release times must be timezone-aware ISO-8601 timestamps")
    if released > recorded or recorded > now:
        raise TrainingProgramError("method release requires released_at <= recorded_at <= real current time")

    program = conn.execute(
        "SELECT * FROM judgment_training_programs WHERE program_id = ?",
        (receipt["program_id"],),
    ).fetchone()
    if not program:
        raise TrainingProgramError("unknown training program: " + receipt["program_id"])
    if program["program_state"] != "ACTIVE":
        raise TrainingProgramError("draft training programs cannot be released for report use")
    if program["method_version"] != receipt["method_version"] or program["method_scope"] != receipt["method_scope"]:
        raise TrainingProgramError("release receipt method identity does not match the registered program")
    frozen = _parse_time(program["method_frozen_at"], "registered_method_frozen_at")
    freeze_recorded = _parse_time(program["method_freeze_recorded_at"], "method_freeze_recorded_at")
    if frozen is None or freeze_recorded is None:
        raise TrainingProgramError("method must be frozen with a recorded receipt before report release")
    if receipt_frozen != frozen:
        raise TrainingProgramError("release receipt method_frozen_at does not match database truth")
    if released < max(frozen, freeze_recorded):
        raise TrainingProgramError("method release cannot predate method freeze and its recording")

    status = reconcile(conn, program_id=program["program_id"], as_of=_iso(released))
    if status["historical_method_state"] != "HISTORICAL_EVALUATION_COMPLETE":
        raise TrainingProgramError("report release requires completed, clean historical holdout evaluation")
    holdout_bindings = [
        row for row in _program_episode_rows(
            conn, program_id=program["program_id"], contract_ref=program["contract_ref"],
        )
        if row["lane"] == "HISTORICAL_HOLDOUT"
    ]
    holdout_rows: list[dict[str, Any]] = []
    for episode in holdout_bindings:
        holdout_rows.extend(dict(row) for row in conn.execute(
            """SELECT ? AS training_episode_id, event.event_id, event.effective_at,
                      event.recorded_at, event.payload_json
                 FROM judgment_feedback_claims AS claim
                 JOIN judgment_feedback_events AS event
                   ON event.feedback_item_id = claim.feedback_item_id
                WHERE claim.episode_id = ?
                  AND claim.training_program_ref = ?
                  AND event.event_type = 'HOLDOUT_EVALUATION_ACCEPTED'
                ORDER BY event.recorded_at, event.event_id""",
            (
                episode["training_episode_id"], episode["case_id"],
                episode["control_contract_ref"],
            ),
        ).fetchall())
    holdout_ids = {row["training_episode_id"] for row in holdout_bindings}
    relation_by_holdout = {
        row["training_episode_id"]: row["holdout_relation"] for row in holdout_bindings
    }
    latest_by_holdout: dict[str, dict[str, Any]] = {}
    for row in holdout_rows:
        payload = json.loads(row["payload_json"])
        payload_program_id = payload.get("program_id")
        if payload_program_id not in {None, program["program_id"]}:
            continue
        if (
            relation_by_holdout[row["training_episode_id"]] == "LINKED"
            and payload_program_id != program["program_id"]
        ):
            continue
        latest_by_holdout[row["training_episode_id"]] = row
    if set(latest_by_holdout) != holdout_ids:
        raise TrainingProgramError("every reserved holdout requires an accepted evaluation receipt")
    accepted_receipt_ids: list[str] = []
    for training_episode_id, row in latest_by_holdout.items():
        payload = json.loads(row["payload_json"])
        if str(payload.get("evaluation_verdict") or "").upper() != "SUPPORTED":
            raise TrainingProgramError(
                f"holdout {training_episode_id} did not support the frozen method"
            )
        event_recorded = _parse_time(row["recorded_at"], "holdout_evaluation.recorded_at")
        if event_recorded is None or event_recorded > released:
            raise TrainingProgramError("method release cannot predate holdout evaluation acceptance")
        receipt_id = str(payload.get("receipt_id") or "").strip()
        if not receipt_id:
            raise TrainingProgramError("holdout evaluation receipt_id is missing")
        accepted_receipt_ids.append(receipt_id)
    declared_receipts = receipt.get("accepted_holdout_receipt_ids")
    if not isinstance(declared_receipts, list) or sorted(declared_receipts) != sorted(accepted_receipt_ids):
        raise TrainingProgramError("release receipt does not bind the accepted holdout receipt set")

    snapshot = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    existing = conn.execute(
        "SELECT * FROM judgment_training_method_releases WHERE program_id = ?",
        (program["program_id"],),
    ).fetchone()
    if existing:
        intended = {
            "release_id": receipt["release_id"],
            "method_version": receipt["method_version"],
            "method_scope": receipt["method_scope"],
            "method_frozen_at": _iso(frozen),
            "released_at": _iso(released),
            "released_by": receipt["released_by"],
            "release_decision": receipt["release_decision"],
            "receipt_json": snapshot,
        }
        if any(existing[field] != value for field, value in intended.items()):
            raise TrainingProgramError("method report release is immutable once recorded")
        return {
            "schema_version": METHOD_REPORT_RELEASE_SCHEMA_VERSION,
            "program_id": program["program_id"],
            "release_id": existing["release_id"],
            "release_decision": existing["release_decision"],
            "idempotent": True,
        }
    with conn:
        conn.execute(
            """INSERT INTO judgment_training_method_releases
                 (program_id, release_id, method_version, method_scope, method_frozen_at,
                  released_at, recorded_at, released_by, release_decision, receipt_ref, receipt_json)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                program["program_id"], receipt["release_id"], receipt["method_version"],
                receipt["method_scope"], _iso(frozen), _iso(released), _iso(recorded),
                receipt["released_by"], receipt["release_decision"], str(path), snapshot,
            ),
        )
    return {
        "schema_version": METHOD_REPORT_RELEASE_SCHEMA_VERSION,
        "program_id": program["program_id"],
        "release_id": receipt["release_id"],
        "release_decision": receipt["release_decision"],
        "idempotent": False,
    }


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
    elif lane == "HISTORICAL_TRAINING":
        eligibility = "BOUNDARY_METHOD_ELIGIBLE"
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
    method_freeze_recorded_at: datetime | None,
    artifacts: dict[str, dict[str, Any]], control_items: list[dict[str, Any]],
    program_id: str | None = None, conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    lane = row["lane"]
    findings: list[str] = []
    case_snapshot = artifacts.get("case_ref")
    case = _snapshot_payload(case_snapshot, kind="case_ref") if case_snapshot else None
    if case is not None:
        if case.get("schema_version") == CANDIDATE_SCHEMA_VERSION:
            result = validate_selection_candidate(case)
            if result.get("state") != "REVIEWABLE":
                findings.extend("case:" + item for item in _validation_findings(result))
            if result.get("state") == "REVIEWABLE":
                for field in ("case_id", "company_id", "company_cluster_id", "industry_id"):
                    expected = row[field]
                    actual = case.get(field)
                    if actual != expected:
                        findings.append("case:" + field + "_mismatch")
                case_cutoff = _parse_time(case.get("cutoff_at"), "selection_candidate.cutoff_at")
                episode_cutoff = _parse_time(row["cutoff_at"], "episode.cutoff_at")
                if case_cutoff is None or episode_cutoff is None or case_cutoff != episode_cutoff:
                    findings.append("case:cutoff_at_mismatch")
            review_snapshot = artifacts.get("selection_review_ref")
            if review_snapshot is None:
                if control_items:
                    findings.append("selection_control_registered_before_independent_review")
                if findings:
                    return {"state": "NEEDS_REPAIR", "actionable": True, "findings": sorted(set(findings))}
                return {
                    "state": "AWAITING_SELECTION_REVIEW",
                    "actionable": True,
                    "findings": ["selection_review_required"],
                }
            review = _snapshot_payload(review_snapshot, kind="selection_review_ref")
            review_result = validate_selection_review(
                review,
                candidate=case,
                case_artifact_ref=case_snapshot.get("artifact_ref"),
                receipt_recorded_at=review_snapshot.get("recorded_at"),
            )
            if review_result.get("state") != "REVIEWABLE":
                findings.extend("selection_review:" + item for item in _validation_findings(review_result))
        elif case.get("schema_version") == "judgment-boundary-case.v1":
            result = validate_boundary_case(case)
        else:
            result = validate_case(case, allow_test_fixtures=False)
        if result.get("state") != "REVIEWABLE":
            findings.extend("case:" + item for item in _validation_findings(result))
        if case.get("case_id") != row["case_id"]:
            findings.append("case_id_mismatch")
    elif "selection_review_ref" in artifacts:
        findings.append("selection_review_without_case_ref")
    if any(item.get("program_lane") != lane for item in control_items):
        findings.append("control_program_lane_mismatch")
    frozen = case is not None or "freeze_ref" in artifacts
    freeze_recorded_at = None
    if lane == "HISTORICAL_HOLDOUT" and frozen:
        freeze_snapshot = artifacts.get("freeze_ref")
        freeze_recorded_at = _parse_time(
            (freeze_snapshot or {}).get("recorded_at"), "freeze_artifact.recorded_at",
        )
        if freeze_recorded_at is None:
            findings.append("freeze_artifact_recorded_at_invalid")
        elif freeze_recorded_at > feedback_control._now_dt():
            findings.append("freeze_artifact_recorded_in_future")
    if lane == "HISTORICAL_HOLDOUT" and any(
        event.get("event_type") == "OUTCOME_EXPOSURE_BREACH"
        for item in control_items
        for event in item.get("event_records", [])
    ):
        return {
            "state": "EXPOSURE_BREACH",
            "actionable": False,
            "findings": ["holdout_outcome_exposure_breach_recorded"],
        }
    if control_items and not frozen:
        findings.append("control_registered_before_episode_freeze")
    if any(item.get("selection_status") == "SELECTION_ADMITTED" for item in control_items) and case is None:
        findings.append("selection_training_requires_structured_case_ref")
    if findings:
        return {"state": "NEEDS_REPAIR", "actionable": True, "findings": sorted(set(findings))}

    if lane == "HISTORICAL_HOLDOUT" and method_frozen_at is not None and method_freeze_recorded_at is None:
        return {
            "state": "NEEDS_REPAIR",
            "actionable": True,
            "findings": ["method_freeze_recorded_at_missing"],
        }
    if lane == "HISTORICAL_HOLDOUT" and frozen and freeze_recorded_at is not None:
        if method_frozen_at is not None and freeze_recorded_at > method_frozen_at:
            return {
                "state": "NEEDS_REPAIR",
                "actionable": True,
                "findings": ["holdout_freeze_recorded_after_method_freeze"],
            }

    if not frozen:
        if lane == "HISTORICAL_TEACHING":
            return {"state": "READY_FOR_BOUNDARY_REVIEW", "actionable": True, "findings": []}
        if lane == "HISTORICAL_HOLDOUT" and method_frozen_at is None:
            return {"state": "HOLDOUT_RESERVATION_INCOMPLETE", "actionable": True, "findings": []}
        return {"state": "READY_TO_FREEZE", "actionable": True, "findings": []}

    event_types = {event for item in control_items for event in item.get("event_types", [])}
    settled_items = [
        item for item in control_items
        if any(
            event.get("event_type") in feedback_control.OUTCOME_EVENTS
            for event in item.get("event_records", [])
        )
    ]
    method_items = [
        item for item in control_items
        if item.get("learning_eligibility") in {"SELECTION_METHOD_ELIGIBLE", "BOUNDARY_METHOD_ELIGIBLE"}
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
        if (
            row.get("holdout_relation") == "LINKED"
            and row.get("case_id") == feedback_control.R103_HOLDOUT_CASE_ID
            and program_id
            and conn is not None
        ):
            freeze_ref = str((artifacts.get("freeze_ref") or {}).get("artifact_ref") or "")
            gate = feedback_control.r103_linked_holdout_administrative_gate(
                conn,
                program_id=program_id,
                source_program_id=str(row.get("source_program_id") or ""),
                training_episode_id=str(row.get("training_episode_id") or ""),
                case_id=str(row.get("case_id") or ""),
                holdout_freeze_ref=freeze_ref,
                as_of=as_of,
            )
            if gate["state"] != "NOT_APPLICABLE":
                return gate
        if not control_items:
            return {"state": "READY_FOR_CONTROL_REGISTRATION", "actionable": True, "findings": []}
        if any(item.get("learning_eligibility") != "EVALUATION_ONLY" for item in control_items):
            return {"state": "NEEDS_REPAIR", "actionable": True, "findings": ["holdout_control_not_evaluation_only"]}
        if any(not str(item.get("pre_reveal_review_receipt_ref") or "").strip() for item in control_items):
            return {"state": "NEEDS_REPAIR", "actionable": True, "findings": ["pre_reveal_review_receipt_missing"]}
        temporal_findings: list[str] = []
        now = feedback_control._now_dt()
        registration_times: list[datetime] = []
        for item in control_items:
            registered_at = _parse_time(item.get("registered_at"), "claim.registered_at")
            if registered_at is None:
                temporal_findings.append("claim_registered_at_invalid")
                continue
            registration_times.append(registered_at)
            if registered_at > now:
                temporal_findings.append("claim_registered_in_future")
            if freeze_recorded_at is None or freeze_recorded_at > registered_at:
                temporal_findings.append("holdout_freeze_recorded_after_claim_registration")
            try:
                feedback_control._holdout_pre_reveal_context(item)
            except feedback_control.ControlPlaneError as exc:
                temporal_findings.append(exc.code)
        event_records = [
            event
            for item in control_items
            for event in item.get("event_records", [])
        ]
        if any(event.get("event_type") == "OUTCOME_EXPOSURE_BREACH" for event in event_records):
            return {
                "state": "EXPOSURE_BREACH",
                "actionable": False,
                "findings": ["holdout_outcome_exposure_breach_recorded"],
            }
        outcome_records = [
            event for event in event_records
            if event.get("event_type") in feedback_control.OUTCOME_PIPELINE_EVENTS | feedback_control.OUTCOME_EVENTS
        ]
        parsed_outcomes: list[tuple[datetime, datetime, dict[str, Any]]] = []
        for event in outcome_records:
            effective = _parse_time(event.get("effective_at"), "holdout_event.effective_at")
            recorded = _parse_time(event.get("recorded_at"), "holdout_event.recorded_at")
            if effective is None or recorded is None:
                temporal_findings.append("holdout_event_time_invalid")
                continue
            parsed_outcomes.append((effective, recorded, event))
            if effective > recorded:
                temporal_findings.append("holdout_event_effective_after_recorded")
            if recorded > now:
                temporal_findings.append("holdout_event_recorded_in_future")
        if parsed_outcomes:
            first_effective, first_recorded, first_event = min(parsed_outcomes, key=lambda value: value[1])
            prerequisites = [method_frozen_at, method_freeze_recorded_at, *registration_times]
            if any(value is None or first_recorded <= value for value in prerequisites):
                temporal_findings.append("holdout_first_outcome_not_after_freeze_and_registration")
            first_access_raw = (first_event.get("payload") or {}).get("first_outcome_accessed_at")
            first_access = _parse_time(first_access_raw, "first_outcome_accessed_at")
            if first_access is None:
                temporal_findings.append("first_outcome_accessed_at_missing")
            else:
                pre_reviews: list[datetime] = []
                for item in control_items:
                    try:
                        pre_reviews.append(feedback_control._holdout_pre_reveal_context(item)["reviewed_at"])
                    except feedback_control.ControlPlaneError:
                        pass
                access_prerequisites = [method_frozen_at, method_freeze_recorded_at, *registration_times, *pre_reviews]
                if any(value is None or value > first_access for value in access_prerequisites):
                    temporal_findings.append("first_outcome_access_precedes_prerequisites")
                if first_access > first_effective:
                    temporal_findings.append("first_outcome_access_after_effective_settlement")
        if temporal_findings:
            return {
                "state": "NEEDS_REPAIR",
                "actionable": True,
                "findings": sorted(set(temporal_findings)),
            }
        if event_types & feedback_control.HOLDOUT_PROHIBITED_RIGHT_EVENTS:
            return {"state": "NEEDS_REPAIR", "actionable": True, "findings": ["holdout_evaluation_rights_breach"]}
        holdout_clocks = {
            match.group(1)
            for item in control_items
            if (match := re.match(r"^(D[1-5])(?:_|$)", str(item.get("stage_id") or "").upper()))
        }
        if len(control_items) != 5 or holdout_clocks != {"D1", "D2", "D3", "D4", "D5"}:
            return {"state": "HOLDOUT_CONTROL_INCOMPLETE", "actionable": True, "findings": ["holdout_d1_d5_required"]}
        if len(settled_items) == len(control_items):
            if "HOLDOUT_EVALUATION_ACCEPTED" in event_types:
                return {"state": "EVALUATED_HOLDOUT", "actionable": False, "findings": []}
            return {"state": "EVALUATION_RECEIPT_PENDING", "actionable": True, "findings": []}
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
    learning_chain_findings = _learning_chain_temporal_findings(control_items)
    if learning_chain_findings:
        return {
            "state": "INVALID_LEARNING_CHAIN",
            "actionable": True,
            "findings": ["invalid_learning_chain", *learning_chain_findings],
        }
    selection_joint = _selection_bundle_joint_feedback(control_items)
    if selection_joint and selection_joint["state"] == "INVALID":
        return {
            "state": "NEEDS_REPAIR",
            "actionable": True,
            "findings": selection_joint["findings"],
        }
    if selection_joint and selection_joint.get("overall_verdict") == "MIXED":
        return {
            "state": "MIXED_MECHANISM_BOUNDARY_CAPTURED",
            "actionable": False,
            "findings": [
                "non_directional_mixed_mechanism_boundary",
                "directional_selection_learning_prohibited",
                "new_selection_training_episode_required",
            ],
        }
    measurement_boundary_notes = [
        event
        for item in control_items
        for event in item.get("event_records", [])
        if event.get("event_type") == "LEARNING_NOTE_READY"
        and str((event.get("payload") or {}).get("learning_scope") or "").upper()
        == "MEASUREMENT_BOUNDARY"
    ]
    if measurement_boundary_notes and len(settled_items) == len(control_items):
        return {
            "state": "MEASUREMENT_BOUNDARY_CAPTURED",
            "actionable": False,
            "findings": [
                "non_directional_measurement_learning_only",
                "new_selection_training_episode_required",
            ],
        }
    if "LEARNING_APPLIED" in event_types:
        return {"state": "TRANSFER_APPLIED", "actionable": False, "findings": []}
    if method_items:
        learning_states = {item.get("learning_state") for item in method_items}
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
    rows = _program_episode_rows(
        conn, program_id=program_id, contract_ref=program["contract_ref"],
    )
    method_frozen_at = _parse_time(program["method_frozen_at"], "method_frozen_at") if program["method_frozen_at"] else None
    method_freeze_recorded_at = (
        _parse_time(program["method_freeze_recorded_at"], "method_freeze_recorded_at")
        if program["method_freeze_recorded_at"] else None
    )
    report_release = conn.execute(
        "SELECT release_id, released_at FROM judgment_training_method_releases WHERE program_id = ?",
        (program_id,),
    ).fetchone()
    control_by_binding = _control_items_by_binding(
        conn, program_id=program_id, rows=rows, as_of=as_of_dt,
    )
    items = []
    for row in rows:
        status = _episode_status(
            row, as_of=as_of_dt, method_frozen_at=method_frozen_at,
            method_freeze_recorded_at=method_freeze_recorded_at,
            artifacts=_artifact_event_records(conn, row["training_episode_id"]),
            control_items=control_by_binding.get(
                (row["control_contract_ref"], row["case_id"]), [],
            ),
            program_id=program_id, conn=conn,
        )
        lineage = (
            {
                "holdout_relation": "LINKED",
                "source_program_id": row["source_program_id"],
            }
            if row["holdout_relation"] == "LINKED"
            else {}
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
            **lineage,
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
    needs_repair = any(
        item["state"] in {"NEEDS_REPAIR", "EXPOSURE_BREACH", "INVALID_LEARNING_CHAIN"}
        for item in historical_items
    )
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
        historical_method_state = (
            "READY_TO_FREEZE_BOUNDARY_METHOD"
            if program["method_scope"] == "BOUNDARY_ONLY"
            else "READY_TO_FREEZE_METHOD"
        )
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

    if program["program_state"] == "DRAFT":
        historical_method_state = "PROGRAM_DRAFT"
        system_state = "DRAFT"
    elif historical_method_state == "NEEDS_REPAIR":
        system_state = "NEEDS_REPAIR"
    elif historical_method_state == "HISTORICAL_EVALUATION_COMPLETE":
        system_state = "HISTORICAL_EVALUATION_COMPLETE"
    else:
        system_state = "ACTIVE"
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "program_id": program_id,
        "method_version": program["method_version"],
        "method_scope": program["method_scope"],
        "required_selection_admission_version": program["required_selection_admission_version"],
        "method_frozen_at": program["method_frozen_at"],
        "method_freeze_recorded_at": program["method_freeze_recorded_at"],
        "as_of": _iso(as_of_dt),
        "system_state": system_state,
        "historical_method_state": historical_method_state,
        "deployment_calibration_state": deployment_calibration_state,
        "report_use_state": (
            "METHOD_RELEASED_FOR_REPORT_USE" if report_release else "NOT_RELEASED_FOR_REPORT_USE"
        ),
        "method_release_id": report_release["release_id"] if report_release else None,
        "method_released_at": report_release["released_at"] if report_release else None,
        "lane_summary": lane_summary,
        "items": items,
        "claim_boundary": (
            "Historical training may change the scoped method; holdout is evaluation-only; "
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
    attach = sub.add_parser("attach-artifact", help="append a freeze, case or selection-review artifact")
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
    release = sub.add_parser(
        "release-for-report-use",
        help="release a frozen method after supported historical holdout evaluation",
    )
    release.add_argument("receipt", type=Path)
    release.add_argument("--recorded-at")
    release.add_argument("--db", type=Path, default=Path("stock_analysis.db"))
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
            elif args.command == "release-for-report-use":
                result = release_method_for_report_use(
                    conn, receipt_ref=args.receipt, recorded_at=args.recorded_at,
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
