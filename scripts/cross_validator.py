#!/usr/bin/env python3
"""cross_validator.py — Zone B vs Zone A numerical cross-validation (Section 4)

Cross-checks Zone B extracted numbers against Zone A DB/compute_bundle values.
Deviation > 5% → Zone A value wins, Zone B field flagged with WARN.

Usage:
  python3 scripts/cross_validator.py --code 01502.HK
  python3 scripts/cross_validator.py --code 01502.HK --max-deviation 0.05
"""

import argparse, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "output")
DB_PATH = os.path.join(ROOT, "stock_analysis.db")

# Field pairs: (zone_b_file, zone_b_field, zone_a_source, zone_a_field)
CROSS_CHECK_FIELDS = [
    # segments.json → annual_financials
    ("segments.json", "total_revenue_check_m", "db", "revenue"),
    # risks.json → annual_financials
    ("risks.json", "ar_total_m", "db", "accounts_receiv"),
    # audit.json → compute_bundle
    ("audit.json", "non_recurring_total_m", "db", None),  # no direct DB field
    # governance.json → compute_bundle
    ("governance.json", "total_related_party_revenue_m", "db", None),
    # mda.json → compute_bundle
    ("mda.json", None, "db", None),  # qualitative only, skip
]


def find_stock_dir(code):
    for e in os.listdir(OUTPUT_DIR):
        if (e.startswith(code.replace(".","_")) or e.startswith(code.split(".")[0]+"_")) and os.path.isdir(os.path.join(OUTPUT_DIR, e)):
            return os.path.join(OUTPUT_DIR, e)
    return None


def load_json(path):
    if os.path.exists(path):
        with open(path) as f: return json.load(f)
    return None


def get_db_value(conn, code, field):
    """Get latest year's value from annual_financials."""
    row = conn.execute(
        f"SELECT {field} FROM annual_financials WHERE ts_code=? ORDER BY fiscal_year DESC LIMIT 1",
        (code,)).fetchone()
    return row[0] if row and row[0] is not None else None


def extract_numeric(value, key=None):
    """Extract numeric value from Zone B output which may be {value, unit, quote} or plain number."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        v = value.get("value") or value.get("amount_m") or value.get("revenue_m")
        if v is not None:
            return float(v) if not isinstance(v, str) else None
    if isinstance(value, list) and key:
        # sum of array items
        total = 0
        for item in value:
            if isinstance(item, dict):
                v = item.get(key)
                if v is not None:
                    try: total += float(v)
                    except: pass
        return total if total > 0 else None
    return None


def cross_validate(code, max_deviation=0.05):
    """Cross-validate all Zone B outputs against Zone A sources."""
    stock_dir = find_stock_dir(code)
    if not stock_dir:
        return {"error": f"output dir not found for {code}"}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Load compute_bundle for bundle-level checks
    bundle = load_json(os.path.join(stock_dir, "compute_bundle.json"))

    results = []
    for zb_file, zb_field, za_source, za_field in CROSS_CHECK_FIELDS:
        zb_data = load_json(os.path.join(stock_dir, zb_file))
        if not zb_data:
            continue

        if zb_field:
            zb_val = extract_numeric(zb_data.get(zb_field))
        else:
            zb_val = None

        # Get Zone A value
        za_val = None
        if za_source == "db" and za_field:
            za_val = get_db_value(conn, code, za_field)
        elif za_source == "bundle" and bundle:
            parts = za_field.split(".")
            za_val = bundle
            for p in parts:
                za_val = za_val.get(p, {}) if isinstance(za_val, dict) else None

        if zb_val is None or za_val is None or za_val == 0:
            results.append({"file": zb_file, "field": zb_field,
                           "zb_value": zb_val, "za_value": za_val,
                           "deviation": None, "verdict": "SKIP"})
            continue

        deviation = abs(zb_val - za_val) / abs(za_val)
        verdict = "PASS" if deviation <= max_deviation else "OVERRIDE"

        result = {"file": zb_file, "field": zb_field,
                  "zb_value": zb_val, "za_value": za_val,
                  "deviation": round(deviation * 100, 1), "verdict": verdict}

        if verdict == "OVERRIDE":
            # Override Zone B value with Zone A value
            result["action"] = f"Zone B={zb_val:.1f}, Zone A={za_val:.1f}, dev={deviation:.1%}, override to Zone A"
            # Save corrected value back
            if zb_field and zb_data:
                zb_data[zb_field] = za_val
                zb_data[f"{zb_field}_zone_a_override"] = True
                zb_data[f"{zb_field}_original_zone_b"] = zb_val
                with open(os.path.join(stock_dir, zb_file), "w") as f:
                    json.dump(zb_data, f, indent=2, ensure_ascii=False)

        results.append(result)

    conn.close()
    return {"code": code, "results": results,
            "summary": {
                "total": len(results),
                "pass": sum(1 for r in results if r["verdict"] == "PASS"),
                "override": sum(1 for r in results if r["verdict"] == "OVERRIDE"),
                "skip": sum(1 for r in results if r["verdict"] == "SKIP"),
            }}


def main():
    p = argparse.ArgumentParser(description="cross_validator.py")
    p.add_argument("--code", required=True)
    p.add_argument("--max-deviation", type=float, default=0.05)
    args = p.parse_args()

    result = cross_validate(args.code, args.max_deviation)
    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr); return 1

    print(f"Cross-Validation: {args.code}")
    print(f"{'File':<20} {'Field':<30} {'Zone B':>10} {'Zone A':>10} {'Dev%':>7} {'Verdict'}")
    print("-" * 90)
    for r in result["results"]:
        zb = f"{r['zb_value']:.1f}" if r['zb_value'] else "N/A"
        za = f"{r['za_value']:.1f}" if r['za_value'] else "N/A"
        dev = f"{r['deviation']}%" if r['deviation'] is not None else "-"
        print(f"{r['file']:<20} {r['field'] or '':>7} {r['verdict']}")

    s = result["summary"]
    print(f"\n✅ {s['pass']} PASS | 🔄 {s['override']} OVERRIDE | ⏭️ {s['skip']} SKIP")

    # Save report
    stock_dir = find_stock_dir(args.code)
    if stock_dir:
        rp = os.path.join(stock_dir, "cross_validation_report.json")
        with open(rp, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Report: {rp}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
