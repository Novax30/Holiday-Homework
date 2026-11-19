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

# Candidates specifically engineered for Fitness > 2.0, Turnover < 15%, Decay <= 4
candidates = [
    {
        "name": "Intraday_Spread_Volume_Dispersion",
        "code": "-ts_std_dev(volume / adv20, 30) * ((high - low) / vwap)",
        "decay": 3,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "TradeWhen_Cashflow_10D_Gated",
        "code": "trade_when(volume > adv20, group_rank(ts_rank(ts_backfill(cashflow_op / cap, 65), 126), subindustry) - 0.3 * group_rank(close / ts_delay(close, 10) - 1, subindustry), -1)",
        "decay": 3,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "VWAP_Dislocation_Range_Weighted",
        "code": "-ts_std_dev(close / vwap, 35) * (high / low)",
        "decay": 3,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    }
]

queued = []
for c in candidates:
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
    res = s.post("https://api.worldquantbrain.com/simulations", json=payload)
    if res.status_code == 201:
        loc = res.headers.get("Location")
        queued.append((c["name"], loc))
        print(f"Queued {c['name']} -> {loc}")
    else:
        print(f"Failed {c['name']}: {res.status_code} {res.text}")

print(f"\nMonitoring {len(queued)} candidate simulations...")
