#!/usr/bin/env python3
"""
Test 3 completely orthogonal archetypes that have ZERO overlap with the 7 active OS alphas:
1. Sloan Accruals (Cashflow vs Net Income Quality)
2. Fama-French Quality x Conservative Investment (Asset Growth)
3. Conditional VWAP Microstructure
"""
import sys, time
sys.path.insert(0, '.')
from grandmaster_alpha_engine import GrandmasterBrainClient, CheckValidator, MAX_SELF_CORRELATION

client = GrandmasterBrainClient("xstreamnova@gmail.com", "nova@1234")
if not client.login():
    print("Login failed"); exit(1)

CANDIDATES = [
    {
        "name": "Orthogonal_Sloan_Accrual_Quality",
        "formula": "group_rank(-ts_backfill((net_income - cashflow_op) / assets, 65), industry)",
        "decay": 6, "truncation": 0.05, "neutralization": "INDUSTRY"
    },
    {
        "name": "Orthogonal_Operating_Quality_Asset_Growth",
        "formula": "group_rank(ts_backfill(operating_income / assets, 65), industry) - group_rank(ts_delta(ts_backfill(assets, 65), 252) / ts_delay(ts_backfill(assets, 65), 252), industry)",
        "decay": 8, "truncation": 0.05, "neutralization": "INDUSTRY"
    },
    {
        "name": "Orthogonal_Gated_VWAP_Exhaustion",
        "formula": "trade_when(volume > adv20, -ts_rank((close - vwap) / close, 10), -1)",
        "decay": 6, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    }
]

for cand in CANDIDATES:
    name = cand["name"]
    formula = cand["formula"]
    settings = {
        "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
        "delay": 1, "decay": cand["decay"], "neutralization": cand["neutralization"],
        "truncation": cand["truncation"], "pasteurization": "ON", "unitHandling": "VERIFY",
        "nanHandling": "OFF", "language": "FASTEXPR", "visualization": False
    }

    print(f"\n[DISPATCH] {name}")
    print(f"  Formula: {formula}")

    sim_url, err = client.simulate(formula, settings)
    if not sim_url:
        print(f"  Dispatch error: {err}")
        continue

    alpha_id, data = client.poll_simulation(sim_url, timeout=400)
    if not alpha_id:
        print(f"  Sim error: {data.get('error')}")
        continue

    detail = client.get_alpha_details(alpha_id)
    if not detail:
        continue

    ev = CheckValidator.evaluate(detail)
    print(f"  [RESULT] ID: {alpha_id} | Grade: {ev['grade']} | Sharpe: {ev['sharpe']:.2f} | Fitness: {ev['fitness']:.2f} | Turnover: {ev['turnover']*100:.1f}% | Margin: {ev['margin_bps']:.1f} bps | Fails: {ev['fails']}")

    if ev['passes_checks']:
        print(f"  Checking self-correlation against all 7 OS alphas...")
        st, max_c, recs = client.check_self_correlation_async(alpha_id)
        print(f"  Max Self-Corr: {max_c:.4f} (Hurdle < {MAX_SELF_CORRELATION}) across {len(recs)} alphas")
        if max_c < MAX_SELF_CORRELATION:
            print(f"  >>> SUBMITTING {alpha_id} into OS! <<<")
            r = client.session.post(f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit", timeout=25)
            print(f"  Submit response HTTP {r.status_code}: {r.text[:120]}")
