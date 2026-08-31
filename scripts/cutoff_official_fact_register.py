#!/usr/bin/env python3
"""Validate cutoff-bound facts located in official PDF sources.

The v1 JSON shape is intentionally small::

    {
      "schema_version": "turtle-cutoff-official-fact-register.v1",
      "cutoff_at": "2018-04-30",
      "sources": [{
        "source_id": "FY2017",
        "static_url": "https://example.gov/reports/fy2017.pdf",
        "available_at": "2018-04-10",
        "declared_pages": 120
      }],
      "observations": [{
        "source_id": "FY2017", "pdf_page": 18,
        "table_or_section": "Revenue by segment", "field": "revenue",
        "period": "FY2017", "responsibility_boundary": "consolidated",
        "unit": "CNY million"
      }],
      "required_series": [{
        "series_id": "revenue_history",
        "fields": ["revenue"], "periods": ["FY2015", "FY2016", "FY2017"],
        "responsibility_boundary": "consolidated", "unit": "CNY million"
      }]
    }

``required_series`` is optional.  When present, every field/period pair must
have an observation; the optional boundary and unit narrow the matching
observations.

``v1`` is a page-locator register: it is deliberately value-free and remains
the right shape for a cutoff source package.  ``v2`` is the canonical-fact
extension consumed by valuation models.  It requires each observation to have
a stable ``fact_id`` and an exact disclosed ``value`` in addition to the same
source, page, date, unit and responsibility-boundary contract.  A caller's
``status=VERIFIED`` flag is not a substitute for a v2 observation.

This module performs no network or PDF access.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit


SCHEMA_VERSION = "turtle-cutoff-official-fact-register.v1"
CANONICAL_FACT_SCHEMA_VERSION = "turtle-cutoff-official-fact-register.v2"
OBSERVATION_FIELDS = (
    "source_id",
    "table_or_section",
    "field",
    "period",
    "responsibility_boundary",
    "unit",
)


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    text = _text(value)
    if not text:
        _add(findings, f"{path}_required")
        return None
    try:
        if "T" not in text and " " not in text:
            return datetime.combine(date.fromisoformat(text), time.min, tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        _add(findings, f"{path}_must_be_iso_date_or_timezone_aware_datetime")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _add(findings, f"{path}_must_be_iso_date_or_timezone_aware_datetime")
        return None
    return parsed.astimezone(timezone.utc)


def _static_pdf_url(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    parsed = urlsplit(text)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and parsed.path.lower().endswith(".pdf")
    )


def _required_texts(value: Any, path: str, findings: list[str]) -> list[str]:
    if not isinstance(value, list) or not value:
        _add(findings, f"{path}_must_be_nonempty_list")
        return []
    result: list[str] = []
    for index, raw in enumerate(value):
        text = _text(raw)
        if not text:
            _add(findings, f"{path}[{index}]_must_be_nonempty_text")
        elif text in result:
            _add(findings, f"{path}[{index}]_duplicate:{text}")
        else:
            result.append(text)
    return result


def validate_fact_register(register: Any) -> dict[str, Any]:
    """Return a deterministic validation result without reading any source."""
    findings: list[str] = []
    if not isinstance(register, dict):
        return {"valid": False, "findings": ["register_must_be_object"]}

    schema_version = register.get("schema_version")
    if schema_version not in {SCHEMA_VERSION, CANONICAL_FACT_SCHEMA_VERSION}:
        _add(findings, "register.schema_version_invalid")
    cutoff = _instant(register.get("cutoff_at"), "register.cutoff_at", findings)

    raw_sources = register.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        _add(findings, "register.sources_must_be_nonempty_list")
    sources: dict[str, int] = {}
    for index, raw in enumerate(_items(raw_sources)):
        path = f"register.sources[{index}]"
        if not isinstance(raw, dict):
            _add(findings, f"{path}_must_be_object")
            continue
        source_id = _text(raw.get("source_id"))
        if not source_id:
            _add(findings, f"{path}.source_id_required")
        elif source_id in sources:
            _add(findings, f"{path}.source_id_duplicate:{source_id}")
        if not _static_pdf_url(raw.get("static_url")):
            _add(findings, f"{path}.static_url_must_be_static_https_pdf")
        available = _instant(raw.get("available_at"), f"{path}.available_at", findings)
        if cutoff is not None and available is not None and available >= cutoff:
            _add(findings, f"{path}.available_at_not_before_cutoff")
        declared_pages = raw.get("declared_pages")
        if type(declared_pages) is not int or declared_pages <= 0:
            _add(findings, f"{path}.declared_pages_must_be_positive_integer")
        elif source_id and source_id not in sources:
            sources[source_id] = declared_pages

    raw_observations = register.get("observations")
    if not isinstance(raw_observations, list) or not raw_observations:
        _add(findings, "register.observations_must_be_nonempty_list")
    observations: list[dict[str, str]] = []
    seen_fact_ids: set[str] = set()
    for index, raw in enumerate(_items(raw_observations)):
        path = f"register.observations[{index}]"
        if not isinstance(raw, dict):
            _add(findings, f"{path}_must_be_object")
            continue
        normalized: dict[str, str] = {}
        for field in OBSERVATION_FIELDS:
            value = _text(raw.get(field))
            if not value:
                _add(findings, f"{path}.{field}_required")
            normalized[field] = value
        source_id = normalized["source_id"]
        if source_id and source_id not in sources:
            _add(findings, f"{path}.source_id_unknown:{source_id}")
        pdf_page = raw.get("pdf_page")
        if type(pdf_page) is not int or pdf_page <= 0:
            _add(findings, f"{path}.pdf_page_must_be_positive_integer")
        elif source_id in sources and pdf_page > sources[source_id]:
            _add(findings, f"{path}.pdf_page_exceeds_source_declared_pages:{pdf_page}>{sources[source_id]}")
        if schema_version == CANONICAL_FACT_SCHEMA_VERSION:
            fact_id = _text(raw.get("fact_id"))
            if not fact_id:
                _add(findings, f"{path}.fact_id_required")
            elif fact_id in seen_fact_ids:
                _add(findings, f"{path}.fact_id_duplicate:{fact_id}")
            else:
                seen_fact_ids.add(fact_id)
            disclosed_value = raw.get("value")
            if isinstance(disclosed_value, bool):
                pass
            elif isinstance(disclosed_value, (int, float)) and not isinstance(
                disclosed_value, bool
            ):
                # NaN and infinities cannot be exact disclosed values.
                if disclosed_value != disclosed_value or disclosed_value in {
                    float("inf"), float("-inf")
                }:
                    _add(findings, f"{path}.value_must_be_finite_scalar")
            elif not _text(disclosed_value):
                _add(findings, f"{path}.value_required")
        observations.append(normalized)

    raw_series = register.get("required_series", [])
    if not isinstance(raw_series, list):
        _add(findings, "register.required_series_must_be_list")
        raw_series = []
    seen_series_ids: set[str] = set()
    for index, raw in enumerate(raw_series):
        path = f"register.required_series[{index}]"
        if not isinstance(raw, dict):
            _add(findings, f"{path}_must_be_object")
            continue
        series_id = _text(raw.get("series_id"))
        if not series_id:
            _add(findings, f"{path}.series_id_required")
        elif series_id in seen_series_ids:
            _add(findings, f"{path}.series_id_duplicate:{series_id}")
        else:
            seen_series_ids.add(series_id)
        fields = _required_texts(raw.get("fields"), f"{path}.fields", findings)
        periods = _required_texts(raw.get("periods"), f"{path}.periods", findings)
        boundary = _text(raw.get("responsibility_boundary"))
        unit = _text(raw.get("unit"))
        for field in fields:
            for period in periods:
                matched = any(
                    observation["field"] == field
                    and observation["period"] == period
                    and (not boundary or observation["responsibility_boundary"] == boundary)
                    and (not unit or observation["unit"] == unit)
                    for observation in observations
                )
                if not matched:
                    identity = series_id or str(index)
                    _add(findings, f"{path}.missing_observation:{identity}:{field}:{period}")

    return {
        "valid": not findings,
        "findings": findings,
        "source_count": len(sources),
        "observation_count": len(observations),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("register", type=Path, help="Path to the JSON fact register")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        register = json.loads(args.register.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "findings": [f"register_unreadable:{exc}"]}, ensure_ascii=False))
        return 2
    result = validate_fact_register(register)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
