#!/usr/bin/env python3
"""
Test fundamental-anchored intraday hybrids & high-conviction gated volume shocks:
1. Operating ROA + Intraday Candle Reversal (Turnover anchored by fundamental quarterly base)
2. Cashflow ROA + Intraday Candle Reversal
3. Volume 1.5x Gated Intraday Candle
"""
import sys, time
sys.path.insert(0, '.')
from grandmaster_alpha_engine import GrandmasterBrainClient, CheckValidator, MAX_SELF_CORRELATION

client = GrandmasterBrainClient("xstreamnova@gmail.com", "nova@1234")
if not client.login():
    print("Login failed"); exit(1)

CANDS = [
    {
        "name": "Hybrid_Operating_ROA_Intraday_Candle",
        "formula": "group_rank(ts_backfill(operating_income / assets, 65), industry) + 0.5 * group_rank(-(close - open) / (high - low + 0.001), subindustry)",
        "decay": 8, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "Hybrid_Cashflow_ROA_Intraday_Candle",
        "formula": "group_rank(ts_backfill(cashflow_op / assets, 65), industry) + 0.5 * group_rank(-(close - open) / (high - low + 0.001), subindustry)",
        "decay": 8, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "Gated_Volume_Extreme_Intraday",
        "formula": "trade_when(volume > 1.5 * adv20, group_rank(-(close - open) / (high - low + 0.001), subindustry), -1)",
        "decay": 10, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    }
]

print("=== DISPATCHING FUNDAMENTAL-ANCHORED HYBRIDS ===")
sims = []
for cand in CANDS:
    settings = {
        "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
        "delay": 1, "decay": cand["decay"], "neutralization": cand["neutralization"],
        "truncation": cand["truncation"], "pasteurization": "ON", "unitHandling": "VERIFY",
        "nanHandling": "OFF", "language": "FASTEXPR", "visualization": False
    }
    url, err = client.simulate(cand["formula"], settings)
    print(f"[DISPATCH] {cand['name']}: {url} (err={err})")
    if url:
        sims.append((cand["name"], url, cand))

print("\n=== POLLING SIMULATION RESULTS & SUBMITTING ===")
submitted = 0
for name, url, cand in sims:
    if submitted >= 3:
        print(f"\n🎉 Goal achieved: Submitted {submitted} alphas to OS!")
        break

    print(f"\nPolling {name}...")
    aid, data = client.poll_simulation(url, timeout=350)
    if not aid:
        print(f"  Simulation failed: {data.get('error')}")
        continue

    d = client.get_alpha_details(aid)
    if not d:
        continue

    ev = CheckValidator.evaluate(d)
    print(f"  ID: {aid} | Grade: {ev['grade']} | Sharpe: {ev['sharpe']:.2f} | Fit: {ev['fitness']:.2f} | Turn: {ev['turnover']*100:.1f}% | Margin: {ev['margin_bps']:.1f}bps | Fails: {ev['fails']}")

    if ev['passes_checks']:
        print(f"  100% Passed all checks! Checking self-correlation against all 7 OS alphas...")
        st, max_c, recs = client.check_self_correlation_async(aid, timeout=50)
        print(f"  Max Self-Corr: {max_c:.4f} (Hurdle < {MAX_SELF_CORRELATION}) across {len(recs)} alphas")
        for r in recs:
            print(f"     vs {r[0]} ({r[1]}): {r[5]}")

        if max_c < MAX_SELF_CORRELATION:
            color = "PURPLE" if ev['sharpe'] >= 2.0 or ev['grade'] in ['EXCELLENT', 'SPECTACULAR'] else "BLUE"
            client.set_badge_and_name(aid, color, name)
            print(f"  >>> SUBMITTING {aid} ({name}) to OS! <<<")
            resp = client.session.post(f"https://api.worldquantbrain.com/alphas/{aid}/submit", timeout=25)
            print(f"  Submit response HTTP {resp.status_code}: {resp.text[:120]}")
            if resp.status_code in [200, 201]:
                submitted += 1
                print(f"  🎉 SUBMISSION #{submitted}/3 SUCCESSFUL! 🎉")
        else:
            print(f"  Correlation rejected: {max_c:.4f} >= {MAX_SELF_CORRELATION}")

print(f"\n=== FINISHED: Submitted {submitted} new alphas to OS ===")
