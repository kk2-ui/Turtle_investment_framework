from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.turtle_agent import run as run_module
from turtle_agent.agent_loop import AgentConfig, TurtleAgent
from turtle_agent.llm_client import LlmResponse, ToolCall
from turtle_agent.tool_registry import ToolRegistry


class ProductionLlm:
    model = "test-pit-production"

    def __init__(self) -> None:
        self.task_type = ""
        self.schemas: list[set[str]] = []
        self.responses = [LlmResponse(tool_calls=[ToolCall(
            id="assemble", name="pit_assemble_report", arguments={"company_name": "Test issuer"},
        )])]

    def set_runtime_task(self, task_type: str) -> None:
        self.task_type = task_type

    def chat(self, messages: list[dict[str, object]], **kwargs: object) -> LlmResponse:
        self.schemas.append({item["function"]["name"] for item in kwargs["tools"]})
        return self.responses.pop(0)


def test_pit_production_agent_uses_only_bound_tools_and_ends_at_assembly() -> None:
    tools = ToolRegistry()
    allowed = TurtleAgent._pit_production_allowed_tools()
    for name in sorted(allowed):
        if name == "pit_assemble_report":
            tools.register(name, lambda company_name="": {"path": "output/pit-report.md"})
        else:
            tools.register(name, lambda: {"ok": True})
    llm = ProductionLlm()

    report_path = TurtleAgent(
        llm=llm,
        tools=tools,
        config=AgentConfig(
            code="600340.SH",
            pit_production_mode=True,
            pit_case_id="HBTCASE:600340:20200427",
            pit_experiment_id="HBT:600340:20200427",
            pit_cutoff_at="2020-04-27T18:00:00+08:00",
        ),
    ).analyze()

    assert report_path == "output/pit-report.md"
    assert llm.task_type == "pit_production_freeze"
    assert llm.schemas == [allowed]


def test_pit_production_registry_discovers_exactly_the_bound_toolset() -> None:
    tools = ToolRegistry()
    tools.auto_discover("turtle_agent.tools.pit_read_tools")
    tools.auto_discover("turtle_agent.tools.pit_production_write_tools")

    assert set(tools.list_tools()) == TurtleAgent._pit_production_allowed_tools()


PIT_ARGS = {
    "pit_source_manifest": "source-manifest.json",
    "pit_package_root": "source-package",
    "pit_case_id": "HBTCASE:600340:20200427",
    "pit_experiment_id": "HBT:600340:20200427",
    "pit_production_freeze": True,
}


@pytest.mark.parametrize(
    "blocked_kwargs",
    [
        {"validation_only": True},
        {"dry_run": True},
        {"unified": True},
        {"qualitative_only": True},
        {"data_source": "600340.SH"},
        {"price_source": "600340.SH"},
        {"source_deepening": False},
    ],
)
def test_pit_production_freeze_rejects_validation_and_ordinary_modes(
    tmp_path: Path, blocked_kwargs: dict[str, object],
) -> None:
    with pytest.raises(RuntimeError, match="PIT运行禁止普通报告"):
        run_module.run_full_pipeline(
            "600340.SH",
            output_dir=str(tmp_path / "output"),
            **PIT_ARGS,
            **blocked_kwargs,
        )


@pytest.mark.parametrize(
    ("acceptance_status", "should_publish"),
    [
        ("READY_FOR_BLIND_REVIEW", True),
        ("REVISION_REQUIRED", False),
    ],
)
def test_pit_production_freeze_uses_one_run_id_and_only_publishes_after_ready_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, acceptance_status: str, should_publish: bool,
) -> None:
    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(json.dumps({"company_code": "600340.SH"}), encoding="utf-8")
    package_root = tmp_path / "source-package"
    package_root.mkdir()
    output = tmp_path / "output"
    observed: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, manifest: dict, package: str, **kwargs: object) -> None:
            observed["runner_manifest"] = manifest
            observed["runner_package"] = package
            observed["runner_kwargs"] = kwargs
            self.state = "REVIEWABLE"
            self.invalid_findings: list[str] = []
            self.incomplete_findings: list[str] = []
            self.run_id = str(kwargs["run_id"])
            self.cutoff_at = "2020-04-27T18:00:00+08:00"

    class FakeRuntimeManifest:
        def __init__(self, path: Path) -> None:
            self.path = path
            self.artifacts: list[tuple[str, str]] = []
            self.finalized: tuple[str, dict] | None = None

        def add_artifact(self, path: str, kind: str) -> None:
            self.artifacts.append((path, kind))

        def record_step(self, *args: object, **kwargs: object) -> None:
            return None

        def add_error(self, *args: object, **kwargs: object) -> None:
            return None

        def finalize(self, status: str, *, publication: dict) -> None:
            self.finalized = (status, publication)

    class FakeRuntime:
        def __init__(self, **kwargs: object) -> None:
            observed["runtime_kwargs"] = kwargs
            self.manifest = FakeRuntimeManifest(Path(str(kwargs["output_dir"])) / "run_manifest.json")
            observed["runtime"] = self

    def fake_production_freeze(**kwargs: object) -> str:
        observed["production_kwargs"] = kwargs
        report_path = Path(str(kwargs["output_dir"])) / "report.md"
        report_path.write_text("# PIT production report\n", encoding="utf-8")
        return str(report_path)

    def unexpected_normal_phase(*args: object, **kwargs: object) -> dict:
        raise AssertionError("normal report phase must not execute in PIT production mode")

    import scripts.phase10_pit_runner as pit_runner_module
    import scripts.real_report_acceptance as real_report_acceptance
    import scripts.runtime_governance as runtime_governance

    monkeypatch.setattr(pit_runner_module, "PITSourcePackage", FakeRunner)
    monkeypatch.setattr(runtime_governance, "RuntimeController", FakeRuntime)
    monkeypatch.setattr(run_module, "_run_pit_production_freeze", fake_production_freeze)
    monkeypatch.setattr(
        run_module,
        "_validate_pit_production_completion",
        lambda **kwargs: {
            "completion_status": "COMPLETE",
            "report_path": str(kwargs["report_path"]),
            "publication_snapshot_path": str(Path(str(kwargs["output_dir"])) / "publication_snapshot.json"),
            "pit_attestation_path": str(Path(str(kwargs["output_dir"])) / "pit_runner_attestation.json"),
        },
    )
    monkeypatch.setattr(
        real_report_acceptance,
        "evaluate_phase10_production_freeze_acceptance",
        lambda **kwargs: {"samples": [{"machine_status": acceptance_status}]},
    )
    monkeypatch.setattr(run_module, "_run_phase", unexpected_normal_phase)

    if should_publish:
        report_path = run_module.run_full_pipeline(
            "600340.SH",
            output_dir=str(output),
            pit_source_manifest=str(manifest_path),
            pit_package_root=str(package_root),
            pit_case_id="HBTCASE:600340:20200427",
            pit_experiment_id="HBT:600340:20200427",
            pit_production_freeze=True,
        )
    else:
        with pytest.raises(RuntimeError, match="not ready at the independent Phase 10 acceptance gate"):
            run_module.run_full_pipeline(
                "600340.SH",
                output_dir=str(output),
                pit_source_manifest=str(manifest_path),
                pit_package_root=str(package_root),
                pit_case_id="HBTCASE:600340:20200427",
                pit_experiment_id="HBT:600340:20200427",
                pit_production_freeze=True,
            )
        report_path = str(output / "report.md")

    runner_kwargs = observed["runner_kwargs"]
    runtime_kwargs = observed["runtime_kwargs"]
    production_kwargs = observed["production_kwargs"]
    assert isinstance(runner_kwargs, dict)
    assert isinstance(runtime_kwargs, dict)
    assert isinstance(production_kwargs, dict)
    run_id = runner_kwargs["run_id"]
    assert run_id == runtime_kwargs["run_id"]
    assert production_kwargs["pit_runner"].run_id == run_id
    assert production_kwargs["runtime"] is observed["runtime"]
    assert report_path == str(output / "report.md")
    runtime = observed["runtime"]
    assert isinstance(runtime, FakeRuntime)
    assert runtime.manifest.artifacts[0] == (report_path, "pit_production_report")
    assert runtime.manifest.finalized == (
        ("COMPLETED", {"status": "PUBLISHED", "validation_only": False})
        if should_publish else ("BLOCKED", {"status": "NOT_PUBLISHED", "validation_only": False})
    )
