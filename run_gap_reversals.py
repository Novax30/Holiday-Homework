#!/usr/bin/env python3
"""
Test 3 novel price-microstructure archetypes:
1. Overnight Gap Reversal: -(open - delay(close, 1)) / delay(close, 1)
2. Normalized Intraday Candle Reversal: -(close - open) / (high - low + 0.001)
3. Volume-Weighted Return Exhaustion: -ts_delta(close, 1) * (volume / adv20)
"""
import sys, time
sys.path.insert(0, '.')
from grandmaster_alpha_engine import GrandmasterBrainClient, CheckValidator, MAX_SELF_CORRELATION

client = GrandmasterBrainClient("xstreamnova@gmail.com", "nova@1234")
if not client.login():
    print("Login failed"); exit(1)

CANDS = [
    {
        "name": "Overnight_Gap_Reversal",
        "formula": "group_rank(-(open - ts_delay(close, 1)) / ts_delay(close, 1), subindustry)",
        "decay": 6, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "Intraday_Candle_Reversal",
        "formula": "group_rank(-(close - open) / (high - low + 0.001), subindustry)",
        "decay": 6, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "Volume_Shock_Return_Exhaustion",
        "formula": "group_rank(-ts_delta(close, 1) / close * (volume / adv20), subindustry)",
        "decay": 6, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    }
]

print("=== DISPATCHING NOVEL MICROSTRUCTURE ARCHETYPES ===")
for cand in CANDS:
    settings = {
        "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
        "delay": 1, "decay": cand["decay"], "neutralization": cand["neutralization"],
        "truncation": cand["truncation"], "pasteurization": "ON", "unitHandling": "VERIFY",
        "nanHandling": "OFF", "language": "FASTEXPR", "visualization": False
    }
    url, err = client.simulate(cand["formula"], settings)
    print(f"[DISPATCH] {cand['name']}: {url} (err={err})")
    cand["url"] = url

print("\n=== POLLING SIMULATION RESULTS ===")
for cand in CANDS:
    if not cand.get("url"):
        continue
    name = cand["name"]
    print(f"\nPolling {name}...")
    aid, data = client.poll_simulation(cand["url"], timeout=300)
    if not aid:
        print(f"  Failed: {data.get('error')}")
        continue
    d = client.get_alpha_details(aid)
    if not d:
        continue
    ev = CheckValidator.evaluate(d)
    print(f"  ID: {aid} | Grade: {ev['grade']} | Sharpe: {ev['sharpe']:.2f} | Fit: {ev['fitness']:.2f} | Turn: {ev['turnover']*100:.1f}% | Margin: {ev['margin_bps']:.1f}bps | Fails: {ev['fails']}")

    if ev['passes_checks']:
        print(f"  Passed all checks! Checking correlation against 7 OS alphas...")
        st, max_c, recs = client.check_self_correlation_async(aid, timeout=45)
        print(f"  Max Self-Corr: {max_c:.4f} across {len(recs)} active alphas")
        if max_c < MAX_SELF_CORRELATION:
            color = "PURPLE" if ev['sharpe'] >= 2.0 or ev['grade'] in ['EXCELLENT', 'SPECTACULAR'] else "BLUE"
            client.set_badge_and_name(aid, color, name)
            print(f"  >>> SUBMITTING {aid} ({name}) to OS! <<<")
            resp = client.session.post(f"https://api.worldquantbrain.com/alphas/{aid}/submit", timeout=25)
            print(f"  Submit HTTP {resp.status_code}: {resp.text[:120]}")
