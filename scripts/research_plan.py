#!/usr/bin/env python3
"""Deterministic chapter research plans for v13 reports.

The plan is deliberately question-led.  It tells the writer why a source is
needed and what counter-evidence must be tested, instead of rewarding a bare
tool call.  The same topic identities are reused by semantic gold regression.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any


def _topic(topic_id: str, question: str, *keywords: str) -> dict[str, Any]:
    return {"id": topic_id, "question": question, "keywords": list(keywords)}


CHAPTER_RESEARCH_SPECS: dict[int, dict[str, Any]] = {
    0: {"sections": ["MDA", "STMT", "NOTES"], "tools": ["compute_gg", "compute_ddm"], "topics": [
        _topic("thesis", "一句话投资逻辑及其最强证据是什么？", "投资逻辑", "核心判断", "一眼看懂"),
        _topic("conflict", "定性与定量结论在哪里冲突，如何裁决？", "定性", "定量", "冲突", "裁决"),
        _topic("trigger", "什么价格或经营信号会改变结论？", "触发", "买入价", "P*", "监控"),
        _topic("downside", "核心下行风险和否决条件是什么？", "风险", "否决", "下行"),
    ]},
    1: {"sections": ["MDA", "SEG"], "tools": ["read_zone_data"], "topics": [
        _topic("revenue_engine", "公司靠什么产品、客户和地区赚钱？", "收入", "产品", "客户", "地区"),
        _topic("economics", "单位经济性和价值链位置如何？", "毛利率", "价值链", "供应商", "渠道"),
        _topic("concentration", "主业集中度与多元化是否真实？", "集中", "主业", "多元化", "分部"),
    ]},
    2: {"sections": ["MDA", "SEG"], "tools": ["web_search", "web_fetch", "get_peer_comparison"], "topics": [
        _topic("structure", "行业规模、增速和周期位置如何？", "行业", "增速", "周期", "渗透率"),
        _topic("position", "公司份额、价格带和相对位置如何？", "市占率", "份额", "排名", "价格"),
        _topic("competition", "主要竞争者以什么机制威胁公司？", "竞争", "对手", "小米", "美的"),
        _topic("externality", "政策、原材料或技术变化如何传导？", "政策", "原材料", "技术", "传导"),
    ]},
    3: {"sections": ["MDA", "SEG"], "tools": ["read_zone_data"], "topics": [
        _topic("moat", "护城河由什么机制形成而非只是什么标签？", "护城河", "品牌", "规模", "网络"),
        _topic("evidence", "超额回报有哪些量化证据？", "溢价", "毛利率", "ROIC", "超额"),
        _topic("erosion", "护城河怎样被侵蚀，领先指标是什么？", "侵蚀", "衰减", "约束", "领先指标"),
        _topic("counter", "最强反证是什么？", "反证", "替代", "失效"),
    ]},
    4: {"sections": ["MDA", "RISK"], "tools": ["search_report"], "topics": [
        _topic("change", "最近一年发生了哪些可量化变化？", "同比", "变化", "下降", "增长"),
        _topic("phase", "这些变化是周期、结构还是会计扰动？", "周期", "结构", "扰动", "阶段"),
        _topic("signal", "最新经营信号是否确认拐点？", "季度", "拐点", "信号", "合同负债"),
    ]},
    5: {"sections": ["MDA", "STMT", "SEG"], "tools": ["get_financial_trends"], "topics": [
        _topic("trend", "收入利润的多年趋势与驱动是什么？", "营收", "净利润", "趋势", "驱动"),
        _topic("margin", "毛利率和费用率为什么变化？", "毛利率", "费用率", "价格", "成本"),
        _topic("cash", "利润是否转化为现金？", "OCF", "现金流", "OCF/NP", "含金量"),
        _topic("segment", "哪个分部解释了主要变化？", "分部", "内销", "外销", "主业"),
    ]},
    6: {"sections": ["STMT", "NOTES"], "tools": ["compute_aa", "get_financial_trends"], "topics": [
        _topic("balance", "现金、债务和营运资本的真实结构如何？", "现金", "债务", "营运资本", "合同负债"),
        _topic("capex", "资本开支是维持性还是增长性？", "资本开支", "Capex", "折旧", "维持性"),
        _topic("allocation", "分红、回购和投资的资本配置效率如何？", "资本配置", "分红", "回购", "投资"),
        _topic("quality", "会计利润有哪些需要归一化的项目？", "归一化", "减值", "一次性", "应付账款"),
    ]},
    7: {"sections": ["STMT", "NOTES", "GOV"], "tools": ["compute_ddm"], "topics": [
        _topic("dividend", "分红能力、意愿和约束分别如何？", "DPS", "分红", "派息", "承诺"),
        _topic("buyback", "回购是否注销并真正增厚每股价值？", "回购", "注销", "股本", "增厚"),
        _topic("sustainability", "股东回报在压力情景下能否持续？", "持续", "覆盖", "压力", "自由现金流"),
    ]},
    8: {"sections": ["GOV", "NOTES"], "tools": ["read_zone_data", "web_search", "web_fetch"], "topics": [
        _topic("control", "控制权、董事会和关键人结构如何？", "控制权", "董事会", "关键人", "接班"),
        _topic("incentive", "激励与股东利益是否一致？", "激励", "员工持股", "股份支付", "薪酬"),
        _topic("related", "关联交易、担保和低效投资有什么约束？", "关联交易", "担保", "格力钛", "减值"),
        _topic("counter", "治理改善与恶化的相反证据分别是什么？", "改善", "反证", "审计", "承诺"),
    ]},
    9: {"sections": ["RISK", "NOTES"], "tools": ["search_report"], "topics": [
        _topic("risk_chain", "风险如何从事件传导到利润、现金和估值？", "传导", "利润", "现金", "估值"),
        _topic("veto", "哪些条件构成否决项？", "否决", "红线", "触发"),
        _topic("monitor", "每项风险用什么领先指标监控？", "领先指标", "监控", "阈值"),
        _topic("counter", "哪些缓冲因素可能使风险不兑现？", "缓冲", "对冲", "反证"),
    ]},
    10: {"sections": ["STMT", "NOTES"], "tools": ["get_financial_trends", "compute_gg"], "topics": [
        _topic("growth", "历史增长中多少可持续？", "增长", "CAGR", "可持续", "归一化"),
        _topic("scenario", "悲观、基准、乐观参数依据是什么？", "悲观", "基准", "乐观", "情景"),
        _topic("bridge", "经营事实如何映射到估值参数？", "参数", "映射", "g", "II"),
    ]},
    11: {"sections": ["STMT", "NOTES"], "tools": ["compute_aa", "compute_gg"], "topics": [
        _topic("identity", "AA、FCFE、Normalized GG口径为何不同？", "AA", "FCFE", "Normalized", "口径"),
        _topic("formula", "GG各参数和公式如何逐步推导？", "公式", "推导", "M", "HH"),
        _topic("stress", "关键参数压力测试结果如何？", "敏感", "压力", "情景"),
        _topic("distortion", "应付账款、少数股东和治理折价如何处理？", "AP", "少数股东", "治理折价", "λ"),
    ]},
    12: {"sections": ["STMT", "NOTES"], "tools": ["compute_gg", "compute_ddm"], "topics": [
        _topic("methods", "AV、EPV、DDM和P_base分别回答什么？", "AV", "EPV", "DDM", "P_base"),
        _topic("conflict", "方法分歧来自哪些假设，如何裁决？", "分歧", "冲突", "裁决", "权重"),
        _topic("sensitivity", "价值对增长、折现率和衰减多敏感？", "敏感", "折现", "增长", "衰减"),
        _topic("margin", "价格与价值安全边际如何区分？", "安全边际", "V_final", "回报安全边际"),
    ]},
    13: {
        "sections": ["STMT", "NOTES"],
        # Some HK annual reports do not expose a stable NOTES boundary in the
        # generated page map.  A failed NOTES read may therefore be replaced
        # by targeted searches of the same official annual-report bodies, but
        # only when the agent records the failed read and covers two fiscal
        # years.  This is an auditable fallback, not a waiver of primary-source
        # research.
        "section_search_fallbacks": {"NOTES": {"minimum_calls": 2, "minimum_years": 2}},
        "tools": ["compute_ddm", "get_market_data"], "topics": [
        _topic("ddm", "股息路径和DDM假设如何推导？", "DPS", "DDM", "折现", "终值"),
        _topic("return", "目标回报率如何反推买入价？", "P*", "目标回报", "买入价", "反推"),
        _topic("position", "安全边际如何映射到仓位和阶梯？", "仓位", "阶梯", "安全边际"),
        _topic("downside", "股息削减或估值压缩时损失多大？", "削减", "下行", "压力", "回撤"),
    ]},
    14: {"sections": ["MDA", "RISK", "STMT", "NOTES"], "tools": ["compute_gg", "compute_ddm"], "topics": [
        _topic("synthesis", "定性、定量和价格结论怎样合成？", "定性", "定量", "合成", "决策"),
        _topic("conflict", "冲突裁决规则和被否决路线是什么？", "冲突", "裁决", "否决", "拒绝"),
        _topic("execution", "当前动作、仓位和价格触发器是什么？", "动作", "仓位", "触发", "买入"),
        _topic("monitor", "未来更新结论需要跟踪什么？", "监控", "跟踪", "复核", "阈值"),
    ]},
}

_EXAMPLE_PATTERNS = {
    "causal_chain": "事实变化→经营机制→利润/现金流→估值或决策",
    "counter_evidence": "主判断+支持证据+最强反证+区分指标",
    "falsifiable_trigger": "若指标越过阈值，则上调/下调/否决判断",
    "valuation_conflict": "方法差异→假设差异→可信路线→拒绝理由",
}


def _example_ids(chapter_index: int) -> list[str]:
    result = ["causal_chain", "counter_evidence"]
    if chapter_index in {0, 4, 7, 9, 13, 14}:
        result.append("falsifiable_trigger")
    if chapter_index in {0, 10, 11, 12, 13, 14}:
        result.append("valuation_conflict")
    return result


def available_annual_years(output_dir: str) -> list[int]:
    try:
        names = os.listdir(output_dir)
    except OSError:
        return []
    return sorted(
        int(match.group(1))
        for name in names
        if (match := re.fullmatch(r"(20\d{2})_年报\.md", name))
    )


def build_research_plan(output_dir: str, chapter_indexes: list[int] | None = None) -> dict[str, Any]:
    indexes = [int(i) for i in (chapter_indexes if chapter_indexes is not None else range(15))]
    years = available_annual_years(output_dir)
    fiscal_years = list(reversed(years[-2:]))
    chapters: dict[str, Any] = {}
    for idx in indexes:
        spec = CHAPTER_RESEARCH_SPECS.get(idx)
        if spec is None:
            raise ValueError(f"无效章节: Ch{idx}")
        chapters[str(idx)] = {
            "chapter_index": idx,
            "primary_sections": spec["sections"],
            "preferred_fiscal_years": fiscal_years,
            "required_tools": spec["tools"],
            "research_questions": [topic["question"] for topic in spec["topics"]],
            "topic_checks": spec["topics"],
            "reasoning_examples": [
                {"id": example_id, "pattern": _EXAMPLE_PATTERNS[example_id]}
                for example_id in _example_ids(idx)
            ],
            "completion_checklist": [
                "每个研究问题均有明确结论或数据缺口",
                "至少一条支持证据与一条反证/替代解释",
                "关键数字可追溯到原文、结构化真源或确定性计算",
                "事实→机制→财务影响→估值/决策影响形成闭环",
            ],
        }
    return {
        "version": 1,
        "output_dir": output_dir,
        "available_annual_years": years,
        "chapter_indexes": indexes,
        "chapters": chapters,
    }


def topic_presence(content: str, chapter_index: int) -> dict[str, bool]:
    return {
        topic["id"]: any(keyword.lower() in content.lower() for keyword in topic["keywords"])
        for topic in CHAPTER_RESEARCH_SPECS[int(chapter_index)]["topics"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 v13 章节研究计划")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--chapters", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    indexes = [int(x) for x in args.chapters.split(",") if x.strip()] or None
    plan = build_research_plan(args.output_dir, indexes)
    path = Path(args.output or Path(args.output_dir) / "research_plan.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
