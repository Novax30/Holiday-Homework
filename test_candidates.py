import os, sys, time, json, requests
from dotenv import load_dotenv

load_dotenv()
sess = requests.Session()
sess.auth = (os.getenv("BRAIN_API_KEY_ID"), os.getenv("BRAIN_API_KEY_SECRET"))

# Test 5 orthogonal candidates
candidates = [
    {
        "name": "Operating_Margin_Efficiency",
        "code": "group_rank(ts_rank(ts_backfill(operating_income / (revenue + 0.01), 65), 252), industry)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "INDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "EPS_Revision_Momentum",
        "code": "group_rank(ts_rank(est_eps - ts_delay(est_eps, 20), 60), industry)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "INDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Sales_Yield_Hybrid",
        "code": "rank(ts_backfill(revenue / cap, 65)) - rank(close / ts_delay(close, 10) - 1)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Target_Price_Revision",
        "code": "group_rank(ts_rank((est_ptp - ts_delay(est_ptp, 20)) / close, 60), subindustry)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Analyst_Spread_Exhaustion",
        "code": "group_rank(ts_rank((est_ptp - close) / close, 120), industry)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "INDUSTRY",
        "universe": "TOP3000"
    }
]

sim_urls = {}
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
    r = sess.post("https://api.worldquantbrain.com/simulations", json=payload)
    if r.status_code == 201:
        loc = r.headers.get("Location")
        sim_urls[c["name"]] = loc
        print(f"Dispatched {c['name']}: {loc}")
    else:
        print(f"Failed {c['name']}: {r.status_code} {r.text}")

print(f"Successfully queued {len(sim_urls)} simulations.")
