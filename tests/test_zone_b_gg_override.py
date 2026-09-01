import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from zone_b_v8 import (  # noqa: E402
    _extract_employee_benefit_total_from_report_md,
    _extract_labor_by_function_from_report_md,
    build_gg_override_from_partials,
    write_zone_b_jsons,
)


def test_build_gg_override_from_partials_extracts_years():
    partials = {
        "2024": {
            "labor_by_function": {
                "production": 3200.0,
                "sales": 400.0,
                "admin": 300.0,
                "rd": 100.0,
                "total": 4100.0,
                "quote": "按职能分类的员工成本包括生产、销售及行政人员。",
                "note_basis": "职工薪酬附注按职能分类表",
                "source_pages": [120, 121],
            }
        },
        "2025": {
            "labor_by_function": {
                "production": 3709.0,
                "sales": 410.0,
                "admin": 307.0,
                "rd": 0.0,
                "total": 4426.0,
                "quote": "僱員福利開支按職能分類列示。",
                "note_basis": "僱員福利開支附注",
                "source_pages": [122],
            }
        },
    }

    override = build_gg_override_from_partials(partials)

    assert override is not None
    assert sorted(override["years"].keys()) == ["2024", "2025"]
    assert override["years"]["2025"]["direct_labor_cost"] == 3709.0
    assert override["years"]["2025"]["admin_labor_cost"] == 307.0
    assert override["years"]["2025"]["sales_labor_cost"] == 410.0
    assert override["years"]["2025"]["rd_labor_cost"] == 0.0
    assert override["years"]["2025"]["outsourced_service_cost"] == 0.0
    assert override["years"]["2025"]["confidence"] == "high"


def test_build_gg_override_from_partials_allows_hybrid_note_without_production():
    partials = {
        "2025": {
            "labor_by_function": {
                "production": None,
                "sales": 65.5,
                "admin": 489.9,
                "rd": 51.3,
                "total": None,
                "quote": "销售费用/管理费用/研发费用中的职工薪酬分项列示。",
                "note_basis": "费用附注中的销售/管理/研发职工薪酬",
                "source_pages": [183, 184],
            }
        }
    }

    override = build_gg_override_from_partials(partials)

    assert override is not None
    assert override["years"]["2025"]["direct_labor_cost"] is None
    assert override["years"]["2025"]["admin_labor_cost"] == 489.9
    assert override["years"]["2025"]["sales_labor_cost"] == 65.5
    assert override["years"]["2025"]["rd_labor_cost"] == 51.3
    assert override["years"]["2025"]["confidence"] == "medium"


def test_write_zone_b_jsons_writes_gg_override(tmp_path):
    master_output = {
        "mda.json": {"year_highlights": {"2025": ["收入保持稳定增长"]}, "key_operations_metrics": []},
        "segments.json": {"segments": {}},
        "risks.json": {"ar_aging": [], "ar_total_m": 0.0, "goodwill_balance_m": 0.0},
        "governance.json": {"related_party_transactions": []},
        "audit.json": {"auditor": "PwC", "audit_opinion": "无保留"},
    }
    partials = {
        "2025": {
            "labor_by_function": {
                "production": 3709.0,
                "sales": 410.0,
                "admin": 307.0,
                "rd": 0.0,
                "total": 4426.0,
                "quote": "僱員福利開支按職能分類列示。",
                "note_basis": "僱員福利開支附注",
                "source_pages": [122],
            }
        }
    }

    write_zone_b_jsons(master_output, str(tmp_path), partials)

    gg_path = tmp_path / "gg_override.json"
    assert gg_path.exists()
    data = json.loads(gg_path.read_text())
    assert data["years"]["2025"]["direct_labor_cost"] == 3709.0
    assert data["years"]["2025"]["rd_labor_cost"] == 0.0
    assert data["years"]["2025"]["source_pages"] == [122]


def test_build_gg_override_from_report_markdown_fallback(tmp_path):
    (tmp_path / "2025_年报.md").write_text(
        "\n".join(
            [
                "年度利潤乃經扣除╱（計入）以下各項得出：",
                "員工成本 — 包括董事薪酬（附註14）",
                "— 計入銷售及服務成本 612,221 574,332",
                "— 計入行政開支 58,319 52,190",
            ]
        ),
        encoding="utf-8",
    )
    partials = {
        "2025": {
            "employee_benefit_expense_m": 670.54,
            "labor_by_function": None,
        }
    }

    override = build_gg_override_from_partials(partials, stock_dir=str(tmp_path))

    assert override is not None
    assert override["years"]["2025"]["direct_labor_cost"] == 612.221
    assert override["years"]["2025"]["admin_labor_cost"] == 58.319
    assert override["years"]["2025"]["total_labor_cost"] == 670.54
    assert "計入銷售及服務成本" in override["years"]["2025"]["quote"]


def test_build_gg_override_skips_total_only_labor_dict(tmp_path):
    partials = {
        "2024": {
            "labor_by_function": {
                "production": None,
                "sales": None,
                "admin": None,
                "rd": None,
                "total": 229.383,
                "quote": "員工成本總額 229,383 208,642",
                "note_basis": "员工成本总额",
                "source_pages": [96],
            }
        }
    }

    override = build_gg_override_from_partials(partials, stock_dir=str(tmp_path))

    assert override is None


def test_extract_employee_benefit_total_from_report_markdown(tmp_path):
    (tmp_path / "2024_年报.md").write_text(
        "\n".join(
            [
                "員工成本（包括附註12所披露董事酬金）：",
                "－薪金及其他福利 203,286 185,838",
                "－退休福利計劃供款 25,276 21,794",
                "員工成本總額 229,383 208,642",
            ]
        ),
        encoding="utf-8",
    )

    total = _extract_employee_benefit_total_from_report_md(str(tmp_path), "2024")

    assert total == 229.383


def test_extract_employee_benefit_total_from_contextual_total_row(tmp_path):
    (tmp_path / "2025_年报.md").write_text(
        "\n".join(
            [
                "6 除稅前溢利（續）",
                "(b) 員工成本",
                "2025年 2024年",
                "薪金、工資及其他福利 320,208 317,478",
                "界定供款退休計劃供款 33,571 33,286",
                "總計 353,779 350,764",
            ]
        ),
        encoding="utf-8",
    )

    total = _extract_employee_benefit_total_from_report_md(str(tmp_path), "2025")

    assert total == 353.779


def test_extract_labor_by_function_from_english_destination_prose(tmp_path):
    (tmp_path / "2025_年报.md").write_text(
        "\n".join(
            [
                "The total staff costs incurred for the year ended 31 December 2025 was approximately RMB4,220.4 million,",
                "of which, RMB3,941.9 million and RMB278.5 million was recognised",
                "in direct operating expenses and selling and administrative expenses respectively.",
            ]
        ),
        encoding="utf-8",
    )

    labor = _extract_labor_by_function_from_report_md(str(tmp_path), "2025")

    assert labor is not None
    assert labor["production"] == 3941.9
    assert labor["admin"] == 278.5
    assert labor["total"] == 4220.4


def test_extract_labor_by_function_ignores_comparison_period_parentheticals(tmp_path):
    (tmp_path / "2025_年报.md").write_text(
        "\n".join(
            [
                "The total staff costs incurred for the year ended 31 December 2025 was approximately RMB4,220.4 million (2024: RMB4,524.2 million (restated)),",
                "of which, RMB3,941.9 million (2024: RMB4,214.5 million (restated)) and RMB278.5 million (2024: RMB309.7 million (restated)) was recognised",
                "in direct operating expenses and selling and administrative expenses respectively.",
            ]
        ),
        encoding="utf-8",
    )

    labor = _extract_labor_by_function_from_report_md(str(tmp_path), "2025")

    assert labor is not None
    assert labor["production"] == 3941.9
    assert labor["admin"] == 278.5
    assert labor["total"] == 4220.4


def test_extract_labor_by_function_from_employee_cost_allocation_table(tmp_path):
    (tmp_path / "2023_年报.md").write_text(
        "\n".join(
            [
                "附註： 計入銷售成本、分銷及銷售開支及行政開支的員工成本和折舊及攤銷總額如下：",
                "2023年 2022年",
                "人民幣百萬元 人民幣百萬元",
                "計入員工成本：",
                "銷售成本 1,148 1,174",
                "分銷及銷售開支 717 718",
                "行政開支 2,150 2,104",
                "4,015 3,996",
            ]
        ),
        encoding="utf-8",
    )

    labor = _extract_labor_by_function_from_report_md(str(tmp_path), "2023")

    assert labor is not None
    assert labor["production"] == 1148.0
    assert labor["sales"] == 717.0
    assert labor["admin"] == 2150.0
    assert labor["total"] == 4015.0


def test_extract_labor_by_function_handles_ocr_split_digits(tmp_path):
    (tmp_path / "2022_年报.md").write_text(
        "\n".join(
            [
                "附註a： 分配員工成本和折舊及攤銷總額如下：",
                "計入員工成本：",
                "銷售成本 1,174 1,144",
                "分銷及銷售開支 718 718",
                "行政開支 2,10 4 1,852",
                "3,996 3,714",
            ]
        ),
        encoding="utf-8",
    )

    labor = _extract_labor_by_function_from_report_md(str(tmp_path), "2022")

    assert labor is not None
    assert labor["admin"] == 2104.0
    assert labor["total"] == 3996.0


def test_extract_employee_benefit_total_from_component_block_total_row(tmp_path):
    (tmp_path / "2025_年报.md").write_text(
        "\n".join(
            [
                "僱員福利開支（* 不包括董事及主要行政人員薪酬（附註9））：",
                "工資及薪金 1,222,464 1,210,480",
                "退休金計劃供款（定額供款計劃）** 263,959 256,857",
                "權益結算股份支付開支 1,431 54,162",
                "減：生物資產資本化 (114,773) (104,308)",
                "1,373,081 1,417,191",
            ]
        ),
        encoding="utf-8",
    )

    total = _extract_employee_benefit_total_from_report_md(str(tmp_path), "2025")

    assert total == 1373.081


def test_extract_employee_benefit_total_from_labeled_total_line(tmp_path):
    (tmp_path / "2024_年报.md").write_text(
        "\n".join(
            [
                "Employee benefit expenses (note 8) 僱員福利開支（附註8） 1,122,272 980,403",
            ]
        ),
        encoding="utf-8",
    )

    total = _extract_employee_benefit_total_from_report_md(str(tmp_path), "2024")

    assert total == 1122.272
