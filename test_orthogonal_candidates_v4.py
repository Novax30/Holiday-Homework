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
        "name": "AssetTurnover_20D_Reversal_Hybrid",
        "code": "group_rank(ts_rank(ts_backfill(revenue / assets, 65), 126), subindustry) - group_rank(close / ts_delay(close, 20) - 1, subindustry)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Analyst_PTP_20D_Reversal_Hybrid",
        "code": "rank(est_ptp / close) - rank(close / ts_delay(close, 20) - 1)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Intraday_OpenClose_Dispersion_30",
        "code": "-ts_std_dev(close / open, 30)",
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
