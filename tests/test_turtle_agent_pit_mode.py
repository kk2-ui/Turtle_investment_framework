from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase10_acquisition import enumerate_sse_announcements
from scripts.turtle_agent.run import run_full_pipeline


def _manifest(path: Path) -> dict:
    manifest = enumerate_sse_announcements([
        {
            "source_id": "SSE:600340:AR2019:ORIGINAL",
            "source_version": "annual-report-2019-original",
            "source_type": "ANNUAL_REPORT",
            "title": "2019 年年度报告",
            "published_at": "2020-04-25",
            "data_as_of": "2019-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
        },
    ], cutoff_at="2020-04-27T18:00:00+08:00", period_start="2019-01-01")
    for source in manifest["inventory"]:
        source["package_path"] = "annual/2019.txt"
    for source in manifest["sources"]:
        source["package_path"] = "annual/2019.txt"
    manifest["framework_allowlist"] = [{"path": "framework/policy.md"}]
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest


def _package(root: Path) -> None:
    (root / "annual").mkdir(parents=True)
    (root / "framework").mkdir()
    (root / "annual/2019.txt").write_text("历史来源", encoding="utf-8")
    (root / "framework/policy.md").write_text("冻结框架", encoding="utf-8")


def test_run_full_pipeline_pit_preflight_registers_only_pit_tools(tmp_path: Path) -> None:
    package = tmp_path / "package"
    _package(package)
    manifest_path = tmp_path / "manifest.json"
    _manifest(manifest_path)
    output = tmp_path / "new-run"

    attestation_path = run_full_pipeline(
        "600340.SH",
        output_dir=str(output),
        validation_only=True,
        pit_source_manifest=str(manifest_path),
        pit_package_root=str(package),
        pit_case_id="HBTCASE:600340",
        pit_experiment_id="HBT:600340",
        pit_preflight=True,
    )

    attestation = json.loads(Path(attestation_path).read_text(encoding="utf-8"))
    diagnostics = json.loads((output / "_diagnostics.json").read_text(encoding="utf-8"))
    assert attestation["state"] == "REVIEWABLE"
    assert attestation["read_count"] == 0
    assert diagnostics["pit_mode"] is True
    assert diagnostics["tools"] == ["pit_list_sources", "pit_read_framework", "pit_read_source"]


def test_run_full_pipeline_pit_rejects_reused_output(tmp_path: Path) -> None:
    package = tmp_path / "package"
    _package(package)
    manifest_path = tmp_path / "manifest.json"
    _manifest(manifest_path)
    output = tmp_path / "existing"
    output.mkdir()
    (output / "future-settlement.json").write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="新建或空目录"):
        run_full_pipeline(
            "600340.SH",
            output_dir=str(output),
            validation_only=True,
            pit_source_manifest=str(manifest_path),
            pit_package_root=str(package),
            pit_case_id="HBTCASE:600340",
            pit_experiment_id="HBT:600340",
            pit_preflight=True,
        )


def test_run_full_pipeline_pit_rejects_output_inside_input_package(tmp_path: Path) -> None:
    package = tmp_path / "package"
    _package(package)
    manifest_path = tmp_path / "manifest.json"
    _manifest(manifest_path)

    with pytest.raises(RuntimeError, match="source/framework 输入根目录隔离"):
        run_full_pipeline(
            "600340.SH",
            output_dir=str(package / "writer-output"),
            validation_only=True,
            pit_source_manifest=str(manifest_path),
            pit_package_root=str(package),
            pit_case_id="HBTCASE:600340",
            pit_experiment_id="HBT:600340",
            pit_preflight=True,
        )


def test_run_full_pipeline_pit_rejects_untrusted_framework_root(tmp_path: Path) -> None:
    package = tmp_path / "package"
    _package(package)
    manifest_path = tmp_path / "manifest.json"
    _manifest(manifest_path)
    untrusted_framework = tmp_path / "ordinary-output"
    untrusted_framework.mkdir()
    (untrusted_framework / "future-settlement.md").write_text("future outcome", encoding="utf-8")

    with pytest.raises(RuntimeError, match="framework root 必须使用仓库内受控静态目录"):
        run_full_pipeline(
            "600340.SH",
            output_dir=str(tmp_path / "new-output"),
            validation_only=True,
            pit_source_manifest=str(manifest_path),
            pit_package_root=str(package),
            pit_framework_root=str(untrusted_framework),
            pit_case_id="HBTCASE:600340",
            pit_experiment_id="HBT:600340",
            pit_preflight=True,
        )


def test_run_full_pipeline_pit_requires_explicit_mode(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="PIT运行必须二选一"):
        run_full_pipeline(
            "600340.SH",
            output_dir=str(tmp_path / "new-run"),
            validation_only=True,
            pit_source_manifest=str(tmp_path / "manifest.json"),
            pit_package_root=str(tmp_path / "package"),
            pit_case_id="HBTCASE:600340",
            pit_experiment_id="HBT:600340",
        )


@pytest.mark.parametrize("ordinary_mode", [
    {"dry_run": True},
    {"unified": True},
    {"qualitative_only": True},
    {"source_deepening": False},
])
def test_run_full_pipeline_pit_rejects_ordinary_pipeline_modes(
    tmp_path: Path, ordinary_mode: dict[str, object],
) -> None:
    package = tmp_path / "package"
    _package(package)
    manifest_path = tmp_path / "manifest.json"
    _manifest(manifest_path)

    with pytest.raises(RuntimeError, match="PIT运行禁止普通报告"):
        run_full_pipeline(
            "600340.SH",
            output_dir=str(tmp_path / "new-run"),
            validation_only=True,
            pit_source_manifest=str(manifest_path),
            pit_package_root=str(package),
            pit_case_id="HBTCASE:600340",
            pit_experiment_id="HBT:600340",
            pit_preflight=True,
            **ordinary_mode,
        )
