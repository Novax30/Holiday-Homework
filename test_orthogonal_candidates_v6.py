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
        "name": "Midpoint_Dislocation_Decay7",
        "code": "group_rank(ts_decay_linear(-(close - (high + low)/2) / (high - low + 0.001) * (volume / adv20), 7), subindustry)",
        "decay": 7,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Bar_Return_Exhaustion_Decay6",
        "code": "group_rank(ts_decay_linear(-(close - open) / (high - low + 0.001) * (volume / adv20), 6), subindustry)",
        "decay": 6,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Intraday_Volume_Expansion_TradeWhen",
        "code": "trade_when(volume > adv20, group_rank(ts_decay_linear(-(close - open) / (high - low + 0.001), 4), subindustry), -1)",
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
