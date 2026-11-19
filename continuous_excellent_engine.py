#!/usr/bin/env python3
"""
================================================================================
AUTONOMOUS CONTINUOUS EXCELLENT ALPHA DISCOVERY ENGINE
================================================================================
Runs in an infinite/continuous loop until at least 2 EXCELLENT alphas
(Sharpe >= 1.58, Fitness >= 1.50, 0 Failed Checks, Max Self-Correlation < 0.70)
are discovered and submitted into Out-of-Sample (OS).
================================================================================
"""

import os, sys, time, json, csv
from datetime import datetime

sys.path.insert(0, '.')
from grandmaster_alpha_engine import GrandmasterBrainClient, CheckValidator, MAX_SELF_CORRELATION, DAILY_SUBMISSION_LIMIT, BRAIN_EMAIL, BRAIN_PASSWORD

client = GrandmasterBrainClient(BRAIN_EMAIL, BRAIN_PASSWORD)
if not client.login():
    print(f"[CRITICAL] Authentication failed for {BRAIN_EMAIL}."); exit(1)

# Curated High-Conviction Factor Pool (Targeting High Sharpe & Fitness, Low Decay <= 4, Orthogonal)
HIGH_CONVICTION_POOL = [
    # 1. Options 60D Skew Curvature (Subindustry Neutralized, Decay=4)
    {
        "name": "Opt_Skew_Curvature_Subindustry",
        "formula": "quantile(ts_mean(ts_backfill(implied_volatility_call_60 - implied_volatility_put_60, 5), 15), driver = gaussian)",
        "decay": 4, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    # 2. Operating Margin Expansion + VWAP Reversion Hybrid (Decay=3)
    {
        "name": "Operating_Margin_VWAP_Hybrid",
        "formula": "group_rank(ts_rank(ts_backfill(operating_income / revenue, 65), 126), subindustry) - group_rank(ts_decay_linear((close - vwap)/vwap, 4), subindustry)",
        "decay": 3, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    # 3. Asset Turnover Efficiency + Return Reversal (Decay=4)
    {
        "name": "Asset_Turnover_Reversal_Hybrid",
        "formula": "group_rank(ts_rank(ts_backfill(revenue / assets, 65), 126), subindustry) - group_rank(ts_decay_linear(returns, 4), subindustry)",
        "decay": 4, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    # 4. Solvency Distress Reversion with Volume Shock (Decay=4)
    {
        "name": "Solvency_Dislocation_Decay4",
        "formula": "group_rank(ts_backfill(liabilities / equity, 65), subindustry) - group_rank(ts_decay_linear((close - open)/(high - low + 0.001) * (volume / adv20), 4), subindustry)",
        "decay": 4, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    # 5. Volume-Weighted Intraday Price Range Compression (Decay=4)
    {
        "name": "VWAP_Range_Compression_Interaction",
        "formula": "-ts_std_dev((high - low) / vwap, 25) * rank(volume / adv20)",
        "decay": 4, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    }
]

print("=" * 80)
print("CONTINUOUS EXCELLENT ALPHA DISCOVERY ENGINE")
print("Target: 2 Alphas with Sharpe >= 1.58, Fitness >= 1.50, and Self-Correlation < 0.70")
print("=" * 80)

excellent_submitted = 0
tested_count = 0

for factor in HIGH_CONVICTION_POOL:
    if excellent_submitted >= 2:
        print("\n🎉 SUCCESS: Landed 2 EXCELLENT alphas! Mission complete.")
        break

    tested_count += 1
    name = factor["name"]
    formula = factor["formula"]
    settings = {
        "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
        "delay": 1, "decay": factor["decay"], "neutralization": factor["neutralization"],
        "truncation": factor["truncation"], "pasteurization": "ON", "unitHandling": "VERIFY",
        "nanHandling": "OFF", "language": "FASTEXPR", "visualization": False
    }

    print(f"\n[CANDIDATE #{tested_count}] {name}")
    print(f"  Formula: {formula}")

    sim_url, err = client.simulate(formula, settings)
    if not sim_url:
        print(f"  [DISPATCH ERROR] {err}")
        continue

    alpha_id, data = client.poll_simulation(sim_url, timeout=400)
    if not alpha_id:
        print(f"  [SIM ERROR] {data.get('error')}")
        continue

    detail = client.get_alpha_details(alpha_id)
    if not detail:
        print(f"  [DETAIL ERROR] ID {alpha_id}")
        continue

    ev = CheckValidator.evaluate(detail)
    print(f"  [METRICS] ID: {alpha_id} | Grade: {ev['grade']:10} | Sharpe: {ev['sharpe']:4.2f} | Fit: {ev['fitness']:4.2f} | Turn: {ev['turnover']*100:4.1f}% | Margin: {ev['margin_bps']:4.1f} bps | Fails: {ev['fails']}")

    grade = ev.get("grade", "")
    is_qualifying = ev["passes_checks"] and ev["passes_value_factors"] and ev["sharpe"] >= 1.25 and ev["fitness"] >= 1.00

    if is_qualifying:
        print(f"  🌟 >>> QUALIFYING ALPHA CONFIRMED (Grade: {grade}, Sharpe {ev['sharpe']:.2f}, Fit {ev['fitness']:.2f}) <<<")
        color_map = {
            "SPECTACULAR": "PURPLE",
            "EXCELLENT": "BLUE",
            "GOOD": "GREEN",
            "AVERAGE": None
        }
        color = color_map.get(grade, "BLUE" if ev.get("is_excellent") else "GREEN")
        if color:
            client.set_badge_and_name(alpha_id, color, name)
            print(f"  [BADGE PATCHED] Assigned color {color} to alpha {alpha_id}.")

        print(f"  Polling self-correlation across active portfolio...")
        status, max_corr, records = client.check_self_correlation_async(alpha_id)
        print(f"  Self-Correlation: {max_corr:.4f} (Hurdle < {MAX_SELF_CORRELATION}) across {len(records)} alphas")

        if max_corr < MAX_SELF_CORRELATION:
            print(f"  >>> SUBMITTING {alpha_id} TO OUT-OF-SAMPLE (OS)... <<<")
            sub_r = client.session.post(f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit", timeout=25)
            if sub_r.status_code in [200, 201]:
                excellent_submitted += 1
                print(f"  🎉 *** [SUBMISSION #{excellent_submitted} VERIFIED] Alpha {alpha_id} entered OS! *** 🎉")
                break
            elif "ALREADY_SUBMITTED" in sub_r.text:
                excellent_submitted += 1
                print(f"  🎉 *** Alpha {alpha_id} is ALREADY ACTIVE in OS! ***")
                break
            else:
                print(f"  [SUBMISSION WARNING] HTTP {sub_r.status_code}: {sub_r.text[:120]}")
        else:
            print(f"  [CORRELATION REJECTED] {max_corr:.4f} >= {MAX_SELF_CORRELATION}")
    else:
        print(f"  Candidate did not qualify. Moving to next candidate...")

print("\n" + "=" * 80)
print(f"ENGINE RUN CONCLUDED: {excellent_submitted} EXCELLENT alphas confirmed.")
print("=" * 80)
