#!/usr/bin/env python3
"""Materialize and bind one frozen report-autonomy cohort cell.

This runner is deliberately a narrow local control plane.  It never selects a
company, changes a contract, calls a model provider, reads an outcome, or
scores an arm.  A fresh Codex sub-agent writes exactly one raw Episode response
at the predeclared path.  The runner then either freezes the validated Episode,
its exact component reader bridge, and its deterministic reader readout, or
freezes an invalid-attempt receipt.  Neither state is retryable.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.enterprise_underwriting_episode import render_underwriting_readout
    from scripts.enterprise_underwriting_training import run_fresh_subagent_response
    from scripts.report_autonomy_bridge import compile_component_reader_bridge
    from scripts.report_autonomy_multicompany_prereg import (
        ARMS,
        validate_multicompany_preregistration,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.enterprise_underwriting_episode import render_underwriting_readout
    from scripts.enterprise_underwriting_training import run_fresh_subagent_response
    from scripts.report_autonomy_bridge import compile_component_reader_bridge
    from scripts.report_autonomy_multicompany_prereg import (
        ARMS,
        validate_multicompany_preregistration,
    )


SCHEMA_VERSION = "report-autonomy-cohort-execution-receipt.v1"
MATERIALIZATION_STATE = "FRESH_TASKS_MATERIALIZED"
_ROOT = Path(__file__).resolve().parents[1]
_RUNTIME_ARTIFACT_FIELDS = (
    "raw_response_ref",
    "episode_ref",
    "reader_bridge_ref",
    "first_reader_report_ref",
    "freeze_receipt_ref",
)
_NATIVE_EPISODE_FILENAME = "enterprise_underwriting_episode.json"
_NATIVE_BUNDLE_FILENAME = "enterprise_underwriting_downstream_bundle.json"


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("json_object_required:" + str(path))
    return value


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _path(ref: Any) -> Path:
    value = Path(_text(ref)).expanduser()
    candidate = value if value.is_absolute() else _ROOT / value
    return Path(os.path.normpath(str(candidate)))


def _validated_preregistration(path: Path) -> dict[str, Any]:
    preregistration = _read_json(path)
    validation = validate_multicompany_preregistration(preregistration)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("preregistration_invalid:" + ",".join(validation["findings"]))
    return preregistration


def _cell(preregistration: dict[str, Any], *, case_id: str, arm_id: str) -> dict[str, Any]:
    if arm_id not in ARMS:
        raise ValueError("arm_id_invalid:" + arm_id)
    matches = [
        _mapping(item)
        for item in _items(_mapping(preregistration.get("execution")).get("cells"))
        if _mapping(item).get("case_id") == case_id
        and _mapping(item).get("arm_id") == arm_id
    ]
    if len(matches) != 1:
        raise ValueError("cell_not_registered:" + case_id + ":" + arm_id)
    return matches[0]


def _assert_absent(paths: list[Path], *, reason: str) -> None:
    present = [str(path) for path in paths if path.exists()]
    if present:
        raise ValueError(reason + ":" + ",".join(present))


def _assert_artifact_paths_unique(cells: list[Any]) -> None:
    """Keep cells isolated before any deterministic write occurs.

    The public preregistration validates that each cell has every path, but it
    intentionally does not assign filesystem semantics.  The execution plane
    must additionally reject a malformed register where two cells would use
    the same on-disk artifact or where a declared path collides with the
    native runner's fixed downstream bundle.
    """

    seen: dict[Path, str] = {}
    for index, raw_cell in enumerate(cells):
        cell = _mapping(raw_cell)
        identity = str(cell.get("case_id")) + ":" + str(cell.get("arm_id"))
        artifacts = _mapping(cell.get("artifact_paths"))
        declared = {
            field: _path(artifacts.get(field))
            for field in (
                "contract_ref", "rendered_task_ref", * _RUNTIME_ARTIFACT_FIELDS,
            )
        }
        if declared["episode_ref"].name != _NATIVE_EPISODE_FILENAME:
            raise ValueError(
                "episode_ref_must_match_native_runner_output:"
                + str(declared["episode_ref"])
            )
        declared["native_downstream_bundle"] = (
            declared["episode_ref"].parent
            / _NATIVE_BUNDLE_FILENAME
        )
        for role, artifact_path in declared.items():
            previous = seen.get(artifact_path)
            if previous is not None:
                raise ValueError(
                    "artifact_path_collision:"
                    + str(artifact_path)
                    + ":"
                    + previous
                    + ":"
                    + identity
                    + ":"
                    + role
                )
            seen[artifact_path] = identity + ":" + role


def materialize_fresh_tasks(preregistration_path: str | Path) -> dict[str, Any]:
    """Write only the pre-frozen contracts and their exact task packets once."""

    path = Path(preregistration_path).expanduser().resolve()
    preregistration = _validated_preregistration(path)
    cells = _items(_mapping(preregistration.get("execution")).get("cells"))
    _assert_artifact_paths_unique(cells)
    to_write: list[tuple[Path, dict[str, Any]]] = []
    for raw_cell in cells:
        cell = _mapping(raw_cell)
        if cell.get("state") != "NOT_STARTED" or cell.get("attempts") != {
            "episode": 0, "reader_report": 0,
        }:
            raise ValueError("materialization_requires_unstarted_cells")
        artifacts = _mapping(cell.get("artifact_paths"))
        contract_path = _path(artifacts.get("contract_ref"))
        task_path = _path(artifacts.get("rendered_task_ref"))
        _assert_absent(
            [contract_path, task_path] + [
                _path(artifacts.get(field)) for field in _RUNTIME_ARTIFACT_FIELDS
            ],
            reason="materialization_refuses_existing_artifact",
        )
        to_write.extend([
            (contract_path, deepcopy(_mapping(cell.get("training_contract")))),
            (task_path, deepcopy(_mapping(cell.get("rendered_task")))),
        ])
    for output, payload in to_write:
        _atomic_json(output, payload)
    return {
        "schema_version": SCHEMA_VERSION,
        "state": MATERIALIZATION_STATE,
        "preregistration_id": preregistration.get("preregistration_id"),
        "cell_count": len(cells),
        "authority": "PREOUTCOME_TASK_MATERIALIZATION_ONLY",
    }


def _write_preregistration(path: Path, preregistration: dict[str, Any]) -> None:
    validation = validate_multicompany_preregistration(preregistration)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("updated_preregistration_invalid:" + ",".join(validation["findings"]))
    _atomic_json(path, preregistration)


def finalize_fresh_cell(
    preregistration_path: str | Path, *, case_id: str, arm_id: str,
) -> dict[str, Any]:
    """Bind one fresh response once; freeze success or invalidity with no retry."""

    path = Path(preregistration_path).expanduser().resolve()
    preregistration = _validated_preregistration(path)
    _assert_artifact_paths_unique(
        _items(_mapping(preregistration.get("execution")).get("cells"))
    )
    cell = _cell(preregistration, case_id=case_id, arm_id=arm_id)
    if cell.get("state") != "NOT_STARTED" or cell.get("attempts") != {
        "episode": 0, "reader_report": 0,
    }:
        raise ValueError("cell_not_unstarted_no_retry:" + case_id + ":" + arm_id)
    artifacts = _mapping(cell.get("artifact_paths"))
    contract_path = _path(artifacts.get("contract_ref"))
    task_path = _path(artifacts.get("rendered_task_ref"))
    raw_response_path = _path(artifacts.get("raw_response_ref"))
    episode_path = _path(artifacts.get("episode_ref"))
    downstream_bundle_path = episode_path.parent / _NATIVE_BUNDLE_FILENAME
    bridge_path = _path(artifacts.get("reader_bridge_ref"))
    report_path = _path(artifacts.get("first_reader_report_ref"))
    receipt_path = _path(artifacts.get("freeze_receipt_ref"))
    if not raw_response_path.is_file():
        raise ValueError("raw_response_missing:" + str(raw_response_path))
    if not contract_path.is_file() or _read_json(contract_path) != cell.get("training_contract"):
        raise ValueError("materialized_contract_missing_or_not_exact")
    if not task_path.is_file() or _read_json(task_path) != cell.get("rendered_task"):
        raise ValueError("materialized_task_missing_or_not_exact")
    _assert_absent(
        [episode_path, downstream_bundle_path, bridge_path, report_path, receipt_path],
        reason="finalization_refuses_existing_output",
    )

    try:
        raw_response = _read_json(raw_response_path)
        run_receipt = run_fresh_subagent_response(
            cell.get("training_contract"),
            agent_response=raw_response,
            output_dir=episode_path.parent,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        cell["state"] = "EPISODE_INVALID"
        cell["attempts"] = {"episode": 1, "reader_report": 0}
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "state": "EPISODE_INVALID",
            "case_id": case_id,
            "arm_id": arm_id,
            "attempts": deepcopy(cell["attempts"]),
            "failure": str(exc),
            "retry_policy": "NO_RETRY_OR_REWRITE",
            "authority": "PREOUTCOME_EXECUTION_CONTROL_PLANE_ONLY",
        }
        _atomic_json(receipt_path, receipt)
        _write_preregistration(path, preregistration)
        return receipt

    if not episode_path.is_file():  # The underlying runner names this artifact.
        raise ValueError("episode_runner_did_not_write_expected_artifact")
    try:
        episode = _read_json(episode_path)
        bridge = compile_component_reader_bridge(
            episode, episode_ref=str(artifacts.get("episode_ref")),
        )
        _atomic_json(bridge_path, bridge)
        _atomic_text(report_path, render_underwriting_readout(episode))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        cell["state"] = "PAIRED_TEST_INVALID"
        cell["attempts"] = {"episode": 1, "reader_report": 1}
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "state": "PAIRED_TEST_INVALID",
            "case_id": case_id,
            "arm_id": arm_id,
            "attempts": deepcopy(cell["attempts"]),
            "episode_run_receipt": run_receipt,
            "failure": str(exc),
            "retry_policy": "NO_RETRY_OR_REWRITE",
            "authority": "PREOUTCOME_EXECUTION_CONTROL_PLANE_ONLY",
        }
        _atomic_json(receipt_path, receipt)
        _write_preregistration(path, preregistration)
        return receipt

    cell["state"] = "FROZEN"
    cell["attempts"] = {"episode": 1, "reader_report": 1}
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "state": "FROZEN",
        "case_id": case_id,
        "arm_id": arm_id,
        "attempts": deepcopy(cell["attempts"]),
        "episode_run_receipt": run_receipt,
        "reader_artifacts": {
            "episode_ref": artifacts.get("episode_ref"),
            "reader_bridge_ref": artifacts.get("reader_bridge_ref"),
            "first_reader_report_ref": artifacts.get("first_reader_report_ref"),
        },
        "retry_policy": "NO_RETRY_OR_REWRITE",
        "authority": "PREOUTCOME_EXECUTION_CONTROL_PLANE_ONLY",
    }
    _atomic_json(receipt_path, receipt)
    _write_preregistration(path, preregistration)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    materialize = sub.add_parser("materialize")
    materialize.add_argument("preregistration", type=Path)
    finalize = sub.add_parser("finalize")
    finalize.add_argument("preregistration", type=Path)
    finalize.add_argument("case_id")
    finalize.add_argument("arm_id", choices=ARMS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "materialize":
            result = materialize_fresh_tasks(args.preregistration)
        else:
            result = finalize_fresh_cell(
                args.preregistration, case_id=args.case_id, arm_id=args.arm_id,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": SCHEMA_VERSION, "state": "INVALID", "findings": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("state") in {MATERIALIZATION_STATE, "FROZEN", "EPISODE_INVALID", "PAIRED_TEST_INVALID"} else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
