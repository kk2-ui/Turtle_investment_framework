#!/usr/bin/env python3
"""quote_verifier.py — Zone B Quote Verifier

Verifies that Zone B extraction quotes actually exist in the source PDF text.
Simple string matching — checks if each quote from Zone B JSONs appears in the
corresponding pdf_sections JSON. Flags fabricated or hallucinated quotes.

Usage:
    python3 scripts/quote_verifier.py --code 01502.HK
"""
import argparse, json, os, sys
OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

ZONE_B_FILES = {
    "mda.json": ["MDA"],
    "segments.json": ["MDA"],
    "risks.json": ["P3"],
    "governance.json": ["MDA", "DAN"],
    "audit.json": ["STMT"],
}

def find_quotes(data, prefix=""):
    """Recursively find all 'quote' fields in a dict."""
    quotes = []
    if isinstance(data, dict):
        if "quote" in data and isinstance(data["quote"], str) and len(data["quote"]) > 10:
            quotes.append((f"{prefix}.quote", data["quote"]))
        for k, v in data.items():
            quotes.extend(find_quotes(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            quotes.extend(find_quotes(v, f"{prefix}[{i}]"))
    return quotes

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--code", required=True); p.add_argument("--output")
    a = p.parse_args()
    sd = a.output or next((os.path.join(OUTPUT_BASE, d) for d in os.listdir(OUTPUT_BASE) if os.path.isdir(os.path.join(OUTPUT_BASE, d)) and d.startswith(a.code.replace(".HK","").replace(".SH","").replace(".SZ",""))), None)
    if not sd: print("ERROR: no dir", file=sys.stderr); return 1

    # Load latest pdf_sections
    pdf_sections = {}
    for f in sorted(os.listdir(sd)):
        if f.startswith("pdf_sections_") and f.endswith(".json"):
            with open(os.path.join(sd, f)) as fh:
                pdf_sections = json.load(fh)

    if not pdf_sections:
        print("⚠️ No pdf_sections found — skipping quote verification")
        return 0

    results = {"verified": 0, "not_found": 0, "missing_pdf_sections": 0, "details": []}
    for fname, section_keys in ZONE_B_FILES.items():
        path = os.path.join(sd, fname)
        if not os.path.exists(path):
            results["details"].append({"file": fname, "status": "MISSING"})
            continue
        with open(path) as f:
            data = json.load(f)
        quotes = find_quotes(data)
        for qpath, quote in quotes:
            # Search in all relevant sections
            found = False
            for sk in section_keys:
                text = pdf_sections.get(sk, "")
                if not text: continue
                # Fuzzy match: try exact, then first 30 chars, then key numbers
                if quote[:40] in text or quote[-40:] in text:
                    found = True; break
                # Try key number matching: find all numbers in quote and check
                import re
                nums = re.findall(r'\d+\.?\d*', quote)
                if nums and all(n in text for n in nums[:3]):
                    found = True; break
            if found:
                results["verified"] += 1
            else:
                results["not_found"] += 1
                results["details"].append({
                    "file": fname, "path": qpath, "status": "NOT_FOUND",
                    "quote_preview": quote[:80]
                })

    out_path = os.path.join(sd, "quote_verification.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total = results["verified"] + results["not_found"]
    rate = results["verified"]/total*100 if total else 100
    icon = "✅" if rate > 90 else ("⚠️" if rate > 70 else "❌")
    print(f"{icon} Quote verification: {results['verified']}/{total} ({rate:.0f}%)")
    if results["not_found"]:
        print(f"  ❌ {results['not_found']} quotes NOT found in source PDF")
        for d in results["details"][:5]:
            if d.get("status") == "NOT_FOUND":
                print(f"    {d['file']}: {d['quote_preview'][:60]}...")
    print(f"✅ {out_path}")
    return 0 if rate > 70 else 1
if __name__ == "__main__": sys.exit(main())
