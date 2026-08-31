from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.industry_experience_pack import (
    build_compact_industry_decision_memory,
    main,
    render_compact_industry_decision_memory,
)


ROOT = Path(__file__).resolve().parents[1]
PILOT_ROOT = (
    ROOT
    / "docs/development/research/industry_learning_blocks"
    / "CN_CEMENT_2014_2018"
)
PACK_PATH = PILOT_ROOT / "67_industry_experience_pack_training_v3.json"
SAMPLE_PATH = PILOT_ROOT / "69_compact_industry_decision_memory_v1.md"
CONTEXT_PATH = (
    ROOT
    / "docs/development/research/training_campaigns"
    / "ENTERPRISE_UNDERWRITING_COURSE_2C_CN600720_20180430"
    / "context/02_CN600720_INDUSTRY_UNDERWRITING_CONTEXT.json"
)


def _inputs() -> tuple[dict, dict]:
    return (
        json.loads(PACK_PATH.read_text(encoding="utf-8")),
        json.loads(CONTEXT_PATH.read_text(encoding="utf-8")),
    )


def test_compact_memory_keeps_five_decision_items_without_company_facts() -> None:
    pack, context = _inputs()

    memory = build_compact_industry_decision_memory(pack, context, root=ROOT)
    rendered = render_compact_industry_decision_memory(memory)

    assert memory["capability_status"] == "HYPOTHESIS_AND_RESEARCH_QUESTION_ONLY"
    assert memory["main_industry_path"] == pack["current_synthesis"]["central_industry_path"]
    assert memory["strongest_rival"] == pack["current_synthesis"]["strongest_rival"]
    assert len(memory["target_company_verification_questions"]) == 4
    assert len(memory["reversal_observations"]) == 4
    assert rendered.count("\n## ") == 5
    assert "行业利润池改善能否穿过营运资本" in rendered
    assert "perimeter bridge" in rendered
    assert rendered == SAMPLE_PATH.read_text(encoding="utf-8")

    prohibited = {
        context["company_identity"]["company_id"],
        context["company_identity"]["company_name"],
        "CN:600585",
        "CN:600425",
        "CN:600802",
        "CN:600801",
        "CN:000401",
        "海螺水泥",
        "青松建化",
        "福建水泥",
        "华新水泥",
        "冀东水泥",
        "Jiuquan Hongda",
        "evidence_refs",
        "source_object_ref",
        "QLS:FY2013",
    }
    assert not [literal for literal in prohibited if literal in rendered]


def test_compact_memory_accepts_bounded_context_but_not_a_draft_pack() -> None:
    pack, context = _inputs()
    assert context["context_status"] == "BOUNDED"
    assert build_compact_industry_decision_memory(pack, context, root=ROOT)

    draft = json.loads(
        (PILOT_ROOT / "56_industry_experience_pack_replay_v1.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(
        ValueError,
        match="industry_experience_pack_not_training_ready:DRAFT",
    ):
        build_compact_industry_decision_memory(draft, context, root=ROOT)


def test_compact_memory_rejects_industry_or_cutoff_mismatch() -> None:
    pack, context = _inputs()
    wrong_industry = deepcopy(context)
    wrong_industry["company_identity"]["industry_ids"] = ["INDUSTRY:OTHER"]
    with pytest.raises(ValueError, match="pack_context_industry_mismatch"):
        build_compact_industry_decision_memory(pack, wrong_industry, root=ROOT)

    earlier_context = deepcopy(context)
    earlier_context["company_identity"]["cutoff_at"] = "2018-04-29T23:59:59+08:00"
    with pytest.raises(ValueError, match="pack_cutoff_after_target_context"):
        build_compact_industry_decision_memory(pack, earlier_context, root=ROOT)


def test_cli_compiles_checked_in_cement_sample(tmp_path: Path, capsys) -> None:
    output = tmp_path / "compact_memory.md"

    assert main([
        str(PACK_PATH),
        "--root",
        str(ROOT),
        "--context",
        str(CONTEXT_PATH),
        "--decision-memory-output",
        str(output),
    ]) == 0

    receipt = json.loads(capsys.readouterr().out)
    rendered = output.read_text(encoding="utf-8")
    assert receipt["pack_validation"]["derived_state"] == "TRAINING_READY"
    assert receipt["decision_memory_version"] == "compact-industry-decision-memory.v1"
    assert receipt["capability_status"] == "HYPOTHESIS_AND_RESEARCH_QUESTION_ONLY"
    assert "## 5. 反转观察" in rendered
