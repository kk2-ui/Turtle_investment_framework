from pathlib import Path

from codex_workflow import collect_turtle_warnings


def test_collect_turtle_warnings_filters_explanatory_items(tmp_path: Path):
    preflight_text = (
        "- Warnings 摘要: 回购无记录；母公司单体报表不适用；`c_pay_to_staff` 不可用\n"
    )
    data_pack_text = """
### 17.4 因子3·步骤4 经营性现金支出
> † W2: `c_pay_to_staff` 为空，已用利润表 SGA（销售+管理+研发费用）替代，偏保守；若港股年报 fallback 已反填员工成本代理，则不会触发此脚注。

### 17.3 因子3·步骤1 真实现金收入（保守基准）
> ⚠️ 2025: contract_liab 为空，CL变动=0 可能影响现金收入
"""

    warnings = collect_turtle_warnings(tmp_path, data_pack_text, preflight_text)

    assert "回购无记录" not in warnings
    assert "母公司单体报表不适用" not in warnings
    assert "`c_pay_to_staff` 不可用" not in warnings
    assert "`contract_liab` 为空" in warnings
    assert "`c_pay_to_staff` 原始字段缺失，W2 已用 SGA 替代" in warnings


def test_collect_turtle_warnings_ignores_stale_preflight_items_when_data_pack_is_current(tmp_path: Path):
    preflight_text = (
        "- Warnings 摘要: 港股业务构成覆盖有限；`contract_liab` 为空；`c_pay_to_staff` 不可用\n"
    )
    data_pack_text = """
## 9. 主营业务构成

| 项目 | 数值 |
| --- | ---: |
| 收入 | 100 |

### 17.3 因子3·步骤1 真实现金收入（保守基准）

| 年份 | S 营业收入 | T 应收变动 | U 合同负债变动 | 真实现金收入 | 收款比率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 100 | 5 | 3 | 95 | 95.00% |

### 17.4 因子3·步骤4 经营性现金支出
> † W2: `c_pay_to_staff` 为空，已用利润表 SGA（销售+管理+研发费用）替代，偏保守；若港股年报 fallback 已反填员工成本代理，则不会触发此脚注。
"""

    warnings = collect_turtle_warnings(tmp_path, data_pack_text, preflight_text)

    assert "`contract_liab` 为空" not in warnings
    assert "港股业务构成覆盖有限" not in warnings
    assert "`c_pay_to_staff` 原始字段缺失，W2 已用 SGA 替代" in warnings
