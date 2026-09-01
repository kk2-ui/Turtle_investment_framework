#!/usr/bin/env python3
"""report_audit.py — Turtle 报告抽样审计工具。"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from random import Random
from typing import Any

_TOLERANCE_WARN = 0.005
_TOLERANCE_FAIL = 0.01
_KV_RE = re.compile(
    r'(?P<label>[A-Za-z一-龥][^\n：:|]{0,40})[：:]\s*[~约]?\$?'
    r'(?P<num>[\d,，\.]+)\s*(?P<unit>%|x|X|倍|港元|HKD|元|亿元|亿)?'
)
_TABLE_RE = re.compile(
    r'^\|\s*(?P<label>[^|]{1,40})\s*\|\s*[~约]?\$?'
    r'(?P<num>[\d,，\.]+)\s*(?P<unit>%|x|X|倍|港元|HKD|元|亿元|亿)?\s*\|'
)

FIELD_SPECS = [
    {
        "field": "II",
        "label_patterns": [r'^II$', r'^II（', r'^II\('],
        "getter": lambda b: (b.get("params", {}) or {}).get("II"),
    },
    {
        "field": "Rf",
        "label_patterns": [r'^Rf$', r'^Rf（', r'^Rf\('],
        "getter": lambda b: (b.get("params", {}) or {}).get("Rf"),
    },
    {
        "field": "GG",
        "label_patterns": [r'^GG$', r'^GG\(', r'精算GG', r'GG_base'],
        "getter": lambda b: (((b.get("factor3", {}) or {}).get("gg", {}) or {}).get("base")),
    },
    {
        "field": "GG_FCFE",
        "label_patterns": [r'FCFE\s*GG', r'GG\(FCFE'],
        "getter": lambda b: (((b.get("factor3", {}) or {}).get("gg_fcfe", {}) or {}).get("base")),
    },
    {
        "field": "GG_NORMALIZED",
        "label_patterns": [r'Normalized\s*GG', r'GG\(Normalized'],
        "getter": lambda b: (((b.get("factor3", {}) or {}).get("gg_normalized", {}) or {}).get("base")),
    },
    {
        "field": "DDM",
        "label_patterns": [r'^DDM$', r'^DDM理论值', r'^DDM理论公允价'],
        "getter": lambda b: ((b.get("factor4", {}) or {}).get("ddm_v_hkd")),
    },
    {
        "field": "P_BASE",
        "label_patterns": [r'^P[_ ]?base$', r'^P[_ ]?base\(GG=II\)$', r'^Pbase\(GG=II\)$'],
        "getter": lambda b: ((((b.get("factor4", {}) or {}).get("p_base", {}) or {}).get("price_hkd"))),
    },
    {
        "field": "P_BASE_DISCOUNTED",
        "label_patterns": [r'^P[_ ]?base折价后$'],
        "getter": lambda b: ((((b.get("factor4", {}) or {}).get("p_base", {}) or {}).get("p_base_discounted_hkd"))),
    },
    {
        "field": "P_FCFE",
        "label_patterns": [r'^FCFE P[_ ]?base$'],
        "getter": lambda b: (((((b.get("factor4", {}) or {}).get("p_base", {}) or {}).get("p_fcfe", {}) or {}).get("price_hkd"))),
    },
]


def _clean_num(raw: str) -> float | None:
    try:
        return float(raw.replace(",", "").replace("，", "").strip())
    except ValueError:
        return None


def _classify_metric(label: str, raw_text: str) -> tuple[str, list[str]]:
    normalized = re.sub(r"[\s_*`（）()：:]+", "", label).lower()
    context = raw_text.lower()
    tags: list[str] = []
    # P_base 的解释性标签常写成「P_base（GG=II 公允价）」；这里的 GG 是
    # 定价条件，不是该单元格的指标身份。必须先于通用 GG 分类。
    if normalized.startswith('pbase'):
        # 「无保护」明确表示原始 P_base。不能因为字符串仍含“保护”二字
        # 就落到 25% 保护折价口径。
        if '无保护' in normalized or '未保护' in normalized or 'undiscounted' in normalized:
            return 'P_BASE', ['price', 'undiscounted']
        if 'discount' in normalized or '折价' in raw_text or '保护' in normalized:
            return 'P_BASE_DISCOUNTED', ['price', 'discounted']
        return 'P_BASE', ['price']
    if normalized.startswith('pfcfe') or normalized.startswith('fcfepbase'):
        return 'P_FCFE', ['price', 'fcfe']
    # A prose key such as ``...P_FCFE...综合区间: 2.28`` merely mentions GG
    # inside its explanation.  Only a key whose identity begins with GG (or a
    # named GG variant) may be reconciled as a GG observation.
    if re.match(r'^(?:gg|精算gg|fcfegg|normalizedgg)', normalized):
        if 'fcfe' in normalized or 'fcfe' in context:
            tags.append('fcfe')
        if 'normalized' in normalized or 'normalized' in context:
            tags.append('normalized')
        if 'discount' in normalized or '折价' in raw_text:
            tags.append('discounted')
        if 'base' in normalized or '基准' in raw_text or 'AA口径' in raw_text:
            tags.append('base')
        if not tags:
            tags.append('generic_gg')
        return 'GG', tags
    if 'ocf/np' in normalized:
        if 'p' in normalized or 'percentile' in context or 'p60' in context:
            return 'OCF_NP_percentile', ['percentile']
        return 'OCF_NP_ratio', ['ratio']
    return '', tags


def extract_data_points(report_text: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    seen: set[tuple[str, float, int]] = set()
    lines = report_text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("```") or stripped.startswith("#"):
            continue
        matchers = list(_KV_RE.finditer(stripped))
        table_match = _TABLE_RE.search(stripped)
        if table_match:
            matchers.append(table_match)
        for match in matchers:
            label = re.sub(r'[\*_`]+', '', (match.group('label') or '').strip())
            value = _clean_num(match.group('num') or '')
            if not label or value is None:
                continue
            key = (label, round(value, 4), lineno)
            if key in seen:
                continue
            seen.add(key)
            inferred_field, metric_tags = _classify_metric(label, stripped[:180])
            points.append({
                'id': len(points) + 1,
                'label': label,
                'reported_value': value,
                'unit': (match.groupdict().get('unit') or '').strip(),
                'raw_text': stripped[:180],
                'line_number': lineno,
                'inferred_field': inferred_field,
                'metric_tags': metric_tags,
            })
    return points


def sample_points(points: list[dict[str, Any]], ratio: float = 0.15, seed: int = 7) -> list[dict[str, Any]]:
    if not points:
        return []
    n = max(3, min(30, math.ceil(len(points) * ratio)))
    n = min(n, len(points))
    sampled = Random(seed).sample(points, n)
    return sorted(sampled, key=lambda item: item['line_number'])


def _expected_candidates(compute_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for spec in FIELD_SPECS:
        expected = spec['getter'](compute_bundle)
        if expected is None:
            continue
        candidates.append({
            'field': spec['field'],
            'expected': float(expected),
            'label_patterns': spec['label_patterns'],
        })
    return candidates


def _match_candidate(point: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    label = point['label'].strip()
    inferred = point.get('inferred_field')
    tags = set(point.get('metric_tags', []))
    if inferred == 'GG':
        # Discounted/scenario GG is a separate decision-layer view, not the
        # canonical AA/base GG identity. It has no FIELD_SPEC candidate and
        # must never fall through merely because its label also contains base.
        if 'discounted' in tags:
            return None
        for candidate in candidates:
            field = candidate['field']
            if field == 'GG' and 'base' in tags:
                return candidate
            if field == 'GG_FCFE' and 'fcfe' in tags:
                return candidate
            if field == 'GG_NORMALIZED' and 'normalized' in tags:
                return candidate
        return None
    if inferred == 'P_BASE':
        return next((candidate for candidate in candidates if candidate['field'] == 'P_BASE'), None)
    if inferred == 'P_BASE_DISCOUNTED':
        return next((candidate for candidate in candidates if candidate['field'] == 'P_BASE_DISCOUNTED'), None)
    if inferred == 'P_FCFE':
        return next((candidate for candidate in candidates if candidate['field'] == 'P_FCFE'), None)
    if inferred == 'OCF_NP_percentile':
        return None
    for candidate in candidates:
        for pattern in candidate['label_patterns']:
            if re.search(pattern, label, re.IGNORECASE):
                return candidate
    return None


def _pct_diff(reported: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if abs(reported) < 1e-12 else 1.0
    return abs(reported - expected) / abs(expected)


def audit_report_against_bundle(
    report_text: str,
    compute_bundle: dict[str, Any],
    ratio: float = 0.15,
    seed: int = 7,
) -> dict[str, Any]:
    extracted = extract_data_points(report_text)
    candidates = _expected_candidates(compute_bundle)
    matched = []
    for point in extracted:
        candidate = _match_candidate(point, candidates)
        if candidate is None:
            continue
        matched.append({**point, 'field': candidate['field'], 'expected_value': candidate['expected']})

    sampled = sample_points(matched, ratio=ratio, seed=seed)
    items = []
    pass_count = warn_count = fail_count = 0
    for point in sampled:
        deviation = _pct_diff(point['reported_value'], point['expected_value'])
        if deviation > _TOLERANCE_FAIL:
            status = 'FAIL'
            fail_count += 1
        elif deviation > _TOLERANCE_WARN:
            status = 'WARN'
            warn_count += 1
        else:
            status = 'PASS'
            pass_count += 1
        items.append({
            'field': point['field'],
            'label': point['label'],
            'reported': point['reported_value'],
            'expected': point['expected_value'],
            'deviation_pct': round(deviation * 100, 4),
            'status': status,
            'line_number': point['line_number'],
            'raw_text': point['raw_text'],
        })

    verdict = 'FAIL' if fail_count else 'PASS'
    return {
        'verdict': verdict,
        'extracted_count': len(extracted),
        'matched_count': len(matched),
        'sampled_count': len(sampled),
        'pass_count': pass_count,
        'warn_count': warn_count,
        'fail_count': fail_count,
        'items': items,
    }


def load_json(path: str) -> dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _read_text(path: str) -> str:
    with open(path, encoding='utf-8') as f:
        return f.read()


def main() -> int:
    parser = argparse.ArgumentParser(description='Turtle 报告抽样审计工具')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_extract = sub.add_parser('extract', help='抽取报告中的数据点')
    p_extract.add_argument('--report', required=True)
    p_extract.add_argument('--ratio', type=float, default=0.15)
    p_extract.add_argument('--seed', type=int, default=7)

    p_audit = sub.add_parser('audit', help='对报告执行抽样审计')
    p_audit.add_argument('--report', required=True)
    p_audit.add_argument('--compute-bundle', required=True)
    p_audit.add_argument('--ratio', type=float, default=0.15)
    p_audit.add_argument('--seed', type=int, default=7)
    p_audit.add_argument('--output', help='输出 JSON 文件')

    p_verdict = sub.add_parser('verdict', help='对现成的 audit 结果给出判决')
    p_verdict.add_argument('--results', required=True, help='JSON 字符串或 JSON 文件路径')

    args = parser.parse_args()

    if args.cmd == 'extract':
        report_text = _read_text(args.report)
        extracted = extract_data_points(report_text)
        sampled = sample_points(extracted, ratio=args.ratio, seed=args.seed)
        print(json.dumps({'extracted_count': len(extracted), 'sampled': sampled}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == 'audit':
        report_text = _read_text(args.report)
        bundle = load_json(args.compute_bundle)
        result = audit_report_against_bundle(report_text, bundle, ratio=args.ratio, seed=args.seed)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result['verdict'] == 'FAIL' else 0

    results_arg = args.results
    if os.path.exists(results_arg):
        result = load_json(results_arg)
    else:
        result = json.loads(results_arg)
    verdict = 'FAIL' if result.get('fail_count', 0) else 'PASS'
    summary = {
        'verdict': verdict,
        'pass_count': result.get('pass_count', 0),
        'warn_count': result.get('warn_count', 0),
        'fail_count': result.get('fail_count', 0),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if verdict == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
