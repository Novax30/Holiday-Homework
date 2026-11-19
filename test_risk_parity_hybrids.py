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
        "name": "PTP_Vol_Scaled_Ratio",
        "code": "(group_rank(ts_rank(est_ptp / close, 126), subindustry) - 0.5) / (ts_std_dev((high - low) / close, 22) + 0.01)",
        "decay": 2,
        "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "OpIncome_Vol_Scaled_Ratio",
        "code": "(group_rank(ts_rank(operating_income / cap, 126), subindustry) - 0.5) / (ts_std_dev((high - low) / close, 22) + 0.01)",
        "decay": 2,
        "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "PTP_Vol_Dispersion_Product",
        "code": "(group_rank(ts_rank(est_ptp / close, 126), subindustry) - 0.5) * (-ts_std_dev(high / low, 22))",
        "decay": 2,
        "neutralization": "SUBINDUSTRY"
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
        print(f"Failed to dispatch {c['name']}: {resp.status_code} {resp.text}")
    time.sleep(2)

print(f"Total dispatched: {len(sim_jobs)}")
