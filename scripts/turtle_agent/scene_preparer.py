"""场景准备器 — 借鉴 Dayu ``scene_preparer.py``。

自动组装 Agent system prompt：加载分析合约 + 模板 + 工具列表 → 统一 prompt。
"""

from __future__ import annotations

import json
import os
from typing import Any

# 默认模板路径
DEFAULT_TEMPLATE_PATH = "templates/report_template_v10.md"


class ScenePreparer:
    """准备 Agent 分析场景。

    借鉴 Dayu 的 scene preparation 流程：
    1. 加载 Scene Definition（分析合约 + 模板）
    2. 收集 Prompt Contributions（工具列表、数据摘要）
    3. Compose → 完整 system prompt

    Args:
        code: 股票代码。
        contract_path: 分析合约 JSON 路径。
        template_path: 模板 Markdown 路径。
        output_dir: 股票输出目录。
    """

    def __init__(
        self,
        code: str,
        contract_path: str,
        template_path: str = DEFAULT_TEMPLATE_PATH,
        output_dir: str = "",
    ) -> None:
        self._code: str = code
        self._contract_path: str = contract_path
        self._template_path: str = template_path
        self._output_dir: str = output_dir or os.path.dirname(contract_path)

        self._contract: dict[str, Any] = {}
        self._template_raw: str = ""
        self._data_context: dict[str, Any] = {}
        self._tool_schemas: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load_contract(self) -> dict[str, Any]:
        """加载分析合约。"""
        if os.path.exists(self._contract_path):
            with open(self._contract_path, encoding="utf-8") as f:
                self._contract = json.load(f)
        return self._contract

    def load_template(self) -> str:
        """加载报告模板。"""
        path = self._template_path
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._template_raw = f.read()
        return self._template_raw

    def load_data_context(self) -> dict[str, Any]:
        """加载 Zone A/B/J 数据上下文（14个JSON）。"""
        data_files = [
            "compute_bundle.json", "financial_trends.json",
            "mda.json", "segments.json", "risks.json",
            "governance.json", "audit.json",
            "moat_assessment.json", "capex_classification.json",
            "earnings_quality.json", "data_discount.json",
        ]
        for jf in data_files:
            path = os.path.join(self._output_dir, jf)
            key = jf.replace(".json", "")
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        self._data_context[key] = json.load(f)
                except (json.JSONDecodeError, OSError):
                    self._data_context[key] = {"_error": "parse_failed"}
            else:
                self._data_context[key] = {"_missing": True}
        return self._data_context

    def set_tool_schemas(self, schemas: list[dict[str, Any]]) -> None:
        """注入工具 schema 列表。"""
        self._tool_schemas = schemas

    # ------------------------------------------------------------------
    # 组装
    # ------------------------------------------------------------------

    def compose(self) -> str:
        """组装完整 system prompt。

        Returns:
            可直接作为 system message 的 prompt 文本。
        """
        effective_years = self._contract.get("effective_years", [])
        cycle_type = self._contract.get("cycle_type", "未知")
        analysis_start = self._contract.get("analysis_start_year", "?")

        # 公司名
        cb = self._data_context.get("compute_bundle", {})
        company_name = cb.get("company_name", self._code)

        # 工具列表
        tool_list = "\n".join(
            f"- **{t['function']['name']}**: {t['function']['description']}"
            for t in self._tool_schemas
        )

        # 数据摘要
        data_summary = self._build_data_summary()

        # 模板（最多5000字）
        template_preview = self._template_raw[:5000]

        return f"""# 龟龟策略分析师 (V11)

你是龟龟投资策略的**唯一分析师**。你拥有完整的分析上下文和工具集。
按顺序逐步完成分析，主动调用工具获取所需数据。

## 分析标的
- 代码: {self._code}
- 公司: {company_name}
- 周期分类: {cycle_type}
- 有效分析窗口: {effective_years}（起始: {analysis_start}）

## 数据上下文
{data_summary}

## 分析方法论
1. **了解数据**: 调用 list_documents 查看可用文档
2. **提取财务**: 调用 get_financial_statement 和 get_financial_trends 获取定量数据
3. **定性分析**: 调用 read_section 读取年报关键章节（MD&A、风险、治理、附注）
4. **定量计算**: 调用 compute_gg、compute_ddm、assess_moat 完成估值
5. **写作报告**: 按模板合约逐章写入（write_chapter），每章写完后审计（audit_chapter）
6. **最终决策**: 综合各因子给出 Continue/Hold/Abandon 结论（evaluate_decision）
7. **组装报告**: 调用 assemble_report 生成完整报告

## 模板合约要求
{template_preview}

## 写作约束
- **所有数据断言必须附带 [source: 文件名] 证据锚点**
- 缺失数据标注 "⚠️ 数据不可用"，禁止编造数字
- 金额单位: 百万元 RMB
- 数值保留 1 位小数

## 可用工具
{tool_list}

## 重要提示
- 不要一次性读完所有数据——按需调用工具
- 工具返回的数据可能很大（如 read_section 可能返回数万字），请合理使用
- 如果工具返回 error，记录错误并尝试其他方式获取数据
- 目标产出: 一份完整的 ~8 章分析报告"""

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _build_data_summary(self) -> str:
        """构建数据上下文摘要。"""
        lines: list[str] = []
        for key, value in self._data_context.items():
            if isinstance(value, dict):
                if value.get("_missing"):
                    lines.append(f"- **{key}**: ❌ 缺失")
                elif value.get("_error"):
                    lines.append(f"- **{key}**: ⚠️ 解析失败")
                else:
                    # 简要摘要
                    summary = self._summarize_json(key, value)
                    lines.append(f"- **{key}**: {summary}")
        return "\n".join(lines) if lines else "（无可用数据文件）"

    @staticmethod
    def _summarize_json(key: str, data: dict[str, Any]) -> str:
        """生成 JSON 数据文件的单行摘要。"""
        if key == "compute_bundle":
            gg = data.get("gg", {})
            ddm = data.get("ddm", {})
            return (
                f"GG(base)={gg.get('base', '?')}%, "
                f"DDM={ddm.get('fair_value', '?')}, "
                f"II={data.get('ii', '?')}%"
            )
        if key == "moat_assessment":
            return f"评级={data.get('moat_rating', '?')}"
        if isinstance(data, dict) and len(data) > 10:
            return f"{{...{len(data)} keys}}"
        return "✅ 可用"
