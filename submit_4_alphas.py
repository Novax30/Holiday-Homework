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
print("Auth successful for user:", env.get('BRAIN_EMAIL'))

# Check current OS count
os_alphas = s.get('https://api.worldquantbrain.com/users/self/alphas?stage=OS').json()
start_count = os_alphas.get('count', len(os_alphas.get('results', [])))
print(f"Current Out-of-Sample count: {start_count}")

# 5 High-Probability Orthogonal Candidates
candidates = [
    {
        "name": "Elite_BalanceSheet_Price_Dislocation",
        "code": "rank(ts_backfill(liabilities / assets, 65)) - rank(close - ts_mean(close, 5))",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Analyst_Earnings_Yield_Momentum",
        "code": "group_rank(ts_rank(est_eps / close, 60), industry)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "INDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Hybrid_Analyst_PTP_Reversal",
        "code": "rank(est_ptp / close) - rank(close - ts_mean(close, 5))",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "IV_Call_Term_Structure_Slope",
        "code": "quantile(ts_mean(ts_backfill(implied_volatility_call_60 / implied_volatility_call_30, 5), 30))",
        "decay": 8,
        "truncation": 0.05,
        "neutralization": "SECTOR",
        "universe": "TOP3000"
    },
    {
        "name": "Sales_Yield_10D_Reversal_Hybrid",
        "code": "rank(ts_backfill(revenue / cap, 65)) - rank(close / ts_delay(close, 10) - 1)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    }
]

submitted_count = 0
target_submissions = 4

# We can queue up to 3 concurrent simulations at a time
queue = list(candidates)
in_flight = {}

while (submitted_count < target_submissions) and (queue or in_flight):
    # Dispatch up to 3 concurrent
    while len(in_flight) < 3 and queue:
        c = queue.pop(0)
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
            in_flight[c["name"]] = {"url": loc, "code": c["code"], "start": time.time()}
            print(f"[QUEUE] Dispatched {c['name']} -> {loc}")
        elif res.status_code == 429:
            # Re-insert at front of queue and wait
            queue.insert(0, c)
            print("[THROTTLE] Concurrent limit reached, waiting...")
            break
        else:
            print(f"[ERROR] Failed to queue {c['name']}: {res.status_code} {res.text}")

    time.sleep(8)
    
    # Check in-flight
    completed_names = []
    for name, info in list(in_flight.items()):
        chk = s.get(info["url"])
        if chk.status_code != 200:
            continue
        data = chk.json()
        status = data.get("status")
        progress = data.get("progress", 0)
        
        if status == "COMPLETE" or progress >= 1.0 or "alpha" in data:
            alpha_id = data.get("alpha")
            print(f"\n[DONE] Simulation finished for {name}! Alpha ID: {alpha_id}")
            completed_names.append(name)
            
            # Fetch details
            a_res = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}").json()
            is_stat = a_res.get("is", {})
            sharpe = is_stat.get("sharpe")
            fitness = is_stat.get("fitness")
            turnover = is_stat.get("turnover")
            margin = is_stat.get("margin")
            checks = is_stat.get("checks", [])
            fails = [chk.get("name") for chk in checks if chk.get("result") == "FAIL"]
            
            print(f"[{name}] Sharpe: {sharpe} | Fitness: {fitness} | TO: {turnover*100 if turnover else 0:.1f}% | Margin: {margin*10000 if margin else 0:.1f}bps | Fails: {fails}")
            
            # Evaluate institutional checks
            if len(fails) == 0 and sharpe and sharpe >= 1.25 and fitness and fitness >= 1.00:
                print(f"[{name}] Institutional checks PASSED! Checking self-correlation...")
                time.sleep(3)
                
                # Check self-correlation
                c_res = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/correlations/self")
                max_corr = 0.0
                corr_passed = True
                if c_res.status_code == 200:
                    try:
                        c_data = c_res.json()
                        records = c_data.get("records", [])
                        for rec in records:
                            val = abs(rec.get("value", 0))
                            if val > max_corr:
                                max_corr = val
                        print(f"[{name}] Max self-correlation against portfolio: {max_corr:.4f}")
                        if max_corr >= 0.70:
                            corr_passed = False
                            print(f"[{name}] Self-correlation {max_corr:.4f} >= 0.70 -> REJECTED")
                    except Exception as e:
                        print(f"Correlation parse error: {e}")
                
                if corr_passed:
                    print(f"🚀 SUBMITTING ALPHA {alpha_id} ({name}) TO OUT-OF-SAMPLE! 🚀")
                    s.patch(f"https://api.worldquantbrain.com/alphas/{alpha_id}", json={"color": "PURPLE", "name": name})
                    sub = s.post(f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit")
                    if sub.status_code in [200, 201]:
                        submitted_count += 1
                        print(f"🎉 SUCCESS ({submitted_count}/{target_submissions})! Alpha {alpha_id} submitted to OS! 🎉")
                        if submitted_count >= target_submissions:
                            break
                    else:
                        print(f"Submission failed: {sub.status_code} {sub.text}")
            else:
                print(f"[{name}] Did not pass institutional criteria.")
                
        elif status == "ERROR":
            print(f"[ERROR] Simulation error for {name}: {data.get('message')}")
            completed_names.append(name)
        else:
            print(f"[{name}] In progress ({progress*100:.0f}%)")

    for n in completed_names:
        in_flight.pop(n, None)

print("\n==========================================")
final_os = s.get('https://api.worldquantbrain.com/users/self/alphas?stage=OS').json()
final_count = final_os.get('count', len(final_os.get('results', [])))
print(f"Starting OS Count: {start_count}")
print(f"Final OS Count: {final_count}")
print(f"Net New Submissions: {final_count - start_count}")
print("==========================================")
