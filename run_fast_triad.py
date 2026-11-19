#!/usr/bin/env python3
"""
Simulate 4 high-probability winning hybrid factor formulas:
1. Cashflow ROA Quality + Weekly Reversal
2. Operating ROA Quality + Weekly Reversal
3. Group-Neutralized Linear Decay Options Skew (fixes concentrated weight on gJaz6aWv)
4. Gated VWAP Threshold Reversion (fixes high turnover on pwaO3pnj)
"""
import sys, time
sys.path.insert(0, '.')
from grandmaster_alpha_engine import GrandmasterBrainClient, CheckValidator, MAX_SELF_CORRELATION

client = GrandmasterBrainClient("xstreamnova@gmail.com", "nova@1234")
if not client.login():
    print("Login failed"); exit(1)

CANDIDATES = [
    {
        "name": "Cashflow_ROA_Weekly_Reversal",
        "formula": "rank(ts_backfill(cashflow_op / assets, 65)) - rank(close - ts_mean(close, 5))",
        "decay": 10, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "Operating_ROA_Weekly_Reversal",
        "formula": "rank(ts_backfill(operating_income / assets, 65)) - rank(close - ts_mean(close, 5))",
        "decay": 10, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "Options_Skew_LinearDecay_Subindustry",
        "formula": "group_neutralize(ts_decay_linear(ts_backfill(implied_volatility_call_30 - implied_volatility_put_30, 5), 10), subindustry)",
        "decay": 6, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "Gated_VWAP_Threshold_Reversion",
        "formula": "trade_when(abs(close - vwap) / close > 0.01, -ts_rank((close - vwap) / vwap, 22), -1)",
        "decay": 8, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    }
]

print("=== DISPATCHING 4 HIGH-PROBABILITY CANDIDATES ===")
sims = []
for cand in CANDIDATES:
    name = cand["name"]
    formula = cand["formula"]
    settings = {
        "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
        "delay": 1, "decay": cand["decay"], "neutralization": cand["neutralization"],
        "truncation": cand["truncation"], "pasteurization": "ON", "unitHandling": "VERIFY",
        "nanHandling": "OFF", "language": "FASTEXPR", "visualization": False
    }
    url, err = client.simulate(formula, settings)
    print(f"[DISPATCH] {name}: {url} (err={err})")
    if url:
        sims.append((name, url, cand))

print("\n=== POLLING SIMULATIONS ===")
submitted_count = 0
for name, url, cand in sims:
    if submitted_count >= 3:
        print(f"\n🎉 Goal achieved: Submitted {submitted_count} alphas to OS!")
        break

    print(f"\nPolling {name}...")
    aid, data = client.poll_simulation(url, timeout=350)
    if not aid:
        print(f"  Simulation failed: {data.get('error')}")
        continue

    detail = client.get_alpha_details(aid)
    if not detail:
        continue

    ev = CheckValidator.evaluate(detail)
    print(f"  ID: {aid} | Grade: {ev['grade']} | Sharpe: {ev['sharpe']:.2f} | Fit: {ev['fitness']:.2f} | Turn: {ev['turnover']*100:.1f}% | Margin: {ev['margin_bps']:.1f}bps | Fails: {ev['fails']}")

    if ev['passes_checks']:
        print(f"  Passed all checks! Checking self-correlation against all 7 OS alphas...")
        st, max_c, recs = client.check_self_correlation_async(aid, timeout=50)
        print(f"  Max Self-Corr: {max_c:.4f} (Hurdle < {MAX_SELF_CORRELATION}) across {len(recs)} alphas")
        for r in recs:
            print(f"     vs {r[0]} ({r[1]}): {r[5]}")

        if max_c < MAX_SELF_CORRELATION:
            color = "PURPLE" if ev['sharpe'] >= 2.0 or ev['grade'] in ['EXCELLENT', 'SPECTACULAR'] else "BLUE"
            client.set_badge_and_name(aid, color, name)
            print(f"  >>> SUBMITTING {aid} ({name}) to OS! <<<")
            r = client.session.post(f"https://api.worldquantbrain.com/alphas/{aid}/submit", timeout=25)
            print(f"  Submit response HTTP {r.status_code}: {r.text[:120]}")
            if r.status_code in [200, 201]:
                submitted_count += 1
                print(f"  🎉 SUBMISSION #{submitted_count}/3 SUCCESSFUL! 🎉")
        else:
            print(f"  Correlation rejected: {max_c:.4f} >= {MAX_SELF_CORRELATION}")

print(f"\n=== FINISHED: Submitted {submitted_count} new alphas to OS ===")
