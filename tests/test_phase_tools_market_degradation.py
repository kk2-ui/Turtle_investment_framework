import json
from pathlib import Path

from scripts import niangao_market_bridge
from scripts.turtle_agent.tools.phase_tools import compute_bundle_db


def test_missing_fresh_quote_preserves_enterprise_research_path(tmp_path: Path, monkeypatch) -> None:
    def _unavailable(*args, **kwargs):
        raise ValueError("no fresh quote")

    monkeypatch.setattr(niangao_market_bridge, "write_snapshot", _unavailable)

    result = compute_bundle_db("000001.SZ", str(tmp_path))

    assert result["ok"] is True
    assert result["degraded"] is True
    assert result["quantitative_status"] == "UNRESOLVED_CURRENT_MARKET"
    bundle = json.loads((tmp_path / "compute_bundle.json").read_text(encoding="utf-8"))
    assert bundle["factor4"]["verdict"]["final"] == "UNRESOLVED_VALUATION"
    assert bundle["factor4"]["position"]["recommended"] is None
    assert bundle["rejection_summary"]["enterprise_judgment"] == "continue"
