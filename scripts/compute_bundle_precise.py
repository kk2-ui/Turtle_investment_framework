#!/usr/bin/env python3
"""compute_bundle_precise.py — Zone A Precise Computation (V7)

Post-processor that reads compute_bundle.json (base) + Zone J JSONs and outputs
adjusted values with Zone-J-derived parameters and full rationale.

Usage:
    python3 scripts/compute_bundle_precise.py --code 01502.HK
"""

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute_precise(ts_code: str, stock_dir: str) -> dict:
    """Read base compute_bundle + Zone J params, produce precise version."""

    base = load_json(os.path.join(stock_dir, "compute_bundle.json"))
    # Load overrides (analyst manual corrections, take priority over Zone J)
    overrides = load_json(os.path.join(stock_dir, "overrides.json"))
    moat = load_json(os.path.join(stock_dir, "moat_assessment.json"))
    capex = load_json(os.path.join(stock_dir, "capex_classification.json"))
    eq = load_json(os.path.join(stock_dir, "earnings_quality.json"))
    discount = load_json(os.path.join(stock_dir, "data_discount.json"))
    # Deep merge: overrides take priority for specified fields (V7.2 fix: explicit mapping)
    _override_map = {"moat_assessment": moat, "capex_classification": capex,
                     "earnings_quality": eq, "data_discount": discount}
    if overrides and not overrides.get("_missing"):
        for section, target in _override_map.items():
            if section in overrides and overrides[section] and target:
                target.update(overrides[section])

    if not base:
        return {"error": "compute_bundle.json not found"}
    if "error" in base:
        return base

    result = deepcopy(base)

    # ── Override parameters from Zone J ──
    adjustments = []
    # V9: Zone J may return {value, rationale, evidence_ref} dict or bare number
    def _v(val):
        """Extract bare value from Zone J dict format or pass through."""
        return val.get("value") if isinstance(val, dict) and "value" in val else val

    old_b = base.get("params", {}).get("b_penalty", 0.25)
    old_g = base.get("params", {}).get("g_base", 2.0)

    # 1. B-class penalty
    j_b_penalty = _v(moat.get("b_penalty_final"))
    if j_b_penalty is not None:
        result["params"]["b_penalty"] = j_b_penalty
        result["params"]["b_penalty_source"] = "zone_j_moat"
        adjustments.append({
            "param": "b_penalty",
            "base": old_b,
            "precise": j_b_penalty,
            "rationale": moat.get("b_penalty_rationale", ""),
            "impact": f"g_adj 从 {2.0*(1-old_b):.2f}% 变为 {2.0*(1-j_b_penalty):.2f}%"
        })

    # 2. g_base and scenarios
    j_g_base = _v(moat.get("g_base"))
    if j_g_base is not None:
        result["params"]["g_base"] = j_g_base
        result["params"]["g_base_source"] = "zone_j_moat"
        g_scenarios = moat.get("g_scenarios", {})
        result["params"]["g_scenarios"] = g_scenarios
        adjustments.append({
            "param": "g_base",
            "base": old_g,
            "precise": j_g_base,
            "rationale": moat.get("g_base_rationale", ""),
            "impact": f"DDM g 从 {(1-0.25)*old_g:.2f}% 变为 {(1-j_b_penalty)*j_g_base:.2f}%"
        })

    # 3. Data quality discount
    j_discount = _v(discount.get("total_discount_pct"))
    if j_discount is not None:
        old_disc = 15  # default
        result["params"]["data_discount_pct"] = j_discount
        result["params"]["discount_factors"] = discount.get("discount_factors", [])
        adjustments.append({
            "param": "data_discount_pct",
            "base": old_disc,
            "precise": j_discount,
            "rationale": f"基于 {len(discount.get('discount_factors',[]))} 项因素",
            "impact": f"GG 折扣从 {old_disc}% 变为 {j_discount}%"
        })

    # 4. Capex classification
    mcapex_pct = _v(capex.get("mcapex_split_pct"))
    if mcapex_pct is not None:
        result["params"]["mcapex_split_pct"] = mcapex_pct
        result["params"]["mcapex_rationale"] = capex.get("mcapex_rationale", "")
        adjustments.append({
            "param": "mcapex_split_pct",
            "base": None,
            "precise": mcapex_pct,
            "rationale": capex.get("mcapex_rationale", ""),
            "impact": f"维持性Capex占比 {mcapex_pct*100:.0f}%，影响 AA 精算"
        })

    # 5. AR adjustment flag
    ar_needed = eq.get("ar_quality", {}).get("ar_adjustment_needed")
    if ar_needed:
        result["params"]["ar_adjustment_years"] = eq["ar_quality"].get("adjustment_years", [])
        adjustments.append({
            "param": "ar_adjustment",
            "base": False,
            "precise": True,
            "rationale": f"FY2024 AR增速异常（+27.7% vs 营收+15.7%），回款率仅95.7%，建议对该年True Revenue做AR调整",
            "impact": "FY2024 True Revenue 可能高估约 30M"
        })

    # 6. Non-recurring net adjustment
    nr_net = eq.get("non_recurring_items", {}).get("net_adjustment_m")
    if nr_net:
        result["params"]["non_recurring_adjustment_m"] = nr_net
        adjustments.append({
            "param": "non_recurring_adjustment",
            "base": 0,
            "precise": nr_net,
            "rationale": f"商誉减值 {abs(nr_net)}M 为一次性，从可持续利润中排除",
            "impact": f"调整后 NP₃y ≈ {base['factor2']['np_avg_3y'] + abs(nr_net)/3:.1f}M"
        })

    # 7. Value trap signals from Zone J
    j_vt = moat.get("value_trap_signals", [])
    if j_vt:
        result["factor4"]["value_trap"]["zone_j_signals"] = j_vt

    # ── Recompute key metrics with new params ──
    # Simplified recomputation (full recompute needs access to raw data)
    new_b = result["params"]["b_penalty"]
    new_g = result["params"]["g_base"]
    new_disc = result["params"].get("data_discount_pct", 15)

    # Recompute g_adj
    old_g_adj = base["factor3"].get("g_adj", 1.5)
    new_g_adj = round(new_g * (1 - new_b), 2)
    result["factor3"]["g_adj_precise"] = new_g_adj
    result["factor3"]["g_adj_change"] = round(new_g_adj - old_g_adj, 2)

    # Recompute GG with new discount
    old_gg = base["factor3"]["gg"]
    new_gg = {}
    for scenario in ["pessimistic", "base", "optimistic"]:
        old_val = old_gg.get(scenario, 0)
        # Apply adjusted discount
        new_val = round(old_val * (1 - new_disc/100), 1)
        new_gg[scenario] = new_val
    result["factor3"]["gg_precise"] = new_gg

    # Recompute DDM with new g
    dps = base.get("params", {}).get("dps_latest") or base["factor4"].get("dps_latest") or 0.157
    II_val = base["params"].get("II", 5.5) / 100
    g_ddm = new_g_adj / 100  # g_adj is in percent
    if II_val > g_ddm:
        new_ddm_rmb = round(dps * (1 + g_ddm) / (II_val - g_ddm), 2)
        fx = base.get("market", {}).get("fx", 0.9346)
        new_ddm_hkd = round(new_ddm_rmb / fx, 2)
        result["factor4"]["ddm_v_rmb_precise"] = new_ddm_rmb
        result["factor4"]["ddm_v_hkd_precise"] = new_ddm_hkd
        old_ddm_hkd = base["factor4"].get("ddm_v_hkd", 0)
        adjustments.append({
            "param": "ddm_v_hkd",
            "base": old_ddm_hkd,
            "precise": new_ddm_hkd,
            "rationale": f"g从{old_g_adj}%→{new_g_adj}% (b_penalty {old_b*100:.0f}%→{new_b*100:.0f}%, g_base {old_g:.1f}%→{new_g:.1f}%)",
            "impact": f"DDM公允价变化 {new_ddm_hkd - old_ddm_hkd:+.2f} HKD"
        })


    # ── Add provenance ──
    result["_precise"] = {
        "generated_at": datetime.now().isoformat(),
        "script": "compute_bundle_precise.py",
        "zone_j_sources": ["moat_assessment.json", "capex_classification.json",
                          "earnings_quality.json", "data_discount.json"],
        "adjustments": adjustments,
        "note": "精算版基于Zone J参数调整。基版compute_bundle.json保留为参考。"
    }

    return result


def main():
    p = argparse.ArgumentParser(description="compute_bundle_precise.py — Zone A Precise Compute")
    p.add_argument("--code", type=str, required=True, help="Stock code")
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

    result = compute_precise(args.code, stock_dir)
    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        return 1

    out_path = os.path.join(stock_dir, "compute_bundle_precise.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    adj = result.get("_precise", {}).get("adjustments", [])
    print(f"✅ compute_bundle_precise.json → {out_path}")
    print(f"   {len(adj)} parameter adjustments from Zone J:")
    for a in adj:
        print(f"   • {a['param']}: {a['base']} → {a['precise']} ({a['impact'][:80]})")

    # Show key output changes
    if "gg_precise" in result.get("factor3", {}):
        old_gg = result["factor3"]["gg"]
        new_gg = result["factor3"]["gg_precise"]
        print(f"\n   GG: {old_gg} → {new_gg}")
    if "ddm_v_hkd_precise" in result.get("factor4", {}):
        old_ddm = result["factor4"]["ddm_v_hkd"]
        new_ddm = result["factor4"]["ddm_v_hkd_precise"]
        print(f"   DDM: {old_ddm} → {new_ddm} HKD")

    return 0


if __name__ == "__main__":
    sys.exit(main())
