#!/usr/bin/env python3
"""decision_synthesizer.py — V10：投资决策综合模块。

在所有分析章节完成后，综合各章关键指标生成 Continue/Hold/Abandon 判断。
借鉴 Dayu 的 Chapter 10（是否值得继续深研）+ Chapter 0（Overview）。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

from models import DecisionInput, DecisionOutput


def synthesize_decision(
    decision_input: DecisionInput,
    chapter_results: dict[int, Any] | None = None,
) -> DecisionOutput:
    """综合各章结果生成投资决策。

    优先使用基于规则的综合，LLM 调用由 write_pipeline.py 协调器驱动。

    Args:
        decision_input: 结构化的决策输入数据。
        chapter_results: 各章写作结果（可选，用于更丰富的上下文）。

    Returns:
        DecisionOutput 对象。
    """
    # 基于规则的综合
    return _rule_based_synthesis(decision_input)


def build_decision_input_from_context(
    context: dict[str, Any],
    company_name: str,
    ts_code: str,
) -> DecisionInput:
    """从数据上下文中构建 DecisionInput。

    Args:
        context: 数据上下文字典（含 Zone A/B/J 的所有 JSON）。
        company_name: 公司名称。
        ts_code: 股票代码。

    Returns:
        DecisionInput 对象。
    """
    from models import DecisionInput

    cb = context.get("compute_bundle", {})
    cb_precise = context.get("compute_bundle_precise", {})
    params = cb.get("params", {})
    market = cb.get("market", {})
    factor2 = cb.get("factor2", {})
    factor3 = cb_precise.get("factor3", cb.get("factor3", {}))
    factor4 = cb_precise.get("factor4", cb.get("factor4", {}))
    rejection = cb.get("rejection_summary", {})

    ii = params.get("II", 0)
    rf = params.get("Rf", 0)

    # GG 提取
    if isinstance(factor3.get("gg"), dict):
        gg_base = factor3["gg"].get("base", 0)
        gg_scenarios = {
            "悲观": factor3["gg"].get("pessimistic", 0),
            "乐观": factor3["gg"].get("optimistic", 0),
        }
    else:
        gg_base = factor3.get("gg", 0)
        gg_scenarios = {}

    ddm_v = factor4.get("ddm_v_hkd", factor4.get("ddm_v", 0))
    current_price = market.get("price_hkd", market.get("price", 0))
    position_pct = factor4.get("position_pct", factor4.get("position", 0))

    # 护城河
    moat = context.get("moat_assessment", {})
    moat_rating = moat.get("moat_rating", moat.get("rating", "Unknown"))

    # 风险
    risks_data = context.get("risks", {})
    key_risks: list[str] = []
    if isinstance(risks_data, dict):
        risk_items = risks_data.get("risks", risks_data.get("risk_items", []))
        if isinstance(risk_items, list):
            key_risks = [
                r.get("description", str(r)) if isinstance(r, dict) else str(r)
                for r in risk_items[:5]
            ]

    # 否决门
    if isinstance(rejection, dict):
        rejection_status = rejection.get("overall", "通过")
    else:
        rejection_status = str(rejection) if rejection else "通过"

    return DecisionInput(
        company_name=company_name,
        ts_code=ts_code,
        factor_1a_summary=f"快筛完成" if rejection_status == "通过" else f"否决门: {rejection_status}",
        factor_1b_summary=f"护城河评级: {moat_rating}",
        factor_1c_summary="增长质量评估完成",
        factor_2_gg=factor2.get("gg", factor2.get("R_NP_tax", 0)),
        factor_3_gg=gg_base,
        factor_3_gg_scenarios=gg_scenarios,
        factor_4_ddm_v=ddm_v,
        factor_4_current_price=current_price,
        factor_4_position_pct=position_pct,
        ii=ii,
        rf=rf,
        key_risks=key_risks,
        rejection_status=rejection_status,
        moat_rating=moat_rating,
    )


def validate_decision(decision: DecisionOutput, di: DecisionInput) -> list[str]:
    """验证决策是否与因子评估一致，返回不一致项列表。

    Args:
        decision: 决策输出。
        di: 决策输入数据。

    Returns:
        不一致问题列表（空列表 = 一致）。
    """
    issues: list[str] = []

    # 检查 GG > II 但决策不是 Continue
    if di.factor_3_gg > di.ii and di.factor_3_gg > 0 and decision.verdict == "Abandon":
        issues.append(f"GG({di.factor_3_gg}%) > II({di.ii}%)，但决策为 Abandon——需要充分理由")

    # 检查 GG < II×0.5 但决策是 Continue
    if di.factor_3_gg < di.ii * 0.5 and di.factor_3_gg > 0 and decision.verdict == "Continue":
        issues.append(f"GG({di.factor_3_gg}%) < II×0.5({di.ii*0.5}%)，但决策为 Continue——需要充分理由")

    # 检查否决门触发但决策不是 Abandon
    if di.rejection_status and "触发" in str(di.rejection_status) and decision.verdict != "Abandon":
        issues.append(f"否决门触发({di.rejection_status})，但决策为 {decision.verdict}")

    # 检查 DDM 公允价远低于当前价但决策是 Continue
    if di.factor_4_ddm_v > 0 and di.factor_4_current_price > 0:
        premium = (di.factor_4_current_price - di.factor_4_ddm_v) / di.factor_4_ddm_v
        if premium > 0.3 and decision.verdict == "Continue":
            issues.append(f"当前价溢价{premium*100:.0f}%超过DDM公允价，但决策为 Continue")

    return issues


def _rule_based_synthesis(di: DecisionInput) -> DecisionOutput:
    """基于规则的综合决策（确定性，不依赖 LLM）。

    规则优先级：
    1. 否决门触发 → Abandon
    2. GG < II×0.5 → Abandon
    3. GG > II → Continue
    4. 其余 → Hold

    Args:
        di: 决策输入数据。

    Returns:
        DecisionOutput 对象。
    """
    # 提取 GG（处理可能的不同格式）
    gg = di.factor_3_gg if di.factor_3_gg > 0 else di.factor_2_gg
    ii = di.ii

    rationale: list[str] = []
    triggers: list[str] = []
    exit_conditions: list[str] = []

    # 规则 1: 否决门
    if di.rejection_status and "触发" in str(di.rejection_status):
        verdict = "Abandon"
        confidence = "high"
        rationale = [
            f"否决门触发: {di.rejection_status}",
            f"GG({gg}%) vs II({ii}%)",
        ]
    # 规则 2: GG 远低于 II
    elif ii > 0 and gg < ii * 0.5:
        verdict = "Abandon"
        confidence = "high"
        rationale = [
            f"GG({gg}%) < II×0.5({ii*0.5}%)——穿透回报率显著不足",
            f"护城河: {di.moat_rating}",
        ]
    # 规则 3: GG > II
    elif ii > 0 and gg > ii:
        # 检查估值安全边际
        if di.factor_4_ddm_v > 0 and di.factor_4_current_price > 0:
            margin = (di.factor_4_ddm_v - di.factor_4_current_price) / di.factor_4_current_price
        else:
            margin = 0

        if margin > 0.15:
            verdict = "Continue"
            confidence = "high"
            rationale = [
                f"GG({gg}%) > II({ii}%)",
                f"DDM公允价溢价{margin*100:.0f}%——具备安全边际",
                f"护城河: {di.moat_rating}",
            ]
        else:
            verdict = "Continue"
            confidence = "medium"
            rationale = [
                f"GG({gg}%) > II({ii}%)——穿透回报率达标",
                f"安全边际{margin*100:.0f}%（需跟踪价格变化）",
                f"护城河: {di.moat_rating}",
            ]
            triggers.append(f"若股价上涨超过 DDM 公允价 {di.factor_4_ddm_v}，降级为 Hold")
    # 规则 4: 其余情况 → Hold
    else:
        verdict = "Hold"
        confidence = "medium"
        rationale = [
            f"GG({gg}%) 在 II×0.5({ii*0.5 if ii > 0 else '?'}%) ~ II({ii}%) 之间",
            f"需进一步观察或等待更好价格",
            f"护城河: {di.moat_rating}",
        ]
        triggers.append(f"若 GG 下降至 < {ii*0.5 if ii > 0 else '?'}%，降级为 Abandon")
        triggers.append(f"若股价跌至 DDM 公允价以下，可考虑升级为 Continue")

    # 通用退出条件
    exit_conditions = [
        f"GG < Rf({di.rf}%)",
        "护城河评级降为 None",
        "管理层出现重大治理负面",
        "核心业务发生不可逆恶化",
    ]

    if di.moat_rating in ("Weak", "None"):
        exit_conditions.insert(0, f"护城河持续弱化（当前: {di.moat_rating}）")

    return DecisionOutput(
        verdict=verdict,
        confidence=confidence,
        rationale=rationale,
        assumptions=[
            {"assumption": "历史财务趋势将持续", "impact_if_wrong": "GG 估算可能偏高", "probability": "medium"},
            {"assumption": "管理层无未披露的重大负面", "impact_if_wrong": "投资逻辑可能完全失效", "probability": "low"},
        ],
        triggers=triggers,
        exit_conditions=exit_conditions,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="综合各章结果生成投资决策")
    ap.add_argument("--code", required=True, help="股票代码")
    ap.add_argument("--output", help="股票输出目录")
    args = ap.parse_args()

    # 加载上下文
    stock_dir = args.output
    if not stock_dir:
        code_base = args.code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
        default_output = os.path.join(os.path.dirname(__file__), "..", "output")
        for name in os.listdir(default_output):
            if name.startswith(code_base):
                stock_dir = os.path.join(default_output, name)
                break

    if not stock_dir or not os.path.isdir(stock_dir):
        print(f"ERROR: 找不到输出目录", file=sys.stderr)
        sys.exit(1)

    # 加载数据文件
    context = {}
    for fname in os.listdir(stock_dir):
        if fname.endswith(".json"):
            key = fname.replace(".json", "")
            path = os.path.join(stock_dir, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    context[key] = json.load(f)
            except Exception:
                pass

    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), "..", "stock_analysis.db")
    company_name = args.code
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT name_cn FROM stocks WHERE ts_code=?", (args.code,)).fetchone()
        conn.close()
        if row:
            company_name = row[0]
    except Exception:
        pass

    di = build_decision_input_from_context(context, company_name, args.code)
    decision = synthesize_decision(di)

    print(f"\n{'='*50}")
    print(f"投资决策: {di.company_name} ({di.ts_code})")
    print(f"{'='*50}")
    print(f"决策: {decision.verdict}")
    print(f"置信度: {decision.confidence}")
    print(f"\n核心依据:")
    for i, r in enumerate(decision.rationale, 1):
        print(f"  {i}. {r}")
    print(f"\n监控触发器:")
    for t in decision.triggers:
        print(f"  - {t}")
    print(f"\n退出条件:")
    for e in decision.exit_conditions:
        print(f"  - {e}")

    # 验证一致性
    issues = validate_decision(decision, di)
    if issues:
        print(f"\n⚠️ 一致性警告:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"\n✅ 决策与分析结果一致")
