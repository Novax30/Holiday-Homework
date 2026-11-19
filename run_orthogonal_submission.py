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

sims = [
    ("Asset_Turnover_Dislocation_Ranked", "https://api.worldquantbrain.com/simulations/4vzw9m7fK4VTa8IqAC4LNZ2"),
    ("IV_120_30_Term_Structure", "https://api.worldquantbrain.com/simulations/4AM0gO5OI4IlbntSXpKjEe0"),
    ("Analyst_PTP_Premium_Quantile", "https://api.worldquantbrain.com/simulations/4pXLOlgpx4KO8UfsDaHHUAm")
]

grade_to_color = {
    "SPECTACULAR": "PURPLE",
    "EXCELLENT": "BLUE",
    "GOOD": "GREEN",
    "AVERAGE": None
}

pending = list(sims)
submitted_count = 0
target_submissions = 2

while pending and submitted_count < target_submissions:
    time.sleep(8)
    for i in range(len(pending)-1, -1, -1):
        name, url = pending[i]
        res = s.get(url)
        if res.status_code != 200:
            continue
        data = res.json()
        status = data.get("status")
        progress = data.get("progress", 0)
        
        if status == "COMPLETE" or progress >= 1.0 or "alpha" in data:
            alpha_id = data.get("alpha")
            print(f"\n[DONE] Simulation finished for {name}! Alpha ID: {alpha_id}")
            pending.pop(i)
            
            a_res = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}").json()
            is_stat = a_res.get("is", {})
            sharpe = is_stat.get("sharpe")
            fitness = is_stat.get("fitness")
            turnover = is_stat.get("turnover")
            margin = is_stat.get("margin")
            grade = a_res.get("grade")
            fails = [chk.get("name") for chk in is_stat.get("checks", []) if chk.get("result") == "FAIL"]
            
            print(f"[{name}] Results:")
            print(f"  Sharpe: {sharpe}")
            print(f"  Fitness: {fitness}")
            print(f"  Grade: {grade}")
            print(f"  Turnover: {turnover*100 if turnover else 0:.2f}%")
            print(f"  Margin: {margin*10000 if margin else 0:.2f} bps")
            print(f"  Fails: {fails}")
            
            if len(fails) == 0 and sharpe and sharpe >= 1.25 and fitness and fitness >= 1.00:
                print(f"[{name}] Passed institutional checks! Checking correlation against all 20 OS alphas...")
                time.sleep(4)
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
                            print(f"[{name}] Correlation {max_corr:.4f} >= 0.70. Rejecting.")
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
            print(f"[ERROR] {name}: {data.get('message')}")
            pending.pop(i)
        else:
            print(f"[{name}] in progress ({progress*100:.0f}%)")

print("\n==========================================")
final_os = s.get('https://api.worldquantbrain.com/users/self/alphas?stage=OS&limit=50').json()
final_count = final_os.get('count', len(final_os.get('results', [])))
print(f"Final Out-of-Sample Count: {final_count}")
print("==========================================")
