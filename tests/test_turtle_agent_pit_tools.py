from __future__ import annotations

from pathlib import Path

import pytest

from scripts.phase10_acquisition import enumerate_sse_announcements
from scripts.phase10_pit_runner import PITSourcePackage
from turtle_agent.tool_registry import ToolRegistry
from turtle_agent.tools import pit_read_tools


def _manifest() -> dict:
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
        {
            "source_id": "SSE:600340:ANN:FUTURE",
            "source_version": "future-v1",
            "source_type": "EXCHANGE_ANNOUNCEMENT",
            "title": "cutoff 后公告",
            "published_at": "2020-04-28",
            "data_as_of": "2020-04-28",
            "revision_policy": "ORIGINAL_VINTAGE",
        },
    ], cutoff_at="2020-04-27T18:00:00+08:00", period_start="2019-01-01")
    for source in manifest["inventory"]:
        if source["source_id"] == "SSE:600340:AR2019:ORIGINAL":
            source["package_path"] = "annual/2019.txt"
    for source in manifest["sources"]:
        source["package_path"] = "annual/2019.txt"
    manifest["framework_allowlist"] = [{"path": "framework/policy.md"}]
    return manifest


@pytest.fixture()
def configured_runner(tmp_path: Path) -> PITSourcePackage:
    package = tmp_path / "package"
    (package / "annual").mkdir(parents=True)
    (package / "framework").mkdir()
    (package / "annual/2019.txt").write_text("历史时点经营事实\n第二行", encoding="utf-8")
    (package / "framework/policy.md").write_text("冻结运行框架", encoding="utf-8")
    runner = PITSourcePackage(_manifest(), package, case_id="HBTCASE:TEST", experiment_id="HBT:TEST", run_id="run-test")
    assert runner.state == "REVIEWABLE"
    pit_read_tools.configure_pit_runner(runner)
    try:
        yield runner
    finally:
        pit_read_tools.clear_pit_runner()


def test_pit_tools_are_discoverable_and_read_only(configured_runner: PITSourcePackage) -> None:
    registry = ToolRegistry()
    assert registry.auto_discover("turtle_agent.tools.pit_read_tools") == 3
    assert registry.list_tools() == ["pit_list_sources", "pit_read_framework", "pit_read_source"]

    listed = registry.execute("pit_list_sources", {})
    assert listed["ok"] is True
    assert listed["value"]["sources"][0]["source_id"] == "SSE:600340:AR2019:ORIGINAL"

    source = registry.execute("pit_read_source", {"source_id": "SSE:600340:AR2019:ORIGINAL"})
    assert source["ok"] is True
    assert source["value"]["content"].startswith("历史时点经营事实")
    assert source["value"]["source_version"] == "annual-report-2019-original"

    framework = registry.execute("pit_read_framework", {"path": "framework/policy.md"})
    assert framework["ok"] is True
    assert framework["value"]["content"] == "冻结运行框架"

    allowed = [event for event in configured_runner.attestation()["read_audit"] if event["allowed"]]
    assert [event["kind"] for event in allowed] == ["SOURCE", "FRAMEWORK"]
    assert allowed[0]["source_id"] == "SSE:600340:AR2019:ORIGINAL"
    assert allowed[0]["data_as_of"] == "2019-12-31"


def test_pit_tools_reject_future_unknown_and_arbitrary_paths(configured_runner: PITSourcePackage) -> None:
    registry = ToolRegistry()

    registry.auto_discover("turtle_agent.tools.pit_read_tools")
    unknown = registry.execute("pit_read_source", {"source_id": "SSE:600340:ANN:FUTURE"})
    assert unknown["ok"] is True
    assert unknown["value"]["ok"] is False
    assert "source_not_allowlisted" in unknown["value"]["error"]

    arbitrary = registry.execute("pit_read_framework", {"path": "../future/settlement.json"})
    assert arbitrary["ok"] is True
    assert arbitrary["value"]["ok"] is False
    assert "framework_not_allowlisted" in arbitrary["value"]["error"]

    denied = [event for event in configured_runner.attestation()["read_audit"] if not event["allowed"]]
    assert len(denied) == 2
    assert all(event["decision"] == "DENY" for event in denied)
    assert all(event["cutoff_at"] == "2020-04-27T18:00:00+08:00" for event in denied)


def test_pit_tools_do_not_read_until_runner_is_explicitly_bound() -> None:
    pit_read_tools.clear_pit_runner()
    assert pit_read_tools.pit_list_sources() == {"ok": False, "error": "pit_runner_not_configured"}
    assert pit_read_tools.pit_read_source("SSE:600340:AR2019:ORIGINAL")["ok"] is False
    assert pit_read_tools.pit_read_framework("framework/policy.md")["ok"] is False
