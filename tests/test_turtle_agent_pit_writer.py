from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase10_acquisition import enumerate_sse_announcements
from scripts.phase10_pit_runner import PITSourcePackage
from scripts.turtle_agent.run import run_full_pipeline
from turtle_agent.agent_loop import AgentConfig, TurtleAgent
from turtle_agent.llm_client import LlmResponse, ToolCall
from turtle_agent.tool_registry import ToolRegistry
from turtle_agent.tools.pit_read_tools import clear_pit_runner, configure_pit_runner
from turtle_agent.tools.pit_write_tools import clear_pit_writer, configure_pit_writer


class ScriptedLlm:
    model = "test-pit-writer"

    def __init__(self) -> None:
        self.schemas: list[set[str]] = []
        self.responses = [
            LlmResponse(tool_calls=[ToolCall(id="blocked", name="web_search", arguments={})]),
            LlmResponse(tool_calls=[
                ToolCall(id="sources", name="pit_list_sources", arguments={}),
                ToolCall(id="framework", name="pit_read_framework", arguments={"path": "framework/policy.md"}),
            ]),
            LlmResponse(tool_calls=[
                ToolCall(id="future", name="pit_read_source", arguments={"source_id": "SSE:600340:FUTURE"}),
                ToolCall(id="admitted", name="pit_read_source", arguments={"source_id": "SSE:600340:AR2019"}),
            ]),
            LlmResponse(tool_calls=[ToolCall(
                id="write",
                name="pit_write_report",
                arguments={
                    "source_ids": ["SSE:600340:AR2019"],
                    "section_markers": [
                        "## Point-in-time scope",
                        "## Evidence",
                        "## Business and financial implications",
                        "## Unknowns and monitoring",
                    ],
                    "report_markdown": """# 600340 historical PIT draft

## Point-in-time scope
This is a freeze-date engineering draft and not a settled investment conclusion.

## Evidence
The admitted annual report is the only financial evidence read in this run. [source: SSE:600340:AR2019]

## Business and financial implications
The available material supports only a bounded description of the reported period; it does not establish a return, entry price, or security selection result. [source: SSE:600340:AR2019]

## Unknowns and monitoring
Debt maturity, restricted cash, and later disclosures remain UNKNOWN until separately admitted and read.
""",
                },
            )]),
        ]

    def set_runtime_task(self, task_type: str) -> None:
        assert task_type == "pit_writer"

    def chat(self, messages: list[dict[str, object]], **kwargs: object) -> LlmResponse:
        tools = kwargs.get("tools") or []
        self.schemas.append({item["function"]["name"] for item in tools})
        return self.responses.pop(0)


class EntryPointLlm(ScriptedLlm):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__()


def _runner(tmp_path: Path) -> PITSourcePackage:
    manifest = enumerate_sse_announcements([
        {
            "source_id": "SSE:600340:AR2019",
            "source_version": "annual-report-2019-original",
            "source_type": "ANNUAL_REPORT",
            "title": "2019 年年度报告",
            "published_at": "2020-04-25T18:00:00+08:00",
            "data_as_of": "2019-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
        },
        {
            "source_id": "SSE:600340:FUTURE",
            "source_version": "future-v1",
            "source_type": "EXCHANGE_ANNOUNCEMENT",
            "title": "cutoff 后公告",
            "published_at": "2020-04-28T09:00:00+08:00",
            "data_as_of": "2020-04-28",
            "revision_policy": "ORIGINAL_VINTAGE",
        },
    ], cutoff_at="2020-04-27T18:00:00+08:00", period_start="2019-01-01")
    package = tmp_path / "package"
    (package / "annual").mkdir(parents=True)
    (package / "annual/2019.txt").write_text("2019 historical annual report", encoding="utf-8")
    for source in manifest["inventory"]:
        if source["source_id"] == "SSE:600340:AR2019":
            source["package_path"] = "annual/2019.txt"
    for source in manifest["sources"]:
        source["package_path"] = "annual/2019.txt"
    manifest["framework_allowlist"] = [{"path": "framework/policy.md"}]
    return PITSourcePackage(
        manifest,
        package,
        case_id="HBTCASE:600340",
        experiment_id="HBT:600340",
        run_id="pit-writer-test",
    )


def test_pit_writer_uses_only_admitted_reads_and_single_restricted_output(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    assert runner.state == "REVIEWABLE"
    output = tmp_path / "fresh-output"
    tools = ToolRegistry()
    configure_pit_runner(runner)
    configure_pit_writer(
        runner,
        output_dir=output,
        case_id="HBTCASE:600340",
        experiment_id="HBT:600340",
    )
    try:
        tools.auto_discover("turtle_agent.tools.pit_read_tools")
        tools.auto_discover("turtle_agent.tools.pit_write_tools")
        llm = ScriptedLlm()
        report_path = TurtleAgent(
            llm=llm,
            tools=tools,
            config=AgentConfig(
                code="600340.SH",
                output_dir=str(output),
                max_iterations=6,
                pit_mode=True,
                pit_case_id="HBTCASE:600340",
                pit_experiment_id="HBT:600340",
                pit_cutoff_at="2020-04-27T18:00:00+08:00",
            ),
        ).analyze()
    finally:
        clear_pit_writer()
        clear_pit_runner()

    assert Path(report_path).name == "pit_writer_report.md"
    assert Path(report_path).is_file()
    assert sorted(path.name for path in output.iterdir()) == ["pit_writer_report.md"]
    assert all(schema == {
        "pit_list_sources", "pit_read_source", "pit_read_framework", "pit_write_report",
    } for schema in llm.schemas)
    audit = runner.attestation()["read_audit"]
    assert any(
        event["decision"] == "DENY"
        and event.get("reason") == "source_not_allowlisted:SSE:600340:FUTURE"
        for event in audit
    )
    assert [event["source_id"] for event in audit if event["kind"] == "SOURCE" and event["allowed"]] == [
        "SSE:600340:AR2019",
    ]


def test_pit_agent_rejects_an_ordinary_tool_registry(tmp_path: Path) -> None:
    tools = ToolRegistry()
    tools.register("web_search", lambda: {"ok": True})

    with pytest.raises(RuntimeError, match="必须只注册受限读取和写入工具"):
        TurtleAgent(
            llm=None,
            tools=tools,
            config=AgentConfig(
                code="600340.SH",
                pit_mode=True,
                pit_case_id="HBTCASE:600340",
                pit_experiment_id="HBT:600340",
                pit_cutoff_at="2020-04-27T18:00:00+08:00",
            ),
        ).analyze()


def test_pit_writer_entrypoint_bypasses_the_normal_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner(tmp_path)
    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(json.dumps(runner.manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("turtle_agent.llm_client.LlmClient", EntryPointLlm)
    output = tmp_path / "fresh-output"

    report_path = run_full_pipeline(
        "600340.SH",
        output_dir=str(output),
        validation_only=True,
        pit_source_manifest=str(manifest_path),
        pit_package_root=str(runner.package_root),
        pit_case_id="HBTCASE:600340",
        pit_experiment_id="HBT:600340",
        pit_writer=True,
    )

    assert Path(report_path).name == "pit_writer_report.md"
    assert sorted(path.name for path in output.iterdir()) == [
        "_diagnostics.json",
        "pit_runner_attestation.json",
        "pit_writer_report.md",
    ]
    attestation = json.loads((output / "pit_runner_attestation.json").read_text(encoding="utf-8"))
    assert attestation["execution_mode"] == "PIT_WRITER"
    assert attestation["writer"]["status"] == "PASS"
    assert attestation["framework_root_class"] == "REPOSITORY_STATIC"
    assert attestation["framework_root"].endswith("config/phase10_pit_framework")
