import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from turtle_agent.tools.phase_tools import _extract_labor_by_function_from_markdown  # noqa: E402


def test_extract_labor_by_function_from_markdown_fee_notes():
    md_text = """
## 第 183 页

45. 销售费用
项目 本年金额 上年金额
职工薪酬 65,536,525.16 66,188,776.52

46. 管理费用
项目 本年金额 上年金额
职工薪酬 489,877,066.42 505,675,805.81

## 第 184 页

47. 研发费用
项目 本年金额 上年金额
职工薪酬 51,273,251.56 44,407,921.62
"""

    result = _extract_labor_by_function_from_markdown(md_text)

    assert result is not None
    assert result["production"] is None
    assert result["sales"] == 65.5365
    assert result["admin"] == 489.8771
    assert result["rd"] == 51.2733
    assert result["total"] is None
    assert result["source_pages"] == [183, 184]
