#!/usr/bin/env python3
"""
Targeted runner for verified SPECTACULAR/EXCELLENT alphas.
Runs until at least 2 EXCELLENT/SPECTACULAR alphas are confirmed.
"""
import sys, time
sys.path.insert(0, '.')
from grandmaster_alpha_engine import GrandmasterBrainClient, CheckValidator, MAX_SELF_CORRELATION, log_alpha_result, create_harness_session

client = GrandmasterBrainClient("xstreamnova@gmail.com", "nova@1234")
if not client.login():
    print("Login failed"); exit(1)

CANDIDATES = [
    # 1. Low-Volatility + Intermediate Trend Quality (Expected Sharpe 2.30+, Fitness 2.20+)
    {
        "name": "Spectacular_LowVol_Trend_Quality",
        "domain": "VOLATILITY_MOMENTUM",
        "formula": "group_rank(-ts_std_dev(high / low, 22), subindustry) + group_rank(ts_rank(close / ts_delay(close, 40), 60), subindustry)",
        "settings": {
            "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
            "delay": 1, "decay": 6, "neutralization": "SUBINDUSTRY", "truncation": 0.05,
            "pasteurization": "ON", "unitHandling": "VERIFY", "nanHandling": "OFF",
            "language": "FASTEXPR", "visualization": False
        }
    },
    # 2. Volume-Weighted Close Location Value (Expected Sharpe 2.01, Fitness 3.77)
    {
        "name": "Spectacular_CLV_Liquidity_Flow",
        "domain": "INTRADAY_MOMENTUM",
        "formula": "group_rank(ts_mean((2 * close - high - low) / (high - low + 0.001) * (volume / adv20), 20), subindustry)",
        "settings": {
            "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
            "delay": 1, "decay": 6, "neutralization": "SUBINDUSTRY", "truncation": 0.05,
            "pasteurization": "ON", "unitHandling": "VERIFY", "nanHandling": "OFF",
            "language": "FASTEXPR", "visualization": False
        }
    },
    # 3. Intermediate Trend Quality with 30-day window
    {
        "name": "Spectacular_LowVol_Trend_lb30",
        "domain": "VOLATILITY_MOMENTUM",
        "formula": "group_rank(-ts_std_dev(high / low, 30), subindustry) + group_rank(ts_rank(close / ts_delay(close, 60), 60), subindustry)",
        "settings": {
            "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
            "delay": 1, "decay": 6, "neutralization": "SUBINDUSTRY", "truncation": 0.05,
            "pasteurization": "ON", "unitHandling": "VERIFY", "nanHandling": "OFF",
            "language": "FASTEXPR", "visualization": False
        }
    },
    # 4. Cash Flow Enterprise Value Yield with Subindustry Ranking
    {
        "name": "Spectacular_FCF_Enterprise_Yield",
        "domain": "FUNDAMENTAL_YIELD",
        "formula": "group_rank(ts_rank(ts_backfill(cashflow_op / enterprise_value, 65), 180), subindustry)",
        "settings": {
            "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
            "delay": 1, "decay": 6, "neutralization": "SUBINDUSTRY", "truncation": 0.05,
            "pasteurization": "ON", "unitHandling": "VERIFY", "nanHandling": "OFF",
            "language": "FASTEXPR", "visualization": False
        }
    }
]

print("Starting Targeted High-Conviction Alpha Run...")
excellent_count = 0

for cand in CANDIDATES:
    if excellent_count >= 2:
        print(f"\n Target achieved: {excellent_count} EXCELLENT alphas completed!")
        break

    name = cand["name"]
    formula = cand["formula"]
    settings = cand["settings"]
    domain = cand["domain"]

    print(f"\n[DISPATCH] {name}")
    print(f"  Formula: {formula}")

    sim_url, err = client.simulate(formula, settings)
    if not sim_url:
        print(f"  [DISPATCH ERROR] {err}")
        continue

    print(f"  Sim dispatched: {sim_url}. Polling cluster...")
    alpha_id, data = client.poll_simulation(sim_url, timeout=400)
    if not alpha_id:
        print(f"  [SIM ERROR] {data.get('error')}")
        continue

    detail = client.get_alpha_details(alpha_id)
    if not detail:
        print(f"  [DETAIL ERROR] ID {alpha_id}")
        continue

    ev = CheckValidator.evaluate(detail)
    print(f"  [RESULT] ID: {alpha_id} | Grade: {ev['grade']} | Sharpe: {ev['sharpe']:.2f} | Fitness: {ev['fitness']:.2f} | Turnover: {ev['turnover']*100:.1f}% | Margin: {ev['margin_bps']:.1f} bps | Fails: {ev['fails']}")

    is_excellent_or_spectacular = (ev["grade"] in ["EXCELLENT", "SPECTACULAR"] or (ev["sharpe"] >= 1.58 and ev["fitness"] >= 1.50)) and ev["passes_checks"]

    if is_excellent_or_spectacular:
        print(f"  🌟 [EXCELLENT ALPHA DETECTED] Sharpe={ev['sharpe']:.2f}, Fitness={ev['fitness']:.2f}")
        color = "PURPLE" if ev["grade"] == "SPECTACULAR" or ev["sharpe"] >= 2.0 else "BLUE"
        client.set_badge_and_name(alpha_id, color, name)

        print(f"  Checking platform self-correlation...")
        c_status, max_corr, records = client.check_self_correlation_async(alpha_id)
        print(f"  Self-Correlation: {max_corr:.4f} across {len(records)} portfolio alphas (Hurdle < {MAX_SELF_CORRELATION})")

        if max_corr < MAX_SELF_CORRELATION:
            print(f"  >>> SUBMITTING {alpha_id} into Out-of-Sample (OS)... <<<")
            sub_resp = client.session.post(f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit", timeout=25)
            print(f"  Submission response HTTP {sub_resp.status_code}: {sub_resp.text[:100]}")
            excellent_count += 1
            print(f"  🎉 EXCELLENT COUNT: {excellent_count}/2")
        else:
            print(f"  High correlation ({max_corr:.4f} >= {MAX_SELF_CORRELATION})")
    else:
        print(f"  Alpha did not meet EXCELLENT threshold (Sharpe>=1.58 & Fitness>=1.50).")

print(f"\nRun concluded. Total EXCELLENT alphas processed: {excellent_count}")
