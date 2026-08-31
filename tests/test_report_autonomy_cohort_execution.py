from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.report_autonomy_appliance_cohort_prereg_generator import (
    build_appliance_cohort_preregistration,
)
from scripts.report_autonomy_cohort_execution import (
    MATERIALIZATION_STATE,
    finalize_fresh_cell,
    materialize_fresh_tasks,
)
from scripts.report_autonomy_multicompany_prereg import (
    validate_multicompany_preregistration,
)
from tests.test_enterprise_underwriting_episode import _episode_with_derivation


_ROOT = Path(__file__).resolve().parents[1]
_INPUT = _ROOT / "tests/fixtures/report_autonomy_appliance_cohort_prereg_input.json"


def _isolated_preregistration(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    preregistration = build_appliance_cohort_preregistration(
        json.loads(_INPUT.read_text(encoding="utf-8"))
    )
    for index, cell in enumerate(preregistration["execution"]["cells"], start=1):
        root = tmp_path / "execution" / f"cell_{index:02d}"
        cell["artifact_paths"] = {
            "contract_ref": str(root / "training_contract.json"),
            "rendered_task_ref": str(root / "fresh_task.json"),
            "raw_response_ref": str(root / "raw_response.json"),
            "episode_ref": str(root / "enterprise_underwriting_episode.json"),
            "reader_bridge_ref": str(root / "reader_bridge.json"),
            "first_reader_report_ref": str(root / "first_reader_report.md"),
            "freeze_receipt_ref": str(root / "freeze_receipt.json"),
        }
    path = tmp_path / "preregistration.json"
    path.write_text(json.dumps(preregistration, ensure_ascii=False), encoding="utf-8")
    return path, preregistration


def test_materializer_writes_only_exact_frozen_contracts_and_tasks_once(tmp_path: Path) -> None:
    preregistration_path, preregistration = _isolated_preregistration(tmp_path)

    receipt = materialize_fresh_tasks(preregistration_path)

    assert receipt["state"] == MATERIALIZATION_STATE
    assert receipt["cell_count"] == 32
    for cell in preregistration["execution"]["cells"]:
        artifacts = cell["artifact_paths"]
        assert json.loads(Path(artifacts["contract_ref"]).read_text(encoding="utf-8")) == cell[
            "training_contract"
        ]
        assert json.loads(Path(artifacts["rendered_task_ref"]).read_text(encoding="utf-8")) == cell[
            "rendered_task"
        ]

    with pytest.raises(ValueError, match="materialization_refuses_existing_artifact"):
        materialize_fresh_tasks(preregistration_path)


def test_invalid_episode_attempt_is_frozen_and_cannot_be_retried(tmp_path: Path) -> None:
    preregistration_path, preregistration = _isolated_preregistration(tmp_path)
    materialize_fresh_tasks(preregistration_path)
    cell = preregistration["execution"]["cells"][0]
    raw_response = Path(cell["artifact_paths"]["raw_response_ref"])
    raw_response.parent.mkdir(parents=True, exist_ok=True)
    raw_response.write_text("not-a-json-object", encoding="utf-8")

    receipt = finalize_fresh_cell(
        preregistration_path, case_id=cell["case_id"], arm_id=cell["arm_id"],
    )

    assert receipt["state"] == "EPISODE_INVALID"
    updated = json.loads(preregistration_path.read_text(encoding="utf-8"))
    updated_cell = updated["execution"]["cells"][0]
    assert updated_cell["state"] == "EPISODE_INVALID"
    assert updated_cell["attempts"] == {"episode": 1, "reader_report": 0}
    assert Path(updated_cell["artifact_paths"]["freeze_receipt_ref"]).is_file()
    assert validate_multicompany_preregistration(updated)["state"] == "REVIEWABLE"

    with pytest.raises(ValueError, match="cell_not_unstarted_no_retry"):
        finalize_fresh_cell(
            preregistration_path, case_id=cell["case_id"], arm_id=cell["arm_id"],
        )


def test_materializer_rejects_cross_cell_artifact_path_collisions(tmp_path: Path) -> None:
    preregistration_path, preregistration = _isolated_preregistration(tmp_path)
    first, second = preregistration["execution"]["cells"][0:2]
    first_contract = Path(first["artifact_paths"]["contract_ref"])
    second["artifact_paths"]["rendered_task_ref"] = str(
        first_contract.parent / "path-alias" / ".." / first_contract.name
    )
    preregistration_path.write_text(
        json.dumps(preregistration, ensure_ascii=False), encoding="utf-8",
    )

    with pytest.raises(ValueError, match="artifact_path_collision"):
        materialize_fresh_tasks(preregistration_path)


def test_materializer_rejects_episode_path_not_emitted_by_native_runner(tmp_path: Path) -> None:
    preregistration_path, preregistration = _isolated_preregistration(tmp_path)
    preregistration["execution"]["cells"][0]["artifact_paths"]["episode_ref"] = str(
        tmp_path / "execution" / "wrong-episode-name.json"
    )
    preregistration_path.write_text(
        json.dumps(preregistration, ensure_ascii=False), encoding="utf-8",
    )

    with pytest.raises(ValueError, match="episode_ref_must_match_native_runner_output"):
        materialize_fresh_tasks(preregistration_path)


def test_finalizer_refuses_a_preexisting_native_downstream_bundle(tmp_path: Path) -> None:
    preregistration_path, preregistration = _isolated_preregistration(tmp_path)
    materialize_fresh_tasks(preregistration_path)
    cell = preregistration["execution"]["cells"][0]
    artifacts = cell["artifact_paths"]
    raw_response = Path(artifacts["raw_response_ref"])
    raw_response.parent.mkdir(parents=True, exist_ok=True)
    raw_response.write_text("{}", encoding="utf-8")
    native_bundle = Path(artifacts["episode_ref"]).parent / (
        "enterprise_underwriting_downstream_bundle.json"
    )
    native_bundle.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="finalization_refuses_existing_output"):
        finalize_fresh_cell(
            preregistration_path, case_id=cell["case_id"], arm_id=cell["arm_id"],
        )
    unchanged = json.loads(preregistration_path.read_text(encoding="utf-8"))
    assert unchanged["execution"]["cells"][0]["state"] == "NOT_STARTED"


def test_reader_failure_is_terminal_paired_test_invalid_and_keeps_prereg_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    preregistration_path, preregistration = _isolated_preregistration(tmp_path)
    materialize_fresh_tasks(preregistration_path)
    cell = preregistration["execution"]["cells"][0]
    raw_response = Path(cell["artifact_paths"]["raw_response_ref"])
    raw_response.parent.mkdir(parents=True, exist_ok=True)
    raw_response.write_text("{}", encoding="utf-8")
    episode = _episode_with_derivation()

    def successful_fresh_response(
        contract: object, *, agent_response: object, output_dir: str | Path,
    ) -> dict[str, object]:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / "enterprise_underwriting_episode.json").write_text(
            json.dumps(deepcopy(episode), ensure_ascii=False), encoding="utf-8",
        )
        return {"state": "TRAINING_EPISODE_COMPLETED"}

    monkeypatch.setattr(
        "scripts.report_autonomy_cohort_execution.run_fresh_subagent_response",
        successful_fresh_response,
    )
    monkeypatch.setattr(
        "scripts.report_autonomy_cohort_execution.compile_component_reader_bridge",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("reader bridge failure")),
    )

    receipt = finalize_fresh_cell(
        preregistration_path, case_id=cell["case_id"], arm_id=cell["arm_id"],
    )

    assert receipt["state"] == "PAIRED_TEST_INVALID"
    updated = json.loads(preregistration_path.read_text(encoding="utf-8"))
    assert updated["execution"]["cells"][0]["state"] == "PAIRED_TEST_INVALID"
    assert updated["execution"]["cells"][0]["attempts"] == {
        "episode": 1, "reader_report": 1,
    }
    assert validate_multicompany_preregistration(updated)["state"] == "REVIEWABLE"


def test_validated_episode_gets_exact_component_bridge_and_reader_readout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    preregistration_path, preregistration = _isolated_preregistration(tmp_path)
    materialize_fresh_tasks(preregistration_path)
    cell = preregistration["execution"]["cells"][0]
    raw_response = Path(cell["artifact_paths"]["raw_response_ref"])
    raw_response.parent.mkdir(parents=True, exist_ok=True)
    raw_response.write_text("{}", encoding="utf-8")
    episode = _episode_with_derivation()

    def successful_fresh_response(
        contract: object, *, agent_response: object, output_dir: str | Path,
    ) -> dict[str, object]:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / "enterprise_underwriting_episode.json").write_text(
            json.dumps(deepcopy(episode), ensure_ascii=False), encoding="utf-8",
        )
        return {
            "state": "TRAINING_EPISODE_COMPLETED",
            "contract_id": (contract if isinstance(contract, dict) else {}).get("contract_id"),
            "execution_mode": "CODEX_FRESH_SUBAGENT",
        }

    monkeypatch.setattr(
        "scripts.report_autonomy_cohort_execution.run_fresh_subagent_response",
        successful_fresh_response,
    )

    receipt = finalize_fresh_cell(
        preregistration_path, case_id=cell["case_id"], arm_id=cell["arm_id"],
    )

    assert receipt["state"] == "FROZEN"
    artifacts = cell["artifact_paths"]
    bridge = json.loads(Path(artifacts["reader_bridge_ref"]).read_text(encoding="utf-8"))
    report = Path(artifacts["first_reader_report_ref"]).read_text(encoding="utf-8")
    assert bridge["episode_ref"] == artifacts["episode_ref"]
    assert "正常盈利组件桥" in report
    updated = json.loads(preregistration_path.read_text(encoding="utf-8"))
    assert updated["execution"]["cells"][0]["state"] == "FROZEN"
    assert validate_multicompany_preregistration(updated)["state"] == "REVIEWABLE"
