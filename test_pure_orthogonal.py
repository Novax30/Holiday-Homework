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

# Pure orthogonal candidates without 5-day price subtraction
candidates = [
    {
        "name": "Operating_Margin_Efficiency_Group",
        "code": "group_rank(ts_rank(ts_backfill(operating_income / (revenue + 0.01), 65), 252), industry)",
        "decay": 3,
        "truncation": 0.05,
        "neutralization": "INDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "IV_60_PutCall_Ratio_Quantile",
        "code": "quantile(ts_mean(ts_backfill(implied_volatility_call_60 / (implied_volatility_put_60 + 0.001), 5), 20))",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SECTOR",
        "universe": "TOP3000"
    },
    {
        "name": "Intraday_Volume_Expansion_Decay",
        "code": "group_rank(ts_decay_linear(-(close - open) / (high - low + 0.001) * (volume / adv20), 4), subindustry)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
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
