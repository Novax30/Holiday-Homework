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
s.post('https://api.worldquantbrain.com/authentication')

sims = [
    {"sim_id": "3MOjyX7dD5989BNILGXJeL9", "name": "Overnight_Gap_Dispersion_30"},
    {"sim_id": "3IPTUnfpM4zI8FAA1IfZVUH", "name": "Idiosyncratic_Return_Vol_30"},
    {"sim_id": "1erJ0Y1Ec4sz9Ek7Tm3Jm4q", "name": "Vol_Term_Structure_Spread"}
]

print("Monitoring simulations...")
completed = {}
for iteration in range(30):
    for item in sims:
        sid = item["sim_id"]
        if sid in completed:
            continue
        try:
            r = s.get(f"https://api.worldquantbrain.com/simulations/{sid}")
            if r.status_code == 200:
                data = r.json()
                if data.get("alpha"):
                    alpha_id = data.get("alpha")
                    completed[sid] = alpha_id
                    print(f"[{item['name']}] SIM COMPLETED -> Alpha: {alpha_id}")
                elif data.get("status") == "ERROR":
                    completed[sid] = "ERROR"
                    print(f"[{item['name']}] SIM ERROR: {data.get('message')}")
                else:
                    progress = data.get("progress")
                    print(f"[{item['name']}] Progress: {progress}")
        except Exception as e:
            print(f"Error checking {sid}: {e}")
    if len(completed) == len(sims):
        break
    time.sleep(8)

print("\n--- RESULTS ANALYSIS ---")
for item in sims:
    sid = item["sim_id"]
    aid = completed.get(sid)
    if not aid or aid == "ERROR":
        continue
    a = s.get(f"https://api.worldquantbrain.com/alphas/{aid}").json()
    ar = a.get("is", {})
    grade = ar.get("grade")
    sharpe = ar.get("sharpe")
    fitness = ar.get("fitness")
    turnover = ar.get("turnover")
    margin_bps = (ar.get("margin") or 0) * 10000
    checks = ar.get("checks", [])
    failed_checks = [c["name"] for c in checks if c.get("result") not in ("PASS", "PENDING")]
    
    print(f"\n==================================================")
    print(f"Candidate: {item['name']} (Alpha ID: {aid})")
    print(f"Formula: {a.get('regular', {}).get('code')}")
    print(f"Grade: {grade} | Sharpe: {sharpe} | Fitness: {fitness} | Turnover: {turnover:.2%} | Margin: {margin_bps:.1f} bps")
    print(f"Failed checks: {failed_checks}")
    
    # If it meets institutional criteria, test correlation
    if sharpe and sharpe >= 1.25 and fitness and fitness >= 1.0 and not failed_checks:
        print(f"-> Qualified candidate! Testing self-correlation...")
        # Step 1: Trigger check
        sub_r = s.post(f"https://api.worldquantbrain.com/alphas/{aid}/submit")
        print(f"   Submit trigger status: {sub_r.status_code}")
        time.sleep(6)
        # Step 2: Read check result
        sub_r2 = s.post(f"https://api.worldquantbrain.com/alphas/{aid}/submit")
        print(f"   Submit verification status: {sub_r2.status_code}")
        if sub_r2.status_code in (200, 201):
            print(f"   *** SUBMISSION SUCCESSFUL! Alpha {aid} is now in OS! ***")
            # Update name and color
            s.patch(f"https://api.worldquantbrain.com/alphas/{aid}", json={"name": item["name"], "color": "PURPLE"})
        elif sub_r2.status_code == 403:
            corr_data = sub_r2.json().get("is", {}).get("selfCorrelated", {})
            max_corr = corr_data.get("max")
            records = corr_data.get("records", [])
            print(f"   Correlation rejection! Max correlation: {max_corr}")
            for rec in records:
                print(f"     Correlates with {rec[0]}: {rec[5]}")

