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
    ('2t0COydeG5dR8D4Vgrpsm6R', 'PTP_Vol_Scaled_Ratio'),
    ('2G3FqJ2LI4E18wU15WXo7esY', 'OpIncome_Vol_Scaled_Ratio'),
    ('3kPPCr4qP5eXae13BpDen0G', 'PTP_Vol_Dispersion_Product')
]

completed = {}
for _ in range(20):
    all_done = True
    for sid, name in sims:
        if sid in completed:
            continue
        r = s.get(f'https://api.worldquantbrain.com/simulations/{sid}').json()
        alpha = r.get('alpha')
        status = r.get('status')
        if alpha:
            completed[sid] = alpha
            print(f'[{name}] COMPLETED -> Alpha: {alpha}', flush=True)
        elif status == 'ERROR':
            completed[sid] = 'ERROR'
            print(f'[{name}] ERROR: {r.get("message")}', flush=True)
        else:
            all_done = False
            print(f'[{name}] progress: {r.get("progress")}', flush=True)
    if all_done:
        break
    time.sleep(10)

print("\n--- HYBRID EVALUATION ---", flush=True)
for sid, name in sims:
    aid = completed.get(sid)
    if not aid or aid == 'ERROR':
        continue
    a = s.get(f'https://api.worldquantbrain.com/alphas/{aid}').json()
    ar = a.get('is', {})
    grade = ar.get('grade')
    sharpe = ar.get('sharpe')
    fitness = ar.get('fitness')
    turnover = ar.get('turnover')
    margin_bps = (ar.get('margin') or 0) * 10000
    checks = ar.get('checks', [])
    failed_checks = [c['name'] for c in checks if c.get('result') not in ('PASS', 'PENDING')]
    
    print(f"\n==================================================", flush=True)
    print(f"Candidate: {name} (Alpha ID: {aid})", flush=True)
    print(f"Formula: {a.get('regular', {}).get('code')}", flush=True)
    print(f"Grade: {grade} | Sharpe: {sharpe} | Fitness: {fitness} | Turnover: {turnover:.2%} | Margin: {margin_bps:.1f} bps", flush=True)
    print(f"Failed checks: {failed_checks}", flush=True)

    if sharpe and sharpe >= 1.25 and fitness and fitness >= 1.0 and not failed_checks:
        print(f"Checking correlation for {aid}...", flush=True)
        s.post(f"https://api.worldquantbrain.com/alphas/{aid}/submit")
        time.sleep(6)
        sub2 = s.post(f"https://api.worldquantbrain.com/alphas/{aid}/submit")
        print(f"Submit status: {sub2.status_code}", flush=True)
        if sub2.status_code in (200, 201):
            print(f"*** SUBMISSION CONFIRMED: Alpha {aid} is in OS! ***", flush=True)
            s.patch(f"https://api.worldquantbrain.com/alphas/{aid}", json={"name": name, "color": "PURPLE"})
        elif sub2.status_code == 403:
            corr_data = sub2.json().get("is", {}).get("selfCorrelated", {})
            print(f"Max correlation: {corr_data.get('max')}", flush=True)
            for rec in corr_data.get("records", []):
                print(f"  vs {rec[0]}: {rec[5]}", flush=True)
