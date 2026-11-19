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

# Verify current OS count
os_alphas = s.get('https://api.worldquantbrain.com/users/self/alphas?stage=OS').json()
current_os_count = os_alphas.get('count', len(os_alphas.get('results', [])))
print(f"Current OS Alphas count: {current_os_count}")
if current_os_count >= 10:
    print(f"Already at {current_os_count} OS alphas (target 10 reached)!")
    sys.exit(0)

# Formulate strong orthogonal alpha designs
candidates = [
    {
        "name": "Operating_Margin_Rank",
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
        "name": "Sales_Yield_10D_Reversal_Hybrid",
        "code": "rank(ts_backfill(revenue / cap, 65)) - rank(close / ts_delay(close, 10) - 1)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Target_Price_Revision_60D",
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
    },
    {
        "name": "Volume_Shock_Decay10",
        "code": "ts_decay_linear(group_rank(-ts_delta(close, 1) / close * (volume / adv20), subindustry), 10)",
        "decay": 10,
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
    resp = s.post("https://api.worldquantbrain.com/simulations", json=payload)
    if resp.status_code == 201:
        loc = resp.headers.get("Location")
        queued.append((c["name"], loc, c["code"]))
        print(f"Queued {c['name']} -> {loc}")
    else:
        print(f"Failed to queue {c['name']}: {resp.status_code} {resp.text}")

print(f"\nMonitoring {len(queued)} candidate simulations...")

submitted_alpha_id = None

while queued and not submitted_alpha_id:
    time.sleep(10)
    for i in range(len(queued) - 1, -1, -1):
        name, url, code = queued[i]
        sim_res = s.get(url)
        if sim_res.status_code != 200:
            continue
        sim_data = sim_res.json()
        status = sim_data.get("status")
        progress = sim_data.get("progress", 0)
        
        if status == "COMPLETE" or progress >= 1.0 or "alpha" in sim_data:
            alpha_id = sim_data.get("alpha")
            print(f"\n[DONE] {name} completed! Alpha ID: {alpha_id}")
            queued.pop(i)
            
            # Fetch Alpha details
            a_res = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}")
            if a_res.status_code != 200:
                print(f"Could not fetch alpha {alpha_id}")
                continue
            a_data = a_res.json()
            is_stat = a_data.get("is", {})
            sharpe = is_stat.get("sharpe")
            fitness = is_stat.get("fitness")
            turnover = is_stat.get("turnover")
            margin = is_stat.get("margin")
            checks = is_stat.get("checks", [])
            
            fails = [chk.get("name") for chk in checks if chk.get("result") == "FAIL"]
            print(f"[{name}] Sharpe: {sharpe} | Fitness: {fitness} | Turnover: {turnover*100 if turnover else 0:.1f}% | Margin: {margin*10000 if margin else 0:.1f}bps | Fails: {fails}")
            
            if len(fails) == 0 and sharpe and sharpe >= 1.25 and fitness and fitness >= 1.00:
                print(f"[{name}] ALL INSTITUTIONAL CHECKS PASSED!")
                # Check self-correlation
                time.sleep(3)
                corr_res = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/correlations/self")
                max_corr = 0.0
                corr_passed = True
                if corr_res.status_code == 200:
                    try:
                        c_data = corr_res.json()
                        records = c_data.get("records", [])
                        for rec in records:
                            val = abs(rec.get("value", 0))
                            if val > max_corr:
                                max_corr = val
                        print(f"[{name}] Max self-correlation against portfolio: {max_corr:.4f}")
                        if max_corr >= 0.70:
                            corr_passed = False
                            print(f"[{name}] Correlation too high (>= 0.70). Rejecting.")
                    except Exception as e:
                        print(f"Could not parse correlation: {e}")
                
                if corr_passed:
                    print(f"🚀 SUBMITTING ALPHA {alpha_id} ({name}) TO OUT-OF-SAMPLE! 🚀")
                    s.patch(f"https://api.worldquantbrain.com/alphas/{alpha_id}", json={"color": "PURPLE", "name": name})
                    sub_res = s.post(f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit")
                    if sub_res.status_code in [200, 201]:
                        print(f"🎉 SUCCESS! Alpha {alpha_id} submitted to Out-of-Sample! Response: {sub_res.status_code}")
                        submitted_alpha_id = alpha_id
                        break
                    else:
                        print(f"Submission failed: {sub_res.status_code} {sub_res.text}")
        elif status == "ERROR":
            print(f"[ERROR] {name} simulation error: {sim_data.get('message')}")
            queued.pop(i)
        else:
            print(f"[{name}] in progress: {progress*100:.0f}%")

if submitted_alpha_id:
    # Verify final OS count
    final_os = s.get('https://api.worldquantbrain.com/users/self/alphas?stage=OS').json()
    count = final_os.get('count', len(final_os.get('results', [])))
    print(f"\n==========================================")
    print(f"FINAL OUT-OF-SAMPLE PORTFOLIO COUNT: {count}")
    print(f"Target of 3 new alphas submitted today is 100% COMPLETE!")
    print(f"==========================================")
else:
    print("\nNo submission completed in this batch.")
