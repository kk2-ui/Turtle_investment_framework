"""Contract checks for the E0/E1 Chinese appliance learning-block document.

These checks catch a research-document regression that would otherwise change
the investor meaning of the block: an after-cutoff/non-static source, an
omitted company chain, or accidental downstream authority.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/development/research/CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1.md"
REGISTER = ROOT / "docs/development/research/CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json"


def test_learning_block_keeps_three_company_e0_e1_scope_and_investor_unknowns() -> None:
    text = DOC.read_text(encoding="utf-8")

    for heading in (
        "## 4. E0：行业史与利润机制",
        "### 5.1 格力",
        "### 5.2 美的",
        "### 5.3 海尔",
        "## 6. 跨公司差异",
        "## 7. UNKNOWN",
        "## 8. 可交给下一轮 J2/J3/J4 的问题",
    ):
        assert heading in text

    assert "全国竞争经济体" in text
    assert "不以省份相同为比较前提" in text
    for status in ("`PLAN`", "`IMPLEMENTED_ACTION`", "`EXECUTION_SIGNAL`", "`CUSTOMER_RESPONSE`", "`OBSERVED_FINANCIAL`"):
        assert status in text
    assert "NO_PRIMARY" not in text
    assert "预测、结果结算、方法迁移、CJO、估值、报告、投资" in text


def test_source_register_is_static_cutoff_before_and_page_bound() -> None:
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    cutoffs = {entry["cutoff_id"]: entry["cutoff_at"][:10] for entry in register["cutoffs"]}

    assert register["status"] == "E0_E1_RESEARCH_ONLY"
    assert {"CN:000651", "CN:000333", "CN:600690"} <= {
        source["company_id"] for source in register["sources"]
    }
    assert {"CN:000921", "CN:600839"} <= {
        source["company_id"] for source in register["sources"]
    }
    assert len({source["company_id"] for source in register["sources"]}) >= 5
    assert len(register["sources"]) >= 10
    assert register["allowed_outputs"] == ["INDUSTRY_LEARNING_BLOCK_ONLY", "RESEARCH_AGENDA_ONLY"]

    for source in register["sources"]:
        assert source["provenance"] == "OFFICIAL_STATUTORY_STATIC_PDF"
        assert source["availability_precision"] == "DATE_ONLY"
        assert source["static_pdf_url"].startswith("https://static.cninfo.com.cn/finalpage/")
        assert source["static_pdf_url"].endswith(".PDF")
        assert all(isinstance(page, int) and page > 0 for page in source["physical_pages_used"])
        announced = date.fromisoformat(source["announced_on"])
        for cutoff_id in source["eligible_for_cutoff_ids"]:
            assert announced < date.fromisoformat(cutoffs[cutoff_id])


def test_source_register_has_no_downstream_training_or_investment_authority() -> None:
    register = json.loads(REGISTER.read_text(encoding="utf-8"))

    assert set(register["prohibited_outputs"]) == {
        "FORECAST",
        "OUTCOME_SETTLEMENT",
        "METHOD_TRANSFER",
        "CJO",
        "VALUATION",
        "REPORT",
        "INVESTMENT",
    }
