from __future__ import annotations

from pathlib import Path

from turtle_agent.tool_registry import ToolRegistry
from turtle_agent.tools.pit_production_write_tools import (
    clear_pit_production_writer,
    configure_pit_production_writer,
)


def test_pit_production_write_facade_binds_output_and_exposes_no_path_argument(tmp_path: Path) -> None:
    output = tmp_path / "fresh-output"
    configure_pit_production_writer(output_dir=output, code="600340.SH")
    try:
        tools = ToolRegistry()
        tools.auto_discover("turtle_agent.tools.pit_production_write_tools")
        schemas = {
            item["function"]["name"]: item["function"]["parameters"]["properties"]
            for item in tools.get_schemas()
        }
        result = tools.execute(
            "pit_write_chapter",
            {
                "chapter_index": 1,
                "title": "Business",
                "content": "The point-in-time report preserves UNKNOWN where the source package is silent.",
            },
        )
    finally:
        clear_pit_production_writer()

    assert "pit_write_chapter" in schemas
    assert "pit_verify_official_fact" in schemas
    assert "pit_assemble_report" in schemas
    assert "write_chapter" not in schemas
    assert all("output_dir" not in parameters for parameters in schemas.values())
    assert result["ok"] is True
    chapter_path = Path(result["value"]["path"])
    assert chapter_path.is_file()
    assert output in chapter_path.parents


def test_pit_production_write_facade_rejects_an_attempted_output_override(tmp_path: Path) -> None:
    configure_pit_production_writer(output_dir=tmp_path / "fresh-output", code="600340.SH")
    try:
        tools = ToolRegistry()
        tools.auto_discover("turtle_agent.tools.pit_production_write_tools")
        result = tools.execute(
            "pit_write_chapter",
            {
                "output_dir": str(tmp_path / "other-output"),
                "chapter_index": 1,
                "title": "Business",
                "content": "attempted path override",
            },
        )
    finally:
        clear_pit_production_writer()

    assert result["ok"] is False
    assert "output_dir" in result["error"]
    assert not (tmp_path / "other-output").exists()
