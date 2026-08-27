"""unified_decision_synthesizer.py — V12：统一决策合成器。

综合 Dayu 定性研究决定（Continue/Pause/Abandon）与 Turtle 定量投资决定（Buy/Hold/Avoid），
通过合成矩阵输出 5 状态统一决策。

用法:
    python unified_decision_synthesizer.py \\
        --qualitative-decision continue \\
        --quantitative-decision buy \\
        --output unified_decision.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# 决策枚举
# ---------------------------------------------------------------------------

class QualitativeDecision(str, Enum):
    """Dayu 定性研究决定。"""
    CONTINUE = "continue"
    PAUSE = "pause"
    ABANDON = "abandon"


class QuantitativeDecision(str, Enum):
    """Turtle 定量投资决定。"""
    BUY = "buy"
    HOLD = "hold"
    AVOID = "avoid"
    UNRESOLVED = "unresolved"


class UnifiedDecision(str, Enum):
    """V12 统一 5 状态决策。"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    AVOID = "avoid"
    STRONG_REJECT = "strong_reject"
    RESEARCH_ONLY = "research_only"


# 合成矩阵: (qualitative, quantitative) → (unified, consistency_note)
SYNTHESIS_MATRIX: dict[tuple[str, str], tuple[str, str]] = {
    (QualitativeDecision.CONTINUE, QuantitativeDecision.BUY): (
        UnifiedDecision.STRONG_BUY,
        "定性定量一致看好：公司质地优秀且估值有吸引力，安全边际充足",
    ),
    (QualitativeDecision.CONTINUE, QuantitativeDecision.HOLD): (
        UnifiedDecision.HOLD,
        "定性看多但定量谨慎：公司质地优秀但当前估值缺乏安全边际，等待更好价格",
    ),
    (QualitativeDecision.CONTINUE, QuantitativeDecision.AVOID): (
        UnifiedDecision.AVOID,
        "⚠️ 根本分歧【好公司太贵】：定性确认公司质地优秀，但定量估值显示严重高估，当前价格无法提供合理回报。建议等待估值回归后重新评估。",
    ),
    (QualitativeDecision.PAUSE, QuantitativeDecision.BUY): (
        UnifiedDecision.BUY,
        "价格合理但定性存疑：估值有吸引力，但定性判断有未解决的难点，建议小仓位试仓并优先验证定性疑虑",
    ),
    (QualitativeDecision.PAUSE, QuantitativeDecision.HOLD): (
        UnifiedDecision.HOLD,
        "定性定量均不确定：继续跟踪关键变量，等待定性或定量信号明确后再做决定",
    ),
    (QualitativeDecision.PAUSE, QuantitativeDecision.AVOID): (
        UnifiedDecision.AVOID,
        "定性存疑且估值偏贵：双重不利因素叠加，建议暂时回避",
    ),
    (QualitativeDecision.ABANDON, QuantitativeDecision.BUY): (
        UnifiedDecision.AVOID,
        "⚠️ 数据冲突：定性判断有否决级信号，但估值显示便宜。可能是价值陷阱，建议重新核验定性和定量数据的可靠性",
    ),
    (QualitativeDecision.ABANDON, QuantitativeDecision.HOLD): (
        UnifiedDecision.AVOID,
        "定性否决信号不容忽视，即使估值不过度，也应保持高度警惕",
    ),
    (QualitativeDecision.ABANDON, QuantitativeDecision.AVOID): (
        UnifiedDecision.STRONG_REJECT,
        "定性定量双重否决：公司存在致命缺陷且估值不具吸引力，强烈建议回避",
    ),
    (QualitativeDecision.CONTINUE, QuantitativeDecision.UNRESOLVED): (
        UnifiedDecision.RESEARCH_ONLY,
        "企业经营判断继续；核心估值或价格输入不可用，当前价格动作暂不承保",
    ),
    (QualitativeDecision.PAUSE, QuantitativeDecision.UNRESOLVED): (
        UnifiedDecision.RESEARCH_ONLY,
        "企业经营判断保留局部疑点；核心估值或价格输入不可用，当前价格动作暂不承保",
    ),
    (QualitativeDecision.ABANDON, QuantitativeDecision.UNRESOLVED): (
        UnifiedDecision.AVOID,
        "企业经营已有独立的永久损失否决证据；估值未结算不抵消该经营否决",
    ),
}


# ---------------------------------------------------------------------------
# 决策输入/输出
# ---------------------------------------------------------------------------


@dataclass
class UnifiedDecisionInput:
    """统一决策输入。

    Args:
        company_name: 公司名称。
        ts_code: 股票代码。
        qualitative_decision: Dayu 定性研究决定。
        qualitative_rationale: 定性决定核心理由。
        quantitative_decision: Turtle 定量投资决定。
        quantitative_rationale: 定量决定核心理由。
        qualitative_quantitative_consistent: 定性定量是否一致。
        root_divergence: 如果不一致，根本分歧是什么。
        position_pct: 若为买入/强买入，建议仓位百分比。
        key_risks: 关键风险列表。
        key_assumptions: 关键假设列表。
        monitor_triggers: 监控触发器。
        exit_conditions: 退出条件。
    """

    company_name: str = ""
    ts_code: str = ""
    qualitative_decision: str = ""
    qualitative_rationale: str = ""
    quantitative_decision: str = ""
    quantitative_rationale: str = ""
    qualitative_quantitative_consistent: bool = True
    root_divergence: str = ""
    position_pct: float | None = 0.0
    key_risks: list[str] = field(default_factory=list)
    key_assumptions: list[dict[str, str]] = field(default_factory=list)
    monitor_triggers: list[str] = field(default_factory=list)
    exit_conditions: list[str] = field(default_factory=list)


@dataclass
class UnifiedDecisionOutput:
    """统一决策输出。

    Args:
        unified_decision: 5状态统一决策。
        consistency_note: 定性定量一致性说明。
        qualitative_decision: 输入的定性决定。
        quantitative_decision: 输入的定量决定。
        rationales: 核心理由列表（来自定性和定量）。
        position_pct: 建议仓位百分比（仅 buy/strong_buy 时 > 0）。
        monitor_triggers: 合并后的监控触发器。
        exit_conditions: 合并后的退出条件。
    """

    unified_decision: str
    consistency_note: str
    qualitative_decision: str
    quantitative_decision: str
    rationales: list[str] = field(default_factory=list)
    position_pct: float | None = 0.0
    monitor_triggers: list[str] = field(default_factory=list)
    exit_conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unified_decision": self.unified_decision,
            "consistency_note": self.consistency_note,
            "qualitative_decision": self.qualitative_decision,
            "quantitative_decision": self.quantitative_decision,
            "rationales": self.rationales,
            "position_pct": self.position_pct,
            "monitor_triggers": self.monitor_triggers,
            "exit_conditions": self.exit_conditions,
        }


# ---------------------------------------------------------------------------
# 合成逻辑
# ---------------------------------------------------------------------------


def synthesize_decision(input_data: UnifiedDecisionInput) -> UnifiedDecisionOutput:
    """综合定性和定量决定，输出统一决策。

    若定性输入缺失（向后兼容），回退到纯定量决策。

    Args:
        input_data: 统一决策输入。

    Returns:
        UnifiedDecisionOutput。
    """
    qual = input_data.qualitative_decision.lower().strip()
    quant = input_data.quantitative_decision.lower().strip()

    # 向后兼容：无定性输入时回退到纯定量
    if not qual or qual not in (q.value for q in QualitativeDecision):
        return _fallback_quantitative_only(input_data)

    if quant not in (q.value for q in QuantitativeDecision):
        quant = QuantitativeDecision.HOLD

    # 查找合成矩阵
    key = (qual, quant)
    if key in SYNTHESIS_MATRIX:
        unified, note = SYNTHESIS_MATRIX[key]
    else:
        unified = UnifiedDecision.HOLD
        note = f"定性={qual}, 定量={quant}，无法确定合成结果，默认观望"

    # 构建输出
    rationales: list[str] = []
    if input_data.qualitative_rationale:
        rationales.append(f"[定性] {input_data.qualitative_rationale}")
    if input_data.quantitative_rationale:
        rationales.append(f"[定量] {input_data.quantitative_rationale}")

    # 只有在买入决策时才保留仓位
    position_pct = input_data.position_pct if unified in (
        UnifiedDecision.STRONG_BUY, UnifiedDecision.BUY
    ) else (None if unified == UnifiedDecision.RESEARCH_ONLY else 0.0)

    return UnifiedDecisionOutput(
        unified_decision=unified,
        consistency_note=note,
        qualitative_decision=qual,
        quantitative_decision=quant,
        rationales=rationales,
        position_pct=position_pct,
        monitor_triggers=list(input_data.monitor_triggers),
        exit_conditions=list(input_data.exit_conditions),
    )


def _fallback_quantitative_only(input_data: UnifiedDecisionInput) -> UnifiedDecisionOutput:
    """纯定量回退决策（V12 向后兼容）。"""
    quant = input_data.quantitative_decision.lower().strip()
    mapping = {
        QuantitativeDecision.BUY: (UnifiedDecision.BUY, "仅定量判断：估值有吸引力（未进行定性分析）"),
        QuantitativeDecision.HOLD: (UnifiedDecision.HOLD, "仅定量判断：估值处于观望区间（未进行定性分析）"),
        QuantitativeDecision.AVOID: (UnifiedDecision.AVOID, "仅定量判断：估值不具吸引力（未进行定性分析）"),
        QuantitativeDecision.UNRESOLVED: (UnifiedDecision.RESEARCH_ONLY, "仅定量判断：估值或价格输入不可用，当前价格动作暂不承保"),
    }
    unified, note = mapping.get(quant, (UnifiedDecision.HOLD, "仅定量判断：无法确定"))
    return UnifiedDecisionOutput(
        unified_decision=unified,
        consistency_note=note,
        qualitative_decision="",
        quantitative_decision=quant,
        rationales=[f"[定量] {input_data.quantitative_rationale}"] if input_data.quantitative_rationale else [],
        position_pct=(
            input_data.position_pct
            if unified in (UnifiedDecision.STRONG_BUY, UnifiedDecision.BUY)
            else (None if unified == UnifiedDecision.RESEARCH_ONLY else 0.0)
        ),
        monitor_triggers=list(input_data.monitor_triggers),
        exit_conditions=list(input_data.exit_conditions),
    )


def validate_decision(output: UnifiedDecisionOutput) -> list[str]:
    """验证统一决策的合理性，返回警告列表。

    Args:
        output: 统一决策输出。

    Returns:
        警告消息列表（空列表表示无问题）。
    """
    warnings: list[str] = []
    if output.unified_decision in (UnifiedDecision.STRONG_BUY, UnifiedDecision.BUY) and (output.position_pct or 0) <= 0:
        warnings.append("买入决策但仓位为0%")
    if output.unified_decision == UnifiedDecision.STRONG_REJECT and (output.position_pct or 0) > 0:
        warnings.append("强回避决策但仓位>0")
    if not output.rationales:
        warnings.append("决策缺乏核心理由")
    if output.qualitative_decision == QualitativeDecision.ABANDON and output.unified_decision == UnifiedDecision.STRONG_BUY:
        warnings.append("定性否决但输出强买入——这是不可能的组合")
    return warnings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="V12 统一决策合成器")
    ap.add_argument("--qualitative-decision", default="", help="Dayu 定性研究决定 (continue/pause/abandon)")
    ap.add_argument("--qualitative-rationale", default="", help="定性决定核心理由")
    ap.add_argument("--quantitative-decision", default="hold", help="Turtle 定量投资决定 (buy/hold/avoid/unresolved)")
    ap.add_argument("--quantitative-rationale", default="", help="定量决定核心理由")
    ap.add_argument("--position-pct", type=float, default=0.0, help="建议仓位百分比")
    ap.add_argument("--output", required=True, help="输出 unified_decision.json 路径")
    ap.add_argument("--input-json", help="从 JSON 文件读取决策输入（替代命令行参数）")
    args = ap.parse_args()

    # 从 JSON 文件读取
    if args.input_json:
        raw = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
        qual_decision = raw.get("qualitative_decision", "")
        qual_rationale = raw.get("qualitative_rationale", "")
        quant_decision = raw.get("quantitative_decision", "hold")
        quant_rationale = raw.get("quantitative_rationale", "")
        raw_position = raw.get("position_pct")
        position_pct = None if raw_position is None else float(raw_position)
    else:
        qual_decision = args.qualitative_decision
        qual_rationale = args.qualitative_rationale
        quant_decision = args.quantitative_decision
        quant_rationale = args.quantitative_rationale
        position_pct = args.position_pct

    # 合成
    input_data = UnifiedDecisionInput(
        qualitative_decision=qual_decision,
        qualitative_rationale=qual_rationale,
        quantitative_decision=quant_decision,
        quantitative_rationale=quant_rationale,
        position_pct=position_pct,
    )
    output = synthesize_decision(input_data)

    # 验证
    warnings = validate_decision(output)
    if warnings:
        for w in warnings:
            print(f"⚠️ {w}", file=sys.stderr)

    # 输出
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 打印结果
    unified_labels = {
        "strong_buy": "🟢 强买入",
        "buy": "🟢 买入",
        "hold": "🟡 观望",
        "avoid": "🔴 回避",
        "strong_reject": "⛔ 强回避",
        "research_only": "🔎 仅研究（当前价格动作未承保）",
    }
    label = unified_labels.get(output.unified_decision, output.unified_decision)
    print(f"✅ 统一决策: {label}")
    print(f"   定性: {output.qualitative_decision or '未提供'} | 定量: {output.quantitative_decision}")
    print(f"   一致性: {output.consistency_note}")
    if (output.position_pct or 0) > 0:
        print(f"   仓位: {output.position_pct}%")
    print(f"   输出: {output_path}")


if __name__ == "__main__":
    main()
