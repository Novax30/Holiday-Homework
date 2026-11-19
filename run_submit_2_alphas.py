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

os_alphas = s.get('https://api.worldquantbrain.com/users/self/alphas?stage=OS&limit=50').json()
start_count = os_alphas.get('count', len(os_alphas.get('results', [])))
print(f"Current Out-of-Sample Alphas in account: {start_count}")

# High-probability orthogonal candidates
candidates = [
    {
        "name": "NonLinear_Quantile_EPS_Surprise",
        "code": "quantile(ts_rank(est_eps / close, 60)) - quantile(close / ts_delay(close, 5) - 1)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Asset_Turnover_Dislocation",
        "code": "group_rank(ts_backfill(revenue / assets, 65), subindustry) - group_rank(close - ts_mean(close, 5), subindustry)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "Analyst_PTP_10D_Reversal",
        "code": "rank(est_ptp / close) - rank(close / ts_delay(close, 10) - 1)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    },
    {
        "name": "TradeWhen_Fundamental_Volume_Gated",
        "code": "trade_when(volume > 1.1 * adv20, group_rank(ts_backfill(operating_income / cap, 65), subindustry) - group_rank(close / ts_delay(close, 5) - 1, subindustry), -1)",
        "decay": 4,
        "truncation": 0.05,
        "neutralization": "SUBINDUSTRY",
        "universe": "TOP3000"
    }
]

grade_to_color = {
    "SPECTACULAR": "PURPLE",
    "EXCELLENT": "BLUE",
    "GOOD": "GREEN",
    "AVERAGE": None
}

in_flight = {}
queue = list(candidates)
submitted_count = 0
target_submissions = 2

# First, check if QP0eZNzX can be submitted as candidate #1
print("\nChecking ready candidate QP0eZNzX...")
chk_res = s.get('https://api.worldquantbrain.com/alphas/QP0eZNzX').json()
chk_fails = [c.get('name') for c in chk_res.get('is', {}).get('checks', []) if c.get('result') == 'FAIL']
if len(chk_fails) == 0 and chk_res.get('is', {}).get('sharpe', 0) >= 1.25 and chk_res.get('is', {}).get('fitness', 0) >= 1.00:
    print("QP0eZNzX meets institutional hurdles! Checking correlation...")
    time.sleep(3)
    corr_res = s.get('https://api.worldquantbrain.com/alphas/QP0eZNzX/correlations/self')
    max_c = 0.0
    passed_corr = True
    if corr_res.status_code == 200:
        try:
            records = corr_res.json().get('records', [])
            for r in records:
                v = abs(r[5]) if len(r) > 5 and isinstance(r[5], (int, float)) else 0.0
                if v > max_c:
                    max_c = v
            print(f"QP0eZNzX Max self-correlation: {max_c:.4f}")
            if max_c >= 0.70:
                passed_corr = False
        except:
            pass
    
    if passed_corr:
        col = grade_to_color.get(chk_res.get('grade'), None)
        s.patch('https://api.worldquantbrain.com/alphas/QP0eZNzX', json={"name": "Sales_Yield_10D_Reversal_Hybrid", "color": col})
        sub = s.post('https://api.worldquantbrain.com/alphas/QP0eZNzX/submit')
        if sub.status_code in [200, 201]:
            submitted_count += 1
            print(f"🎉 SUCCESS ({submitted_count}/{target_submissions})! Alpha QP0eZNzX submitted to Out-of-Sample! 🎉")
            print(f"   Name: Sales_Yield_10D_Reversal_Hybrid | Sharpe: {chk_res.get('is',{}).get('sharpe')} | Grade: {chk_res.get('grade')} | Color: {col}")

while submitted_count < target_submissions and (queue or in_flight):
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
            in_flight[c["name"]] = {"url": loc, "code": c["code"]}
            print(f"[QUEUE] Dispatched {c['name']} -> {loc}")
        elif res.status_code == 429:
            queue.insert(0, c)
            print("[THROTTLE] Concurrent limit, waiting...")
            break
        else:
            print(f"[ERROR] Failed {c['name']}: {res.status_code} {res.text}")

    time.sleep(8)
    
    completed = []
    for name, info in list(in_flight.items()):
        chk = s.get(info["url"])
        if chk.status_code != 200:
            continue
        data = chk.json()
        status = data.get("status")
        progress = data.get("progress", 0)
        
        if status == "COMPLETE" or progress >= 1.0 or "alpha" in data:
            alpha_id = data.get("alpha")
            completed.append(name)
            print(f"\n[DONE] Simulation finished for {name}! Alpha ID: {alpha_id}")
            
            a_res = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}").json()
            is_stat = a_res.get("is", {})
            sharpe = is_stat.get("sharpe")
            fitness = is_stat.get("fitness")
            turnover = is_stat.get("turnover")
            margin = is_stat.get("margin")
            grade = a_res.get("grade")
            fails = [chk.get("name") for chk in is_stat.get("checks", []) if chk.get("result") == "FAIL"]
            
            print(f"[{name}] Sharpe: {sharpe} | Fitness: {fitness} | Grade: {grade} | TO: {turnover*100 if turnover else 0:.1f}% | Margin: {margin*10000 if margin else 0:.1f}bps | Fails: {fails}")
            
            if len(fails) == 0 and sharpe and sharpe >= 1.25 and fitness and fitness >= 1.00:
                print(f"[{name}] Passed institutional checks! Verifying correlation...")
                time.sleep(3)
                c_res = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/correlations/self")
                max_corr = 0.0
                corr_passed = True
                if c_res.status_code == 200:
                    try:
                        records = c_res.json().get("records", [])
                        for rec in records:
                            val = abs(rec[5]) if len(rec) > 5 and isinstance(rec[5], (int, float)) else 0.0
                            if val > max_corr:
                                max_corr = val
                        print(f"[{name}] Max self-correlation against portfolio: {max_corr:.4f}")
                        if max_corr >= 0.70:
                            corr_passed = False
                            print(f"[{name}] Correlation too high ({max_corr:.4f} >= 0.70). Rejecting.")
                    except:
                        pass
                
                if corr_passed:
                    col = grade_to_color.get(grade, None)
                    print(f"🚀 SUBMITTING ALPHA {alpha_id} ({name}) TO OUT-OF-SAMPLE (Grade: {grade}, Color: {col})! 🚀")
                    s.patch(f"https://api.worldquantbrain.com/alphas/{alpha_id}", json={"name": name, "color": col})
                    sub = s.post(f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit")
                    if sub.status_code in [200, 201]:
                        submitted_count += 1
                        print(f"🎉 SUCCESS ({submitted_count}/{target_submissions})! Alpha {alpha_id} submitted to Out-of-Sample! 🎉")
                        if submitted_count >= target_submissions:
                            break
                    else:
                        print(f"Submission failed: {sub.status_code} {sub.text}")
            else:
                print(f"[{name}] Did not pass institutional criteria.")
                
        elif status == "ERROR":
            print(f"[ERROR] Simulation error for {name}: {data.get('message')}")
            completed.append(name)
        else:
            print(f"[{name}] In progress ({progress*100:.0f}%)")

    for n in completed:
        in_flight.pop(n, None)

print("\n==========================================")
final_os = s.get('https://api.worldquantbrain.com/users/self/alphas?stage=OS&limit=50').json()
final_count = final_os.get('count', len(final_os.get('results', [])))
print(f"Initial Out-of-Sample Count: {start_count}")
print(f"Final Out-of-Sample Count: {final_count}")
print(f"Target 2 Alphas Submitted: {'COMPLETE' if final_count >= start_count + 2 else 'IN PROGRESS'}")
print("==========================================")
