#!/usr/bin/env python3
"""boundary_validator.py — JSON Schema Boundary Validation (V7)

Validates Zone B/J/A output JSONs against expected schemas at 3 key boundaries:
  1. Zone B → cross-validator boundary
  2. Zone J → compute_bundle_precise boundary
  3. Zone A precise → Zone C boundary

Catches silent failures: missing required fields, wrong types, out-of-range values.
Without this layer, a typo in a field name silently corrupts downstream computation.

Usage:
    python3 scripts/boundary_validator.py --code 01502.HK --boundary zone_b
    python3 scripts/boundary_validator.py --code 01502.HK --boundary all
"""

import argparse
import json
import os
import sys

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

# ── Expected schemas (simplified: field_name → {required, type, range}) ──

ZONE_B_SCHEMAS = {
    "mda.json": {
        "required_fields": ["year_highlights", "key_operations_metrics"],
        "field_types": {
            "key_operations_metrics": list,
            "year_highlights": list,
        },
    },
    "segments.json": {
        "required_fields": ["segments"],
        "field_types": {"segments": list},
    },
    "risks.json": {
        "required_fields": ["ar_aging", "ar_total_m", "goodwill_balance_m"],
        "field_types": {
            "ar_aging": list,
            "ar_total_m": (int, float),
            "goodwill_balance_m": (int, float, type(None)),
        },
    },
    "governance.json": {
        "required_fields": ["related_party_transactions"],
        "field_types": {"related_party_transactions": list},
    },
    "audit.json": {
        "required_fields": ["auditor", "audit_opinion"],
        "field_types": {"auditor": str, "audit_opinion": str},
    },
}

ZONE_J_SCHEMAS = {
    "moat_assessment.json": {
        "required_fields": ["b_penalty_final", "g_base", "g_scenarios", "value_trap_signals", "moat_evidence"],
        "field_types": {
            "b_penalty_final": (int, float),
            "g_base": (int, float),
            "g_scenarios": dict,
            "value_trap_signals": list,
            "moat_evidence": list,
        },
        "range_checks": {
            "b_penalty_final": (0.0, 0.5),
            "g_base": (0.0, 5.0),
        },
        "sub_fields": {
            "g_scenarios": {"required_fields": ["pessimistic", "base", "optimistic"], "field_types": {"pessimistic": (int,float), "base": (int,float), "optimistic": (int,float)}},
            "moat_evidence": {"is_list_of_objects": True, "item_required": ["type"]},
        },
    },
    "capex_classification.json": {
        "required_fields": ["capex_type", "mcapex_split_pct", "growth_classification"],
        "field_types": {
            "capex_type": str,
            "mcapex_split_pct": (int, float),
            "growth_classification": dict,
        },
        "range_checks": {
            "mcapex_split_pct": (0.0, 1.0),
        },
        "sub_fields": {
            "growth_classification": {"required_fields": ["A_class_pct", "B_class_pct", "C_class_pct"], "field_types": {"A_class_pct": (int,float), "B_class_pct": (int,float), "C_class_pct": (int,float)}},
        },
    },
    "earnings_quality.json": {
        "required_fields": ["ar_quality", "ap_excess_check", "non_recurring_items"],
        "field_types": {
            "ar_quality": dict,
            "ap_excess_check": dict,
            "non_recurring_items": dict,
        },
        "sub_fields": {
            "ar_quality": {"required_fields": ["ar_adjustment_needed"], "field_types": {"ar_adjustment_needed": bool}},
            "non_recurring_items": {"required_fields": ["keep", "exclude"], "field_types": {"keep": list, "exclude": list}},
        },
    },
    "data_discount.json": {
        "required_fields": ["total_discount_pct", "confidence_by_section", "discount_factors"],
        "field_types": {
            "total_discount_pct": (int, float),
            "confidence_by_section": dict,
            "discount_factors": list,
        },
        "range_checks": {
            "total_discount_pct": (0, 50),
        },
    },
}

ZONE_A_PRECISE_SCHEMA = {
    "required_fields": ["factor2", "factor3", "factor4", "rejection_summary"],
    "field_types": {
        "factor2": dict,
        "factor3": dict,
        "factor4": dict,
        "rejection_summary": dict,
    },
}


def validate_file(data: dict, schema: dict, fname: str) -> list:
    """Validate a JSON object against its expected schema. Returns list of errors."""
    errors = []

    # Check required fields
    for field in schema.get("required_fields", []):
        if field not in data or data[field] is None:
            errors.append(f"MISSING_REQUIRED: {fname} missing field '{field}'")

    # Check types
    for field, expected_type in schema.get("field_types", {}).items():
        if field in data and data[field] is not None:
            if not isinstance(data[field], expected_type):
                errors.append(
                    f"WRONG_TYPE: {fname}.{field} is {type(data[field]).__name__}, expected {expected_type}")

    # Check ranges
    for field, (lo, hi) in schema.get("range_checks", {}).items():
        if field in data and data[field] is not None:
            val = data[field]
            if val < lo or val > hi:
                errors.append(
                    f"OUT_OF_RANGE: {fname}.{field}={val}, expected [{lo}, {hi}]")

    # V7.2: Check sub-fields (nested objects)
    for field, sub_schema in schema.get("sub_fields", {}).items():
        if field not in data or data[field] is None:
            continue
        val = data[field]
        if sub_schema.get("is_list_of_objects") and isinstance(val, list):
            for i, item in enumerate(val):
                if isinstance(item, dict):
                    for req in sub_schema.get("item_required", []):
                        if req not in item:
                            errors.append(f"SUB_MISSING: {fname}.{field}[{i}] missing '{req}'")
        elif isinstance(val, dict):
            for req in sub_schema.get("required_fields", []):
                if req not in val or val[req] is None:
                    errors.append(f"SUB_MISSING: {fname}.{field}.{req}")
            for sf, st in sub_schema.get("field_types", {}).items():
                if sf in val and val[sf] is not None:
                    if not isinstance(val[sf], st):
                        errors.append(f"SUB_TYPE: {fname}.{field}.{sf} is {type(val[sf]).__name__}, expected {st}")

    return errors


def validate_boundary(stock_dir: str, boundary: str) -> dict:
    """Validate all files at a specific boundary."""
    results = {"boundary": boundary, "status": "PASS", "files": {}, "errors": []}

    if boundary == "zone_b":
        schemas = ZONE_B_SCHEMAS
    elif boundary == "zone_j":
        schemas = ZONE_J_SCHEMAS
    elif boundary == "zone_a_precise":
        schemas = {"compute_bundle_precise.json": ZONE_A_PRECISE_SCHEMA}
    else:
        results["errors"].append(f"Unknown boundary: {boundary}")
        results["status"] = "FAIL"
        return results

    for fname, schema in schemas.items():
        path = os.path.join(stock_dir, fname)
        if not os.path.exists(path):
            results["files"][fname] = "MISSING"
            results["errors"].append(f"MISSING_FILE: {fname}")
            results["status"] = "FAIL" if results["status"] == "PASS" else results["status"]
            continue

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        file_errors = validate_file(data, schema, fname)
        if file_errors:
            results["files"][fname] = {"status": "FAIL", "errors": file_errors}
            results["errors"].extend(file_errors)
            results["status"] = "FAIL"
        else:
            results["files"][fname] = {"status": "PASS"}

    return results


def main():
    p = argparse.ArgumentParser(description="boundary_validator.py — JSON Schema Validation")
    p.add_argument("--code", type=str, required=True, help="Stock code")
    p.add_argument("--boundary", type=str, default="all",
                   choices=["zone_b", "zone_j", "zone_a_precise", "all"])
    p.add_argument("--output", type=str, help="Output directory")
    args = p.parse_args()

    if args.output:
        stock_dir = args.output
    else:
        code_base = args.code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
        candidates = [d for d in os.listdir(OUTPUT_BASE)
                      if os.path.isdir(os.path.join(OUTPUT_BASE, d)) and d.startswith(code_base)]
        if not candidates:
            print(f"ERROR: No output directory for {args.code}", file=sys.stderr)
            return 1
        stock_dir = os.path.join(OUTPUT_BASE, candidates[0])

    boundaries = ["zone_b", "zone_j", "zone_a_precise"] if args.boundary == "all" else [args.boundary]

    all_ok = True
    for boundary in boundaries:
        result = validate_boundary(stock_dir, boundary)
        status_icon = "✅" if result["status"] == "PASS" else "❌"
        print(f"{status_icon} {boundary}: {result['status']}")
        for fname, fresult in result["files"].items():
            if isinstance(fresult, dict) and fresult.get("status") == "FAIL":
                for e in fresult.get("errors", []):
                    print(f"   • {e}")
            elif fresult == "MISSING":
                print(f"   • {fname}: MISSING")
        if result["status"] != "PASS":
            all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
