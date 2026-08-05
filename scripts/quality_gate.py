#!/usr/bin/env python3
"""quality_gate.py — report structural quality gate."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

LEGACY_REQUIRED = [
    ("报告元信息", "报告元信息"),
    ("Executive Summary", "Executive Summary"),
    ("财务趋势", "财务趋势"),
    ("因子1A", "因子1A"), ("因子1B", "因子1B"), ("因子1C", "因子1C"),
    ("因子2/3", "因子2"), ("因子4", "因子4"),
    ("风险", "风险"), ("投资决策", "投资决策"), ("来源清单", "来源清单"),
]

ANOMALY_KEYWORDS = ["扭曲", "不可持续", "失真", "异常", "偏离", "虚增"]
MITIGATION_KEYWORDS = ["保守", "风险提示", "谨慎", "有条件", "警告", "下调"]


def _check_anomaly_propagation(text: str) -> bool:
    has_anomaly = any(kw in text for kw in ANOMALY_KEYWORDS)
    if not has_anomaly:
        return True
    return any(kw in text for kw in MITIGATION_KEYWORDS)


def _check_dps_consistency(text: str) -> bool:
    # Historical DPS series are legitimate. Only flag contradictory values that
    # are both explicitly presented as the current/latest DPS identity.
    current_mentions = re.findall(
        r'(?:当前|最新|本期)\s*(?:常规)?\s*DPS\s*[=：:]?\s*(\d+(?:\.\d+)?)',
        text,
        flags=re.IGNORECASE,
    )
    return len({round(float(value), 6) for value in current_mentions}) <= 1


def _check_variable_residue(text: str) -> bool:
    residues = re.findall(r'\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}', text)
    if residues:
        unique = list(set(residues))[:10]
        print(f"  ⚠️ 未解析变量: {unique}", file=sys.stderr)
        return False
    return True


def _detect_version(text: str) -> str:
    return "v13" if re.search(r"^##\s+Ch1\b", text, flags=re.M) else "legacy"


def _v13_checks(text: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    blocks: list[str] = []
    warns: list[str] = []
    chapter_headers = re.findall(r'^##\s+Ch(\d+)\b', text, flags=re.M)
    chapter_indexes = [int(idx) for idx in chapter_headers if int(idx) != 0]
    expected = list(range(1, 15))
    has_overview = bool(re.search(r"^##\s+(?:Ch0\s+)?投资要点概览\s*$", text, flags=re.M))
    structure_ok = chapter_indexes == expected and has_overview and '## 来源清单' in text
    checks.append({"name": "v13_structure", "status": "PASS" if structure_ok else "FAIL", "severity": "BLOCK"})
    if not structure_ok:
        blocks.append('v13_structure')
    checks.append({"name": "source_list", "status": "PASS" if '## 来源清单' in text else "FAIL", "severity": "BLOCK"})
    if '## 来源清单' not in text:
        blocks.append('source_list')
    return checks, blocks, warns


def check(text: str, report_version: str | None = None) -> dict[str, Any]:
    version = report_version or _detect_version(text)
    result = {"status": "PASS", "checks": [], "blocks": [], "warns": [], "lines": len(text.splitlines()), "report_version": version}
    if version == 'v13':
        checks, blocks, warns = _v13_checks(text)
        result['checks'].extend(checks)
        result['blocks'].extend(blocks)
        result['warns'].extend(warns)
    else:
        for name, pattern in LEGACY_REQUIRED:
            ok = bool(re.search(pattern, text))
            result['checks'].append({"name": name, "status": "PASS" if ok else "FAIL", "severity": "BLOCK"})
            if not ok:
                result['blocks'].append(name)
    for name, sev, fn in [
        ("ES_filled", "BLOCK", lambda t: "C4_PLACEHOLDER" not in t),
        ("has_tables", "WARN", lambda t: len(re.findall(r'\|.*\|.*\|', t)) >= 20),
        ("rejection_summary", "WARN", lambda t: "否决门总览" in t or "否决项" in t),
        ("factor3_AA", "WARN", lambda t: any(x in t for x in ("AA序列", "AA 序列", "AA逐年", "AA 逐年", "AA（可支配现金）逐年"))),
        ("factor2_Q_tax", "WARN", lambda t: "Q税率" in t or "三档" in t),
        ("anomaly_propagation", "WARN", _check_anomaly_propagation),
        ("dps_consistency", "WARN", _check_dps_consistency),
        ("variable_residue", "BLOCK", _check_variable_residue),
    ]:
        ok = fn(text)
        result['checks'].append({"name": name, "status": "PASS" if ok else "FAIL", "severity": sev})
        if not ok:
            (result['blocks'] if sev == 'BLOCK' else result['warns']).append(name)
    # Physical line count is a formatting property. Chapter-level semantic
    # depth is enforced by report_completion; retain only a catastrophic
    # whole-report guard for legacy callers.
    substantive_chars = len(re.sub(r"\s+|[#|`*_~>-]", "", text))
    result["substantive_chars"] = substantive_chars
    if substantive_chars < 20_000:
        result['blocks'].append(f"SubstantiveChars:{substantive_chars}<20000")
    if result['blocks']:
        result['status'] = 'BLOCKED'
    elif result['warns']:
        result['status'] = 'WARN'
    return result


def _default_report_path(stock_dir: str) -> str | None:
    reports_dir = os.path.join(stock_dir, 'reports')
    if os.path.isdir(reports_dir):
        candidates = sorted(Path(reports_dir).glob('*.md'))
        if candidates:
            return str(candidates[-1])
    candidates = sorted(Path(stock_dir).glob('*.md'))
    return str(candidates[-1]) if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--code', required=True)
    parser.add_argument('--report')
    parser.add_argument('--output')
    args = parser.parse_args()
    stock_dir = args.output or next((os.path.join(OUTPUT_BASE, d) for d in os.listdir(OUTPUT_BASE) if os.path.isdir(os.path.join(OUTPUT_BASE, d)) and d.startswith(args.code.replace('.HK', '').replace('.SH', '').replace('.SZ', ''))), None)
    if not stock_dir:
        print('ERROR: no dir', file=sys.stderr)
        return 1
    report_path = args.report or _default_report_path(stock_dir)
    if not report_path:
        print('ERROR: no report', file=sys.stderr)
        return 1
    text = Path(report_path).read_text(encoding='utf-8')
    res = check(text)
    Path(os.path.join(stock_dir, 'quality_gate_report.json')).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
    icon = {'PASS': '✅', 'WARN': '⚠️', 'BLOCKED': '❌'}[res['status']]
    print(f"{icon} Quality: {res['status']} | {res['lines']} lines | version={res['report_version']}")
    for b in res['blocks']:
        print(f"  ❌ {b}")
    for w in res['warns']:
        print(f"  ⚠️ {w}")
    return 0 if res['status'] != 'BLOCKED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
