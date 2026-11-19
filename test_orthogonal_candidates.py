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
s.post('https://api.worldquantbrain.com/authentication')

candidates = [
    {
        "name": "Asset_Turnover_Dislocation_Ranked",
        "code": "group_rank(ts_backfill(revenue / assets, 65), subindustry) - group_rank(close - ts_mean(close, 5), subindustry)",
        "decay": 3,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "IV_120_30_Term_Structure",
        "code": "quantile(ts_mean(ts_backfill(implied_volatility_call_120 / implied_volatility_call_30, 5), 20))",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SECTOR",
        "universe": "TOP3000"
    },
    {
        "name": "Analyst_PTP_Premium_Quantile",
        "code": "quantile(ts_rank((est_ptp - close) / close, 60)) - quantile(close / ts_delay(close, 5) - 1)",
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

print(f"\nDispatched {len(queued)} orthogonal simulations with decay <= 4.")
