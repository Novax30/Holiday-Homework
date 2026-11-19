#!/usr/bin/env python3
import requests, time, os, sys, json

env = {}
with open('/Users/nova/Documents/ALPAHA/.env') as f:
    for line in f:
        if '=' in line:
            k, v = line.strip().split('=', 1)
            env[k.strip('\"\' ')] = v.strip('\"\' ')

s = requests.Session()
s.auth = (env.get('BRAIN_EMAIL'), env.get('BRAIN_PASSWORD'))
r = s.post('https://api.worldquantbrain.com/authentication')
if r.status_code not in [200, 201]:
    print('Auth failed:', r.status_code, r.text)
    sys.exit(1)
print("Auth successful.")

# Define 4 candidate expressions using S-Tier operators
test_candidates = [
    {
        "name": "TradeWhen_Fundamental_Dislocation",
        "code": "trade_when(volume > 1.2 * adv20, group_rank(ts_backfill(operating_income / cap, 65), subindustry) - group_rank(close / ts_delay(close, 5) - 1, subindustry), -1)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Quantile_Analyst_Cashflow_Surprise",
        "code": "quantile(ts_rank(est_eps / close, 60)) - quantile(close / ts_delay(close, 5) - 1)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Residual_Price_Exhaustion",
        "code": "group_rank(ts_regression(close / ts_delay(close, 5) - 1, volume / adv20, 20), subindustry) * (-1)",
        "decay": 6,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "TradeWhen_TargetPrice_Exhaustion",
        "code": "trade_when(volume > adv20, rank(est_ptp / close) - rank(close / ts_delay(close, 5) - 1), -1)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    }
]

for c in test_candidates:
    payload = {
        "type": "REGULAR",
        "settings": {
            "instrumentType": "EQUITY",
            "region": "USA",
            "universe": c["universe"],
            "delay": 1,
            "decay": c["decay"],
            "neutralization": c["neutralization"],
            "truncation": c["truncation"],
            "pasteurization": "ON",
            "unitHandling": "VERIFY",
            "nanHandling": "OFF",
            "language": "FASTEXPR",
            "visualization": False
        },
        "regular": c["code"]
    }
    resp = s.post("https://api.worldquantbrain.com/simulations", json=payload)
    if resp.status_code == 201:
        loc = resp.headers.get("Location")
        print(f"✅ Queued {c['name']} -> {loc}")
    else:
        print(f"❌ Failed to queue {c['name']}: {resp.status_code} {resp.text}")
