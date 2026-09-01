from __future__ import annotations

from pathlib import Path

from scripts.turtle_agent.tools import phase_tools


class _DummyLlm:
    pass


def test_one_failed_zone_b_year_does_not_discard_successful_years(
    tmp_path: Path, monkeypatch
) -> None:
    for year in (2024, 2025):
        (tmp_path / f"{year}_年报.md").write_text("official annual report", encoding="utf-8")

    def _extract(year: str, stock_dir: str, llm_client: object) -> dict:
        if year == "2024":
            return {"ok": False, "error": "extractor could not parse this year"}
        partial = Path(stock_dir) / f"zone_b_{year}_partial.json"
        partial.write_text("{}", encoding="utf-8")
        return {"ok": True, "path": str(partial)}

    monkeypatch.setattr(phase_tools, "_run_year_extraction_from_md", _extract)

    result = phase_tools.extract_zone_b_years(
        stock_dir=str(tmp_path), llm_client=_DummyLlm()
    )

    assert result["ok"] is True
    assert result["degraded"] is True
    assert result["coverage_status"] == "PARTIAL"
    assert result["years_succeeded"] == [2025]
    assert result["failed_years"] == [2024]
    assert (tmp_path / "zone_b_2025_partial.json").exists()


def test_zone_b_stops_only_when_no_year_body_can_be_materialized(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "2025_年报.md").write_text("official annual report", encoding="utf-8")
    monkeypatch.setattr(
        phase_tools,
        "_run_year_extraction_from_md",
        lambda *args, **kwargs: {"ok": False, "error": "extract failed"},
    )

    result = phase_tools.extract_zone_b_years(
        stock_dir=str(tmp_path), llm_client=_DummyLlm()
    )

    assert result["ok"] is False
    assert result["coverage_status"] == "UNAVAILABLE"
    assert result["years_succeeded"] == []
    assert result["failed_years"] == [2025]

