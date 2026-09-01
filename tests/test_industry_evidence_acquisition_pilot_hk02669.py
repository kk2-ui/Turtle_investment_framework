from __future__ import annotations

import json
from pathlib import Path

from scripts.industry_experience_acquisition import (
    validate_industry_evidence_acquisition_plan,
    validate_industry_evidence_acquisition_receipt,
)
from scripts.turtle_agent.tools import read_tools


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / (
    "docs/development/research/pilots/"
    "INDUSTRY_EVIDENCE_ACQUISITION_PILOT_HK02669_20260813"
)


def _read(name: str) -> dict:
    return json.loads((PILOT / name).read_text(encoding="utf-8"))


def test_hk02669_industry_evidence_pilot_is_report_readable_and_keeps_unavailable_sources_local() -> None:
    plan = _read("industry_evidence_acquisition_plan.json")
    receipt = _read("industry_evidence_acquisition_receipt.json")

    assert validate_industry_evidence_acquisition_plan(plan)["state"] == "REVIEWABLE"
    assert validate_industry_evidence_acquisition_receipt(receipt, plan)["state"] == "REVIEWABLE"

    by_role = {
        task["task_id"].split(":")[3]: task
        for task in receipt["task_receipts"]
    }
    assert by_role["CUSTOMER_CHANNEL"]["outcome"] == "PUBLIC_INFO_UNAVAILABLE"
    assert by_role["REGULATION"]["outcome"] == "PUBLIC_INFO_UNAVAILABLE"

    handoff = read_tools.read_industry_evidence_acquisition(str(PILOT))
    assert handoff["ok"] is True
    assert handoff["receipt_state"] == "REVIEWABLE"
    assert len(handoff["accepted_observations"]) == 4
    assert handoff["episode_binding"]["status"] == "READY"
    assert len(handoff["episode_binding"]["evidence_trace_candidates"]) == 4
    assert all(
        "target-company transmission still requires its own primary evidence"
        in candidate["used_for"]
        for candidate in handoff["episode_binding"]["evidence_trace_candidates"]
    )
