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
        "name": "TradeWhen_AssetTurnover_Gated",
        "code": "trade_when(volume > adv20, group_rank(ts_rank(ts_backfill(revenue / assets, 65), 126), subindustry), -1)",
        "decay": 3,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "TradeWhen_Analyst_EPS_Gated",
        "code": "trade_when(volume > adv20, group_rank(ts_rank(est_eps / close, 126), industry), -1)",
        "decay": 3,
        "truncation": 0.05,
        "neutralization": "INDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "IV_90_30_Term_Structure_Decay4",
        "code": "quantile(ts_mean(ts_backfill(implied_volatility_call_90 / implied_volatility_call_30, 5), 20))",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SECTOR",
        "universe": "TOP3000"
    }
]

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
        print(f"Queued {c['name']} -> {res.headers.get('Location')}")
    else:
        print(f"Failed {c['name']}: {res.status_code} {res.text}")
