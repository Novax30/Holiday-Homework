import os, requests, json, time

env = {}
with open('/Users/nova/Documents/ALPAHA/.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

s = requests.Session()
s.auth = (env['BRAIN_EMAIL'], env['BRAIN_PASSWORD'])
r = s.post('https://api.worldquantbrain.com/authentication')
if r.status_code != 201:
    print('Auth failed:', r.status_code, r.text)
    exit(1)

candidates = [
    {
        "name": "Vol_Asymmetry_Upside_Ratio",
        "code": "ts_std_dev(max(returns, 0), 25) / (ts_std_dev(max(-returns, 0), 25) + 0.001)",
        "decay": 2,
        "neutralization": "INDUSTRY"
    },
    {
        "name": "Intraday_Trend_Efficiency",
        "code": "ts_mean(abs(close - open) / (high - low + 0.0001 * close), 20)",
        "decay": 2,
        "neutralization": "INDUSTRY"
    },
    {
        "name": "Intraday_Realized_Skewness",
        "code": "ts_mean(signed_power((close - (high + low)/2) / (high - low + 0.0001 * close), 3), 20)",
        "decay": 2,
        "neutralization": "INDUSTRY"
    }
]

sim_jobs = []
for c in candidates:
    payload = {
        "type": "REGULAR",
        "settings": {
            "instrumentType": "EQUITY",
            "region": "USA",
            "universe": "TOP3000",
            "delay": 1,
            "decay": c["decay"],
            "neutralization": c["neutralization"],
            "truncation": 0.05,
            "pasteurization": "ON",
            "unitHandling": "VERIFY",
            "nanHandling": "OFF",
            "maxTrade": "OFF",
            "maxPosition": "OFF",
            "language": "FASTEXPR",
            "visualization": False
        },
        "regular": c["code"]
    }
    resp = s.post("https://api.worldquantbrain.com/simulations", json=payload)
    if resp.status_code == 201:
        sim_id = resp.headers.get("Location", "").split("/")[-1]
        print(f"Dispatched {c['name']} -> sim {sim_id}")
        sim_jobs.append({"sim_id": sim_id, "name": c["name"], "code": c["code"]})
    else:
        print(f"Failed {c['name']}: {resp.status_code} {resp.text}")
    time.sleep(2)

print(f"Total dispatched: {len(sim_jobs)}")
