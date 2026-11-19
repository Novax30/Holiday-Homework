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
        "name": "IV_Parkinson_Vol_Spread_Quantile",
        "code": "quantile(ts_mean(ts_backfill(implied_volatility_call_30 / (parkinson_volatility_120 + 0.001), 5), 20))",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SECTOR",
        "universe": "TOP3000"
    },
    {
        "name": "Intraday_Range_Volume_Decay3",
        "code": "group_rank(ts_decay_linear(-(high - close) / (high - low + 0.001) + (close - low) / (high - low + 0.001), 3), subindustry)",
        "decay": 3,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Monthly_Return_Volume_Shock_Decay3",
        "code": "group_rank(ts_decay_linear(-ts_delta(close, 20) / close * (volume / adv20), 3), subindustry)",
        "decay": 3,
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
