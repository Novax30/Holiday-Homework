import os, requests, json, time
from datetime import datetime

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
    ('3TcYs01LM4jUbDX1bKrlsKCX', 'Quarterly_Shadow_Dispersion_63'),
    ('13vmXH9kY4SoaxI13VpZYjtB', 'Blended_Shadow_Reversal_Hybrid'),
    ('papMebuK50db8B1dx47EIs2', 'Quarterly_NATR_Dispersion_63')
]

completed = {}
for attempt in range(25):
    all_done = True
    for sid, name in sims:
        if sid in completed:
            continue
        try:
            r = s.get(f'https://api.worldquantbrain.com/simulations/{sid}', timeout=20).json()
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
        except Exception as e:
            print(f'[{name}] poll error: {e}', flush=True)
            all_done = False
    if all_done:
        break
    time.sleep(8)

print("\n--- DECORRELATED CANDIDATE EVALUATION ---", flush=True)
submitted_alpha = None
for sid, name in sims:
    if submitted_alpha:
        break
    aid = completed.get(sid)
    if not aid or aid == 'ERROR':
        continue
    a = s.get(f'https://api.worldquantbrain.com/alphas/{aid}').json()
    ar = a.get('is', {})
    grade = ar.get('grade')
    sharpe = ar.get('sharpe')
    fitness = ar.get('fitness')
    turnover = ar.get('turnover')
    returns = ar.get('returns')
    margin_bps = (ar.get('margin') or 0) * 10000
    checks = ar.get('checks', [])
    failed_checks = [c['name'] for c in checks if c.get('result') not in ('PASS', 'PENDING')]
    
    print(f"\n==================================================", flush=True)
    print(f"Candidate: {name} (Alpha ID: {aid})", flush=True)
    print(f"Formula: {a.get('regular', {}).get('code')}", flush=True)
    print(f"Grade: {grade} | Sharpe: {sharpe} | Fitness: {fitness} | Returns: {returns:.2%} | Turnover: {turnover:.2%} | Margin: {margin_bps:.1f} bps", flush=True)
    print(f"Failed checks: {failed_checks}", flush=True)

    # Check institutional qualification
    if sharpe and sharpe >= 1.25 and fitness and fitness >= 1.0 and not failed_checks:
        print(f"-> Testing self-correlation against OS portfolio...", flush=True)
        sub1 = s.post(f"https://api.worldquantbrain.com/alphas/{aid}/submit")
        print(f"   Submit trigger status: {sub1.status_code}", flush=True)
        time.sleep(6)
        sub2 = s.post(f"https://api.worldquantbrain.com/alphas/{aid}/submit")
        print(f"   Submit verification status: {sub2.status_code}", flush=True)
        if sub2.status_code in (200, 201):
            print(f"\n**************************************************", flush=True)
            print(f"*** SPECTACULAR SUBMISSION SUCCESSFUL! ***", flush=True)
            print(f"*** Alpha {aid} is now officially in OS! ***", flush=True)
            print(f"**************************************************", flush=True)
            # Patch name and PURPLE color
            s.patch(f"https://api.worldquantbrain.com/alphas/{aid}", json={"name": name, "color": "PURPLE"})
            submitted_alpha = {
                "alpha_id": aid,
                "name": name,
                "formula": a.get('regular', {}).get('code'),
                "grade": grade,
                "sharpe": sharpe,
                "fitness": fitness,
                "returns": returns,
                "turnover": turnover,
                "margin_bps": margin_bps,
                "submitted_at": datetime.now().isoformat()
            }
            with open("/Users/nova/Documents/ALPAHA/spectacular_engine_status.json", "w") as sf:
                json.dump({"state": "SUBMITTED", "timestamp": datetime.now().isoformat(), "details": submitted_alpha}, sf, indent=2)
            break
        elif sub2.status_code == 403:
            corr_data = sub2.json().get("is", {}).get("selfCorrelated", {})
            max_c = corr_data.get("max")
            print(f"   Rejected on correlation: max = {max_c}", flush=True)
            for rec in corr_data.get("records", [])[:3]:
                print(f"     vs {rec[0]}: {rec[5]}", flush=True)

